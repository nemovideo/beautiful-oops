from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional

from beautiful_oops.core.oops import OopsError


@dataclass
class StageInfo:
    chapter: str
    stage: str
    name: str | None = None


@dataclass
class MomentCtx:
    moment: "Moment"
    attempt: int = 0
    oops: Optional[OopsError] = None
    result: Any | None = None
    wait_seconds: float = 0.0
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    cancelled: bool = False


class Moment:
    def __init__(self, adv, stage: StageInfo, elf, fn):
        self.adv = adv
        self.stage = stage
        self.elf = elf
        self.fn = fn
        self.attempt = 0

    def next_attempt(self) -> MomentCtx:
        self.attempt += 1
        return MomentCtx(moment=self, attempt=self.attempt)
