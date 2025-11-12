from __future__ import annotations
from typing import Optional, Set, cast

from .models.storybook import StoryBook
from ..core.adventure import BaseOopsPlugin, MomentEvent, Event
from ..core.moment import MomentCtx, StageInfo


class StorybookPlugin(BaseOopsPlugin):
    """
    把 StoryBook 的 enter/attempt_enter/success/fail 行为挂到 on_moment_* 事件上。
    - 不依赖 ctx.span_id（很多实现里没有），统一用可推导的 attempt_id 构造方法。
    - 通过 _ensure_attached 返回已收窄为 StoryBook 的实例，避免 mypy union-attr 报错。
    """
    def __init__(self, storybook: Optional[StoryBook] = None):
        self.storybook: Optional[StoryBook] = storybook
        self._attached = False

    def supported_events(self) -> Set[Event]:
        # 注意：只列出你项目里真实存在的 MomentEvent 值；不要写 CANCEL 之类不存在的枚举
        return {
            MomentEvent.ENTER,
            MomentEvent.BEFORE_FN,
            MomentEvent.RETRY,
            MomentEvent.SUCCESS,
            MomentEvent.FAIL,
            MomentEvent.IGNORE,
            MomentEvent.FALLBACK,
            MomentEvent.ABORT,
            MomentEvent.EXIT,
        }

    def _ensure_attached(self, ctx: MomentCtx) -> StoryBook:
        """
        确保 plugin 已经把 storybook 挂到 adv 上，并返回已收窄类型的 StoryBook。
        这样后续使用 sb 时，mypy 不会再提示 union-attr。
        """
        if (not self._attached) or (self.storybook is None):
            adv = ctx.moment.adv
            if self.storybook is None:
                # 懒初始化：优先用 adv.name 作为书名
                title = getattr(adv, "name", "adventure")
                self.storybook = StoryBook(title)
            setattr(adv, "storybook", self.storybook)
            self._attached = True
        return cast(StoryBook, self.storybook)

    def _attempt_id(self, ctx: MomentCtx) -> str:
        """
        统一构造 attempt_id，而不是依赖 ctx.span_id：
        attempt_id = f"{trace_id}:{chapter}/{stage}#{attempt}"
        """
        adv = ctx.moment.adv
        s: StageInfo = ctx.moment.stage
        return StoryBook.build_attempt_id(adv.trace_id, s.chapter, s.stage, ctx.attempt)

    def on_moment_enter(self, ctx: MomentCtx) -> None:
        sb = self._ensure_attached(ctx)
        adv = ctx.moment.adv
        s: StageInfo = ctx.moment.stage
        parent = getattr(ctx, "parent_span_id", None)
        sb.enter(
            trace_id=adv.trace_id,
            chapter=s.chapter,
            stage=s.stage,
            parent_span_id=parent,  # 允许 moment 挂到父 attempt / 父 span 下
        )

    def on_moment_before_fn(self, ctx: MomentCtx) -> None:
        sb = self._ensure_attached(ctx)
        adv = ctx.moment.adv
        s: StageInfo = ctx.moment.stage
        parent = getattr(ctx, "parent_span_id", None)
        sb.attempt_enter(
            trace_id=adv.trace_id,
            chapter=s.chapter,
            stage=s.stage,
            attempt=ctx.attempt,
            span_id=self._attempt_id(ctx),     # 显式传入 attempt_id
            parent_span_id=parent,
        )

    def on_moment_retry(self, ctx: MomentCtx) -> None:
        sb = self._ensure_attached(ctx)
        sb.attempt_fail(self._attempt_id(ctx), getattr(ctx, "oops", None))

    # 若你没有 CANCEL 事件，可删去这个钩子
    # def on_moment_cancel(self, ctx: MomentCtx) -> None:
    #     sb = self._ensure_attached(ctx)
    #     sb.attempt_fail(self._attempt_id(ctx), getattr(ctx, "oops", None))

    def on_moment_success(self, ctx: MomentCtx) -> None:
        sb = self._ensure_attached(ctx)
        sb.attempt_success(self._attempt_id(ctx), getattr(ctx, "result", None))

    def on_moment_fail(self, ctx: MomentCtx) -> None:
        sb = self._ensure_attached(ctx)
        sb.attempt_fail(self._attempt_id(ctx), getattr(ctx, "oops", None))
        adv = ctx.moment.adv
        s: StageInfo = ctx.moment.stage
        sb.fail(adv.trace_id, s.chapter, s.stage, getattr(ctx, "oops", None))
