from __future__ import annotations
from typing import Set
import asyncio
from ..core.adventure import BaseOopsPlugin, Event, AdventureEvent
from .models.storybook import StoryBook


class StorybookConsoleSinkPlugin(BaseOopsPlugin):
    def __init__(self, print_on_end: bool = True):
        self.print_on_end = print_on_end

    def supported_events(self) -> Set[Event]:
        return {AdventureEvent.END}

    def on_adventure_end(self, adv) -> None:
        if not self.print_on_end:
            return
        sb: StoryBook | None = getattr(adv, "storybook", None)
        if not sb:
            return
        asyncio.create_task(self._print_async(sb))

    async def _print_async(self, sb: StoryBook) -> None:
        print(f"\n📘 Adventure: {sb.title}")
        print(sb.render_ascii())
