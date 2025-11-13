from __future__ import annotations
from time import time
from typing import Optional, Set

from .models.storybook import StoryBook
from ..core.adventure import BaseOopsPlugin, Event, MomentEvent, AdventureEvent
from ..core.moment import StageInfo, MomentCtx
from ..core.oops import OopsError
from ..utils.trace_id_generator import TraceIdGenerator


class StorybookPlugin(BaseOopsPlugin):
    """
    把 Adventure 的事件转成 StoryBook 的“分组运行统计”。

    规则：
      - 每个 Moment（chapter/stage）的一次完整执行 = 一个 run
      - run 里包含多个 attempt（重试）
      - StoryBook 渲染时按 (chapter,stage) 聚合 + run 展开
    """

    def __init__(self, storybook: Optional[StoryBook] = None):
        self.storybook: Optional[StoryBook] = storybook
        self._attached_advs: Set[int] = set()

    def supported_events(self) -> Set[Event]:
        return {
            AdventureEvent.END,
            MomentEvent.ENTER,
            MomentEvent.BEFORE_FN,
            MomentEvent.RETRY,
            MomentEvent.SUCCESS,
            MomentEvent.FAIL,
            MomentEvent.ABORT,
            MomentEvent.FALLBACK,
        }

    # ---- 内部工具 ----
    def _ensure_storybook(self, ctx: MomentCtx) -> StoryBook:
        adv = ctx.moment.adv
        if self.storybook is None:
            title = getattr(adv, "name", "adventure")
            self.storybook = StoryBook(title)
        if id(adv) not in self._attached_advs:
            setattr(adv, "storybook", self.storybook)
            self._attached_advs.add(id(adv))
        return self.storybook  # type: ignore[return-value]

    def _run_id_for_ctx(self, ctx: MomentCtx) -> str:
        """
        为一个 Moment（生命周期内）生成稳定 run_id，
        挂在 ctx.moment 上，确保重试时不变。
        """
        m = ctx.moment
        rid = getattr(m, "_storybook_run_id", None)
        if rid is None:
            s: StageInfo = m.stage
            trace_id = getattr(m.adv, "trace_id", "no-trace")
            rid = f"{trace_id}:{s.chapter}/{s.stage}:{id(m)}"
            setattr(m, "_storybook_run_id", rid)
        return rid

    def _attempt_start(self, ctx: MomentCtx) -> None:
        setattr(ctx, "_storybook_attempt_started_at", time())

    def _attempt_end(self, ctx: MomentCtx, error: Optional[OopsError] = None) -> None:
        sb = self.storybook
        if not sb:
            return

        run_id = self._run_id_for_ctx(ctx)
        started = getattr(ctx, "_storybook_attempt_started_at", None)
        if started is None:
            return

        dur = max(0.0, time() - started)
        span_id = getattr(ctx, "span_id", None) or TraceIdGenerator.new_span_id()
        sb.attempt_end(
            run_id=run_id,
            span_id=span_id,
            attempt=ctx.attempt,
            duration=dur,
            error=getattr(error, "message", None) if error else None,
        )

    # ---- 事件实现 ----
    def on_moment_enter(self, ctx: MomentCtx) -> None:
        sb = self._ensure_storybook(ctx)
        run_id = self._run_id_for_ctx(ctx)
        s: StageInfo = ctx.moment.stage
        span_id = getattr(ctx, "span_id", None) or TraceIdGenerator.new_span_id()
        sb.moment_enter(run_id=run_id, chapter=s.chapter, stage=s.stage, span_id=span_id)

    def on_moment_before_fn(self, ctx: MomentCtx) -> None:
        sb = self._ensure_storybook(ctx)
        run_id = self._run_id_for_ctx(ctx)
        span_id = getattr(ctx, "span_id", None) or TraceIdGenerator.new_span_id()
        sb.attempt_enter(run_id=run_id, span_id=span_id, attempt=ctx.attempt)
        self._attempt_start(ctx)

    def on_moment_retry(self, ctx: MomentCtx) -> None:
        # 本次 attempt 结束（失败），moment 继续
        if ctx.oops is not None:
            self._attempt_end(ctx, error=ctx.oops)

    def on_moment_success(self, ctx: MomentCtx) -> None:
        # 最后一次 attempt 成功，同时关闭 moment
        sb = self.storybook
        if not sb:
            return
        self._attempt_end(ctx, error=None)
        run_id = self._run_id_for_ctx(ctx)
        s: StageInfo = ctx.moment.stage
        sb.moment_end(run_id=run_id, chapter=s.chapter, stage=s.stage, success=True)

    def on_moment_fail(self, ctx: MomentCtx) -> None:
        # Hero 决定 ABORT / FALLBACK 时，会触发 FAIL，这是最终失败
        sb = self.storybook
        if not sb:
            return
        if ctx.oops is not None:
            self._attempt_end(ctx, error=ctx.oops)
        run_id = self._run_id_for_ctx(ctx)
        s: StageInfo = ctx.moment.stage
        sb.moment_end(run_id=run_id, chapter=s.chapter, stage=s.stage, success=False)

    def on_adventure_end(self, adv) -> None:
        # 不直接打印，打印交给 StorybookConsoleSinkPlugin
        return
