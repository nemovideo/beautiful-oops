from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Type, Callable
import random

from .moment import MomentCtx
from .hero import Advice
from .oops import OopsSolution


class Elf:
    def advise(self, ctx: MomentCtx) -> Advice:
        return Advice(action=OopsSolution.ABORT)


@dataclass
class BackoffPolicy:
    base: float = 0.5
    factor: float = 2.0
    max_wait: float = 8.0
    jitter: float = 0.1

    def __call__(self, attempt: int) -> float:
        raw = min(self.base * (self.factor ** max(attempt - 1, 0)), self.max_wait)
        if self.jitter:
            span = raw * self.jitter
            raw += random.uniform(-span, span)
        return max(0.0, raw)


class SimpleBackoffElf(Elf):
    def __init__(
            self,
            rules: Optional[Dict[Type[BaseException], OopsSolution]] = None,
            default: OopsSolution = OopsSolution.ABORT,
            retries: int = 3,
            backoff: Optional[Callable[[int], float]] = None,
    ):
        self.rules = rules or {}
        self.default = default
        self.retries = retries
        self.backoff = backoff or BackoffPolicy()

    def _classify(self, ctx: MomentCtx) -> OopsSolution:
        if not ctx.oops:
            return self.default
        err = ctx.oops.cause
        for et, sol in self.rules.items():
            if isinstance(err, et):
                return sol
        return self.default

    def advise(self, ctx: MomentCtx) -> Advice:
        if ctx.attempt >= self.retries:
            final = self.default
            if final == OopsSolution.RETRY:
                final = OopsSolution.ABORT
            return Advice(action=final, wait_seconds=0.0, meta={"reason": "max_retries"})

        action = self._classify(ctx)
        if action == OopsSolution.RETRY:
            if ctx.attempt + 1 > self.retries:
                final = self.default
                if final == OopsSolution.RETRY:
                    final = OopsSolution.ABORT
                return Advice(action=final, wait_seconds=0.0, meta={"reason": "will_exceed_max"})
            wait = float(self.backoff(ctx.attempt))
            return Advice(action=OopsSolution.RETRY, wait_seconds=wait, meta={"policy": "expo"})
        return Advice(action=action, wait_seconds=0.0)
