# beautiful_oops/plugins/tracing_stack_plugin.py
from __future__ import annotations
from typing import Optional, Set, List
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from contextvars import ContextVar

from beautiful_oops.core.adventure import BaseOopsPlugin, Event, AdventureEvent, MomentEvent
from beautiful_oops.core.moment import MomentCtx
from beautiful_oops.utils.trace_id_generator import TraceIdGenerator


@dataclass
class _TracingContext:
    trace_id: ContextVar[Optional[str]] = field(default_factory=lambda: ContextVar("trace_id", default=None))
    span_stack: ContextVar[List[str]] = field(default_factory=lambda: ContextVar("span_stack", default=[]))

    # helpers
    def set_trace_id(self, tid: str) -> None:
        self.trace_id.set(tid)

    def get_trace_id(self) -> Optional[str]:
        return self.trace_id.get()

    def current_span(self) -> Optional[str]:
        st = self.span_stack.get()
        return st[-1] if st else None

    def push_span(self, sid: str) -> None:
        st = list(self.span_stack.get())
        st.append(sid)
        self.span_stack.set(st)

    def pop_span(self) -> Optional[str]:
        st = list(self.span_stack.get())
        if not st:
            return None
        sid = st.pop()
        self.span_stack.set(st)
        return sid


class TracingStackPlugin(BaseOopsPlugin):

    # --------- 静态访问桥（可选）：让外部能读到“当前插件上下文” ---------
    _current_plugin: ContextVar[Optional["TracingStackPlugin"]] = ContextVar("_current_tracing_plugin", default=None)

    @classmethod
    def current(cls) -> Optional["TracingStackPlugin"]:
        return cls._current_plugin.get()

    @classmethod
    def current_trace_id(cls) -> Optional[str]:
        p = cls.current()
        return p.ctx.get_trace_id() if p else None

    @classmethod
    def current_span_id(cls) -> Optional[str]:
        p = cls.current()
        return p.ctx.current_span() if p else None

    # -------------------------------------------------------------------------
    def __init__(self, *, sample_ratio: float = 1.0, make_root_span: bool = True, flush_timeout: float = 1.5):
        assert 0.0 <= sample_ratio <= 1.0
        self.sample_ratio = sample_ratio
        self.make_root_span = make_root_span
        self.flush_timeout = flush_timeout

        self.ctx = _TracingContext()
        self._started = False
        self._sampled = True
        self._root_span_id: Optional[str] = None

    def supported_events(self) -> Set[Event]:
        return {AdventureEvent.START, AdventureEvent.END, MomentEvent.ENTER, MomentEvent.EXIT}

    # ----------------------- Adventure 生命周期 -----------------------
    async def on_adventure_start(self, adv) -> None:
        if self._started:
            return
        self._started = True
        # 将“当前插件”绑定进 ContextVar，保证同一请求内任何地方可读到
        self._current_plugin.set(self)

        tid = getattr(adv, "trace_id", None) or self.ctx.get_trace_id() or TraceIdGenerator.new_trace_id()
        setattr(adv, "trace_id", tid)
        self.ctx.set_trace_id(tid)

        self._sampled = self._should_sample(tid)
        if self._sampled and self.make_root_span and self.ctx.current_span() is None:
            self._root_span_id = TraceIdGenerator.new_span_id()
            self.ctx.push_span(self._root_span_id)

        setattr(adv, "started_at", datetime.utcnow())

    async def on_adventure_end(self, adv) -> None:
        async def _flush():
            # 这里可以做 sink/export flush
            pass

        try:
            await asyncio.wait_for(_flush(), timeout=self.flush_timeout)
        except Exception:
            pass

        # 清理 root span（只有我们创建时才弹）
        if self._root_span_id and self.ctx.current_span() == self._root_span_id:
            self.ctx.pop_span()
        self._root_span_id = None
        self._started = False
        # 结束时不主动清 trace_id：让响应阶段还能读；如需清理，可自行 ctx.set_trace_id(None)

    # ----------------------- Moment 进出栈 -----------------------
    async def on_moment_enter(self, ctx: MomentCtx) -> None:
        if not self._sampled:
            return
        parent = self.ctx.current_span()
        span = TraceIdGenerator.new_span_id()
        # 建议在 MomentCtx dataclass 中显式声明 Optional[str] 字段
        ctx.parent_span_id = parent  # type: ignore[attr-defined]
        ctx.span_id = span  # type: ignore[attr-defined]
        self.ctx.push_span(span)

    async def on_moment_exit(self, ctx: MomentCtx) -> None:
        if not self._sampled:
            return
        try:
            top = self.ctx.current_span()
            span = getattr(ctx, "span_id", None)
            if top and span and top == span:
                self.ctx.pop_span()
        except Exception:
            pass

    # ----------------------- 采样策略 -----------------------
    def _should_sample(self, trace_id: str) -> bool:
        if self.sample_ratio >= 1.0:
            return True
        if self.sample_ratio <= 0.0:
            return False
        try:
            bucket = int(trace_id[-2:], 16) / 255.0
            return bucket < self.sample_ratio
        except Exception:
            return True
