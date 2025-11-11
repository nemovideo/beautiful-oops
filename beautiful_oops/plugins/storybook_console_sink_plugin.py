# plugins/sinks/console_tree.py
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Optional, Callable, Set, List, Tuple

from beautiful_oops import BaseOopsPlugin, AdventureEvent, Event
from beautiful_oops.plugins.models.storybook import Footprint


class StorybookConsoleSinkPlugin(BaseOopsPlugin):
    """
    在 Adventure 结束时输出 StoryBook 树形轨迹。
    - background=False：同步渲染（适合 CLI/单测/with Adventure.auto）
    - background=True：仅在已有长期事件循环中用 create_task 异步渲染
    - only_when：条件开关（例如 only_when=lambda adv: adv.debug）
    - show_duration：是否显示每步用时
    """

    def __init__(
            self,
            *,
            background: bool = False,
            show_duration: bool = True,
            only_when: Optional[Callable[[object], bool]] = None,
    ):
        self.background = background
        self.show_duration = show_duration
        self.only_when = only_when

    def supported_events(self) -> Set[Event]:
        return {AdventureEvent.END}

    def on_adventure_end(self, adv) -> None:
        if self.only_when and not self.only_when(adv):
            return
        sb = getattr(adv, "storybook", None)
        if not sb:
            return

        # —— 短生命周期 loop（asyncio.run）下不要异步；直接同步渲染更可靠 ——
        if not self.background:
            render_story_tree(sb, show_duration=self.show_duration)
            return

        # —— 背景异步渲染：只在长期事件循环中使用（FastAPI/Uvicorn） ——
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中的 loop，退化为同步渲染
            render_story_tree(sb, show_duration=self.show_duration)
            return

        if loop.is_closed():
            render_story_tree(sb, show_duration=self.show_duration)
            return

        # 尽量不阻塞主流程
        loop.create_task(_async_render(sb, self.show_duration))


async def _async_render(sb, show_duration: bool):
    # 给事件循环一个调度片刻
    await asyncio.sleep(0)
    render_story_tree(sb, show_duration=show_duration)


# ---------------- 渲染函数（同步） ----------------
def _fmt_time(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else ""


def _fmt_dur(start, end, show: bool) -> str:
    if not show or not start:
        return ""
    end = end or datetime.now().timestamp()
    dur = max(0.0, end - start)
    return f" ⏱ {int(dur * 1000)}ms" if dur < 3 else f" ⏱ {dur:.2f}s"


def _mark(status: str) -> str:
    return "✅" if status == "success" else ("💀" if status == "failed" else "⏳")


def render_story_tree(sb, *, show_duration: bool = True) -> None:
    # 1) 排序分组：moment -> attempts[]
    fps = sorted(sb.footprints, key=lambda f: f.started_at)
    if not fps:
        print("\n📘 Adventure:", getattr(sb, "title", "storybook"))
        print(" (no footprints)")
        return

    groups: List[Tuple[Footprint, List[Footprint]]] = []
    cur = None
    for fp in fps:
        if getattr(fp, "category", "moment") == "moment":
            if cur:
                groups.append(cur)
            cur = (fp, [])
        else:
            if cur is None:
                cur = (fp, [])
            else:
                cur[1].append(fp)
    if cur:
        groups.append(cur)

    print("\n📘 Adventure:", getattr(sb, "title", "storybook"))

    for gi, (mfp, attempts) in enumerate(groups):
        is_last_group = gi == len(groups) - 1
        m_joint = "┗━━" if is_last_group else "┣━━"
        print(
            f"{_fmt_time(mfp.started_at):<8}"
            f"{('→' + _fmt_time(getattr(mfp, 'finished_at', None))) if getattr(mfp, 'finished_at', None) else '':<10} "
            f"{m_joint} [M] {mfp.chapter} / {mfp.stage} {_mark(getattr(mfp, 'status', 'running'))}"
            f"{_fmt_dur(mfp.started_at, getattr(mfp, 'finished_at', None), show_duration)}"
        )
        for ai, afp in enumerate(attempts):
            is_last_attempt = ai == len(attempts) - 1
            a_joint = "┗━━" if is_last_attempt else "┣━━"
            trunk = "    " if is_last_group else "┃   "
            print(
                f"{_fmt_time(afp.started_at):<8}"
                f"{('→' + _fmt_time(getattr(afp, 'finished_at', None))) if getattr(afp, 'finished_at', None) else '':<10} "
                f"{trunk} {a_joint} [A#{getattr(afp, 'attempt', 0)}] {afp.chapter} / {afp.stage} {_mark(getattr(afp, 'status', 'running'))}"
                f"{_fmt_dur(getattr(afp, 'started_at', None), getattr(afp, 'finished_at', None), show_duration)}"
            )
