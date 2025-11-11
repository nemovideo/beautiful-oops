from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional
from time import time, perf_counter
from ...core.oops import OopsError


@dataclass
class Footprint:
    chapter: str
    stage: str
    category: str = "moment"  # "moment" | "attempt"
    attempt: Optional[int] = None
    wall_started_at: float = field(default_factory=time)
    started_at: float = field(default_factory=perf_counter)
    wall_finished_at: Optional[float] = None
    finished_at: Optional[float] = None
    status: str = "running"  # "success" | "failed" | "running"
    note: Optional[str] = None


@dataclass
class Treasure:
    chapter: str
    stage: str
    value: Any
    at: float = field(default_factory=time)


@dataclass
class Tear:
    chapter: str
    stage: str
    error: str
    at: float = field(default_factory=time)


@dataclass
class StoryBook:
    title: str
    footprints: List[Footprint] = field(default_factory=list)
    tears: List[Tear] = field(default_factory=list)
    treasures: List[Treasure] = field(default_factory=list)

    def _open(self, chapter: str, stage: str, *, category: str, attempt: Optional[int] = None) -> Footprint:
        fp = Footprint(chapter=chapter, stage=stage, category=category, attempt=attempt)
        self.footprints.append(fp)
        return fp

    def _close_latest(self, chapter: str, stage: str, *, category: str, status: str, attempt: Optional[int] = None, note: Optional[str] = None) -> None:
        for fp in reversed(self.footprints):
            if fp.chapter == chapter and fp.stage == stage and fp.category == category and fp.status == "running":
                if attempt is None or fp.attempt == attempt:
                    fp.status = status
                    fp.wall_finished_at = time()
                    fp.finished_at = perf_counter()
                    if note:
                        fp.note = note
                    break

    def enter(self, chapter: str, stage: str) -> Footprint:
        return self._open(chapter, stage, category="moment")

    def success(self, chapter: str, stage: str, result: Any) -> None:
        self._close_latest(chapter, stage, category="moment", status="success")
        self.treasures.append(Treasure(chapter=chapter, stage=stage, value=result))

    def fail(self, chapter: str, stage: str, oops: OopsError) -> None:
        note = getattr(oops, "safe_message", str(oops))
        self._close_latest(chapter, stage, category="moment", status="failed", note=note)
        self.tears.append(Tear(chapter=chapter, stage=stage, error=note))

    def attempt_enter(self, chapter: str, stage: str, attempt: int) -> Footprint:
        return self._open(chapter, stage, category="attempt", attempt=attempt)

    def attempt_success(self, chapter: str, stage: str, attempt: int) -> None:
        self._close_latest(chapter, stage, category="attempt", status="success", attempt=attempt)

    def attempt_fail(self, chapter: str, stage: str, attempt: int, oops: Optional[OopsError] = None) -> None:
        note = getattr(oops, "safe_message", None) if oops else None
        self._close_latest(chapter, stage, category="attempt", status="failed", attempt=attempt, note=note)
