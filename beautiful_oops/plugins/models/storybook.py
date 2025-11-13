from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from time import time
import statistics


class NodeStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AttemptInfo:
    span_id: str
    attempt: int
    duration: float
    error: Optional[str] = None


@dataclass
class RunInfo:
    run_span: str  # 对应 moment 的 span_id
    attempts: List[AttemptInfo]  # 多个 attempt
    start_at: float
    end_at: float
    status: NodeStatus
    chapter: str  # ✅ 新增
    stage: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end_at - self.start_at)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def success(self) -> bool:
        return self.status == NodeStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status == NodeStatus.FAILED

    @property
    def cancelled(self) -> bool:
        return self.status == NodeStatus.CANCELLED


class StageGroup:
    """
    聚合同 chapter / stage 的所有 run（也就是 moment）
    """

    def __init__(self, chapter: str, stage: str):
        self.chapter = chapter
        self.stage = stage
        self.runs: List[RunInfo] = []

    # ---- 统计 ----
    @property
    def run_count(self) -> int:
        return len(self.runs)

    @property
    def success_count(self) -> int:
        return len([r for r in self.runs if r.success])

    @property
    def fail_count(self) -> int:
        return len([r for r in self.runs if r.failed])

    @property
    def cancel_count(self) -> int:  # ✅ 新增
        return len([r for r in self.runs if r.cancelled])

    @property
    def attempt_count(self) -> int:
        return sum(r.attempt_count for r in self.runs)

    def latency_stats(self) -> Tuple[float, float]:
        """返回 p50, p95"""
        if not self.runs:
            return 0.0, 0.0
        durations = [r.duration for r in self.runs]
        p50 = statistics.median(durations)
        # p95 简单取 95 百分位
        durations_sorted = sorted(durations)
        p95 = durations_sorted[int(0.95 * (len(durations_sorted) - 1))]
        return p50, p95

    # ---- 渲染 ----
    def render_ascii(
            self,
            limit: int = 3,
            show_attempt_spans: bool = True,
            attempt_span_limit: int = 3,
            child_prefix: str = "┃   ",  # ⭐ 前缀从 StoryBook 注入
    ) -> str:
        if not self.runs:
            return ""

        p50, p95 = self.latency_stats()

        head = (
            f"┣━━ {self.chapter}/{self.stage}  "
            f"runs={self.run_count}  "
            f"✅{self.success_count} 💀{self.fail_count} 🚫{self.cancel_count}  "
            f"attempts={self.attempt_count}  "
            f"⏱p50={p50:.2f}s p95={p95:.2f}s"
        )

        lines = [head]

        display_runs = self.runs[-limit:]

        for i, run in enumerate(display_runs):
            is_last = (i == len(self.runs) - 1)
            connector = "┗━━" if is_last else "┣━━"

            if run.success:
                mark = "✅"
            elif run.cancelled:
                mark = "🚫"
            else:
                mark = "💀"

            run_line = (
                f"{child_prefix}{connector} [span:{run.run_span}] "
                f"{mark}  "
                f"⏱ {run.duration:.2f}s"
            )

            # attempts
            if show_attempt_spans:
                parts = []
                for att in run.attempts[:attempt_span_limit]:
                    if att.error:
                        parts.append(f"A#{att.attempt}={att.duration:.2f}s, err={att.error}")
                    else:
                        parts.append(f"A#{att.attempt}={att.duration:.2f}s")

                if len(run.attempts) > attempt_span_limit:
                    parts.append("...")

                if parts:
                    run_line += f"  ({', '.join(parts)})"

            lines.append(run_line)

        # more
        if len(self.runs) > limit:
            more = f"{child_prefix}┗━━ … and {len(self.runs) - limit} more"
            lines.append(more)

        return "\n".join(lines)


