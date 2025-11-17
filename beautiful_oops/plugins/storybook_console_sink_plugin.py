from __future__ import annotations
from typing import Set

from ..core.adventure import BaseOopsPlugin, Event, AdventureEvent
from .models.storybook import StoryBook


class StorybookConsoleSinkPlugin(BaseOopsPlugin):
    """
    在 Adventure END 时，把 StoryBook 的 DAG/统计信息渲染成 ASCII 树输出。
    """

    def __init__(
            self,
            print_on_end: bool = True,
            limit_per_stage: int = 3,
            show_attempt_spans: bool = True,
            attempt_span_limit: int = 3,
    ):
        self.print_on_end = print_on_end
        self.limit_per_stage = limit_per_stage
        self.show_attempt_spans = show_attempt_spans
        self.attempt_span_limit = attempt_span_limit

    def supported_events(self) -> Set[Event]:
        return {AdventureEvent.END}

    def on_adventure_end(self, adv) -> None:
        if not self.print_on_end:
            return
        sb: StoryBook | None = getattr(adv, "storybook", None)
        if not sb:
            return
        # 同步打印，避免 event loop 中再开协程
        print(
            sb.render_ascii(
                limit_per_stage=self.limit_per_stage,
                show_attempt_spans=self.show_attempt_spans,
                attempt_span_limit=self.attempt_span_limit,
            )
        )
