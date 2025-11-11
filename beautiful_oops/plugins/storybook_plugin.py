from __future__ import annotations
from typing import Set

from .models.storybook import StoryBook
from ..core.adventure import BaseOopsPlugin, MomentEvent, Event
from ..core.moment import StageInfo, MomentCtx


class StorybookPlugin(BaseOopsPlugin):
    storybook: StoryBook = StoryBook("undefined")
    _attached = False

    def supported_events(self) -> Set[Event]:
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

    def _ensure_attached(self, ctx: MomentCtx) -> None:
        adv = ctx.moment.adv
        if not self._attached:
            # 挂到 adv.storybook
            setattr(adv, "storybook", self.storybook)
            setattr(self.storybook, "title", getattr(adv, "name", "adventure"))
            self._attached = True

    def on_moment_enter(self, ctx: MomentCtx) -> None:
        self._ensure_attached(ctx)
        s: StageInfo = ctx.moment.stage
        self.storybook.enter(s.chapter, s.stage)

    def on_moment_before_fn(self, ctx: MomentCtx) -> None:
        s: StageInfo = ctx.moment.stage
        self.storybook.attempt_enter(s.chapter, s.stage, ctx.attempt)

    def on_moment_retry(self, ctx: MomentCtx) -> None:
        s: StageInfo = ctx.moment.stage
        self.storybook.attempt_fail(s.chapter, s.stage, ctx.attempt, oops=ctx.oops)

    def on_moment_success(self, ctx: MomentCtx) -> None:
        s: StageInfo = ctx.moment.stage
        self.storybook.attempt_success(s.chapter, s.stage, ctx.attempt)
        self.storybook.success(s.chapter, s.stage, result=ctx.result)

    def on_moment_fail(self, ctx: MomentCtx) -> None:
        s: StageInfo = ctx.moment.stage
        self.storybook.attempt_fail(s.chapter, s.stage, ctx.attempt, oops=ctx.oops)
        assert ctx.oops is not None, "on_moment_fail should be called with ctx.oops set"
        self.storybook.fail(s.chapter, s.stage, oops=ctx.oops)
