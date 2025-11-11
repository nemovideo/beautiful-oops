from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict

from .moment import MomentCtx
from .oops import OopsSolution


@dataclass
class Advice:
    action: OopsSolution
    wait_seconds: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    action: OopsSolution
    wait_seconds: float = 0.0


class Hero:
    def decide(self, *, ctx: MomentCtx, advice: Advice) -> Decision:
        return Decision(action=advice.action, wait_seconds=advice.wait_seconds)


class HeroFactory:
    @staticmethod
    def default() -> "Hero":
        return Hero()
