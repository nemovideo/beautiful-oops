from __future__ import annotations

import asyncio
import inspect
import traceback
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, Protocol, runtime_checkable, List, Callable, Optional, Union
from contextvars import ContextVar

# ---- 依赖你的现有模型 ----
from beautiful_oops.core.hero import Hero, HeroFactory, Decision
from beautiful_oops.core.oops import OopsError, OopsSolution
from beautiful_oops.core.moment import Moment, MomentCtx, StageInfo
from beautiful_oops.utils.trace_id_generator import TraceIdGenerator


# ==========================================================
# 事件定义
# ==========================================================
class MomentEvent(StrEnum):
    ENTER = auto()
    BEFORE_FN = auto()
    SUCCESS = auto()
    FAIL = auto()
    RETRY = auto()
    FALLBACK = auto()
    IGNORE = auto()
    ABORT = auto()
    EXIT = auto()


class AdventureEvent(StrEnum):
    START = auto()
    END = auto()


Event = Union[MomentEvent, AdventureEvent]


# ==========================================================
# 插件协议定义
# ==========================================================
@runtime_checkable
class OopsPlugin(Protocol):
    def supported_events(self) -> set[Event]: ...

    def on_any(self, event: Event, payload: Any) -> Any: ...

    # —— Moment 事件钩子 ——
    def on_moment_enter(self, ctx: MomentCtx) -> Any: ...

    def on_moment_success(self, ctx: MomentCtx) -> Any: ...

    def on_moment_fail(self, ctx: MomentCtx) -> Any: ...

    def on_moment_retry(self, ctx: MomentCtx) -> Any: ...

    def on_moment_fallback(self, ctx: MomentCtx) -> Any: ...

    def on_moment_ignore(self, ctx: MomentCtx) -> Any: ...

    def on_moment_abort(self, ctx: MomentCtx) -> Any: ...

    def on_moment_exit(self, ctx: MomentCtx) -> Any: ...

    # —— Adventure 生命周期钩子 ——
    def on_adventure_start(self, adv: Adventure) -> Any: ...

    def on_adventure_end(self, adv: Adventure) -> Any: ...


class BaseOopsPlugin:
    def supported_events(self) -> set[Event]:
        return set()