# ================================================================
# StoryBook：外部插件调用的主收集器
# ================================================================
class StoryBook:

    def __init__(self, title: str):
        self.title = title
        # {(chapter,stage): StageGroup}
        self.groups: Dict[Tuple[str, str], StageGroup] = {}

        # moment_id => RunInfo（未关闭状态）
        self._active_moments: Dict[str, RunInfo] = {}

    # ---- moment / attempt 记录 ----
    def moment_enter(self, run_id: str, chapter: str, stage: str, span_id: str):
        key = (chapter, stage)
        if key not in self.groups:
            self.groups[key] = StageGroup(chapter, stage)

        self._active_moments[run_id] = RunInfo(
            run_span=span_id,
            attempts=[],
            start_at=time(),
            end_at=time(),
            status=NodeStatus.RUNNING,
            chapter=chapter,
            stage=stage,
        )

    def moment_cancel(self, run_id: str, chapter: str, stage: str):
        """
        标记某个 moment 的 run 被取消（例如 asyncio.CancelledError）；
        通常在插件收到 MomentEvent.CANCEL 时调用。
        """
        ri = self._active_moments.get(run_id)
        if not ri:
            return
        ri.end_at = time()
        ri.status = NodeStatus.CANCELLED
        self.groups[(chapter, stage)].runs.append(ri)
        del self._active_moments[run_id]

    def attempt_enter(self, run_id: str, span_id: str, attempt: int):
        ri = self._active_moments.get(run_id)
        if not ri:
            return
        ri.attempts.append(
            AttemptInfo(
                span_id=span_id,
                attempt=attempt,
                duration=0.0,
            )
        )

    def attempt_end(self, run_id: str, span_id: str, attempt: int, duration: float, error: Optional[str] = None):
        ri = self._active_moments.get(run_id)
        if not ri:
            return
        # 更新 attempt 信息
        if ri.attempts:
            ri.attempts[-1].duration = duration
            ri.attempts[-1].error = error

    def moment_end(self, run_id: str, chapter: str, stage: str, success: bool):
        ri = self._active_moments.get(run_id)
        if not ri:
            return
        ri.end_at = time()
        ri.status = NodeStatus.SUCCESS if success else NodeStatus.FAILED
        self.groups[(chapter, stage)].runs.append(ri)
        del self._active_moments[run_id]

    # ---- 分组排序 ----
    def sorted_groups(self, sort: str = "order") -> List[StageGroup]:
        return list(self.groups.values())

    # ---- 渲染 ----
    def render_ascii(
            self,
            limit_per_stage: int = 3,
            sort: str = "order",
            show_attempt_spans: bool = True,
            attempt_span_limit: int = 3,
    ) -> str:
        self._auto_close_active_as_cancelled()

        lines = [f"📘 Adventure: {self.title}"]
        groups = self.sorted_groups(sort=sort)

        for i, g in enumerate(groups):
            is_last_group = (i == len(groups) - 1)

            # ⭐ 非最后一个 group：children 用 |> "┃   "
            # ⭐ 最后一个 group：children 用空格 "    "
            child_prefix = "    " if is_last_group else "┃   "

            block = g.render_ascii(
                limit=limit_per_stage,
                show_attempt_spans=show_attempt_spans,
                attempt_span_limit=attempt_span_limit,
                child_prefix=child_prefix,
            )

            # 换掉头的 connector
            if is_last_group:
                block = block.replace("┣━━", "┗━━", 1)

            lines.append(block)

        return "\n".join(lines)

    def _auto_close_active_as_cancelled(self):
        now = time()
        for run_id, ri in list(self._active_moments.items()):
            if ri.status == NodeStatus.RUNNING:
                ri.end_at = now
                ri.status = NodeStatus.CANCELLED
                key = (ri.chapter, ri.stage)
                if key not in self.groups:
                    self.groups[key] = StageGroup(ri.chapter, ri.stage)
                self.groups[key].runs.append(ri)
            # 不管是不是 RUNNING，一律从 active 里删掉，避免重复
            del self._active_moments[run_id]