# ==========================================================
# Adventure 主体
# ==========================================================
@dataclass
class Adventure:
    name: str = "adventure"
    trace_id: str = field(default_factory=TraceIdGenerator.new_trace_id)
    hero: Hero = field(default_factory=lambda: HeroFactory.default())
    plugins: list[OopsPlugin] = field(default_factory=list)
    stop_on_plugin_error: bool = False
    debug: bool = False
    filter: Callable[..., bool] = staticmethod(lambda **_: True)

    _plugins: list[OopsPlugin] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self):
        self._plugins.extend(self.plugins)

    @staticmethod
    async def _maybe_await(fn, *args, **kwargs):
        if inspect.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        ret = fn(*args, **kwargs)
        if inspect.isawaitable(ret):
            return await ret
        return ret

    async def emit_event(self, event: Event, payload: Any):
        if isinstance(event, MomentEvent):
            method = f"on_moment_{event.name.lower()}"
        else:
            method = f"on_adventure_{event.name.lower()}"

        for p in list(self._plugins):
            try:
                declared = getattr(p, "supported_events", None)
                if callable(declared):
                    se = declared()
                    if se and event not in se:
                        continue
            except Exception as e:
                if self.debug:
                    print(f"[plugin:{p.__class__.__name__}] supported_events error: {e}")
                    traceback.print_exc()
                if self.stop_on_plugin_error:
                    raise

            fn_any = getattr(p, "on_any", None)
            if callable(fn_any):
                try:
                    await self._maybe_await(fn_any, event, payload)
                except Exception as e:
                    if self.debug:
                        print(f"[plugin:{p.__class__.__name__}] on_any error: {e}")
                        traceback.print_exc()
                    if self.stop_on_plugin_error:
                        raise

            fn = getattr(p, method, None)
            if callable(fn):
                try:
                    await self._maybe_await(fn, payload)
                except Exception as e:
                    if self.debug:
                        print(f"[plugin:{p.__class__.__name__}] {method} error: {e}")
                        traceback.print_exc()
                    if self.stop_on_plugin_error:
                        raise

    async def enter_moment(self, moment: Moment) -> Any:
        stage: StageInfo = moment.stage
        ctx: MomentCtx = moment.next_attempt()
        await self.emit_event(MomentEvent.ENTER, ctx)

        while True:
            try:
                await self.emit_event(MomentEvent.BEFORE_FN, ctx)
                ctx.result = await self._maybe_await(moment.fn)
                await self.emit_event(MomentEvent.SUCCESS, ctx)
                break

            except Exception as e:
                ctx.oops = OopsError.of(e)
                advice = moment.elf.advise(ctx)
                decision: Decision = moment.adv.hero.decide(ctx=ctx, advice=advice)

                if decision.action == OopsSolution.ABORT:
                    await self.emit_event(MomentEvent.ABORT, ctx)
                    await self.emit_event(MomentEvent.FAIL, ctx)
                    raise OopsError(e, message=f"Aborted at {stage.chapter}/{stage.stage}: {e}") from e

                if decision.action == OopsSolution.IGNORE:
                    await self.emit_event(MomentEvent.IGNORE, ctx)
                    await self.emit_event(MomentEvent.SUCCESS, ctx)
                    break

                if decision.action == OopsSolution.FALLBACK:
                    await self.emit_event(MomentEvent.FALLBACK, ctx)
                    await self.emit_event(MomentEvent.FAIL, ctx)
                    raise

                if decision.action == OopsSolution.RETRY:
                    await self.emit_event(MomentEvent.RETRY, ctx)
                    if self.debug:
                        print(
                            f"[RETRY] {stage.chapter}/{stage.stage} attempt={ctx.attempt} wait={decision.wait_seconds}s")
                    if decision.wait_seconds and decision.wait_seconds > 0:
                        await asyncio.sleep(decision.wait_seconds)
                    ctx = moment.next_attempt()
                    continue

        await self.emit_event(MomentEvent.EXIT, ctx)
        return ctx.result

    async def start(self):
        register_adventure(self)
        await self.emit_event(AdventureEvent.START, self)

    async def end(self):
        await self.emit_event(AdventureEvent.END, self)
        remove_adventure(self)

    @classmethod
    def auto(cls, adv: "Adventure"):
        class _AutoCtx:
            def __enter__(self):
                register_adventure(adv)
                asyncio.run(adv.emit_event(AdventureEvent.START, adv))
                return adv

            def __exit__(self, exc_type, exc, tb):
                try:
                    asyncio.run(adv.emit_event(AdventureEvent.END, adv))
                finally:
                    remove_adventure(adv)

            async def __aenter__(self):
                await adv.start()
                return adv

            async def __aexit__(self, exc_type, exc, tb):
                await adv.end()

        return _AutoCtx()

    @staticmethod
    def auto_start(adv: "Adventure") -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            register_adventure(adv)
            asyncio.run(adv.emit_event(AdventureEvent.START, adv))
            return
        raise RuntimeError("auto_start() is sync-only inside a running loop; use `await adv.start()` instead.")

    @staticmethod
    def auto_end(adv: "Adventure") -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            try:
                asyncio.run(adv.emit_event(AdventureEvent.END, adv))
            finally:
                remove_adventure(adv)
            return
        raise RuntimeError("auto_end() is sync-only inside a running loop; use `await adv.end()` instead.")


# ==========================================================
# Adventure Pool 工具（与事件解耦）
# ==========================================================
_ctx_adv_pool: ContextVar[List[Adventure]] = ContextVar("_adventure_pool", default=[])


def get_pool() -> List[Adventure]:
    return _ctx_adv_pool.get()


def register_adventure(adv: "Adventure") -> None:
    pool = get_pool()
    if adv not in pool:
        pool.append(adv)


def remove_adventure(adv: "Adventure") -> None:
    if adv is None:
        return
    pool = get_pool()
    try:
        pool.remove(adv)
    except ValueError:
        pass


def clear_pool() -> None:
    _ctx_adv_pool.set([])


def _call_filter(adv: Adventure, kwargs: dict[str, Any]) -> bool:
    f = getattr(adv, "filter", None)
    if not callable(f):
        return True
    try:
        sig = inspect.signature(f)
        if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
            return bool(f(**kwargs))
        call_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return bool(f(**call_kwargs))
    except Exception:
        return False


def find_adventure(
        *,
        stage: Optional[StageInfo] = None,
        event: Optional[Event] = None,
        **extra,
) -> Adventure:
    pool = get_pool()
    if not pool:
        adv = Adventure(name="default adventure")
        pool.append(adv)

    kwargs = {"stage": stage, "event": event, **extra}
    for adv in pool:
        if _call_filter(adv, kwargs):
            return adv

    return pool[0]
