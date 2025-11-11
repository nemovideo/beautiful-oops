from __future__ import annotations
import asyncio
from functools import wraps
from typing import Optional, Callable, Any, Literal

from .core.moment import StageInfo, Moment
from .core.adventure import Adventure, get_pool, register_adventure, remove_adventure
from .core.elf import Elf


def oops_moment_auto(
    *,
    chapter: str,
    stage: Optional[str] = None,
    name: Optional[str] = None,
    elf: Optional[Elf] = None,
    mode: Literal["auto", "async", "sync"] = "auto",
):
    def deco(fn: Callable[..., Any]):
        async def _async_call(*args, **kwargs):
            pool = get_pool()
            created = False
            if pool:
                adv = pool[0]
            else:
                adv = Adventure(name="auto")
                register_adventure(adv)
                created = True
                await adv.start()

            st = StageInfo(chapter=chapter, stage=stage or fn.__name__, name=name or fn.__name__)
            m = Moment(adv=adv, stage=st, elf=elf or Elf(), fn=lambda: fn(*args, **kwargs))
            try:
                return await adv.enter_moment(m)
            finally:
                if created:
                    try:
                        await adv.end()
                    finally:
                        remove_adventure(adv)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if mode == "async":
                return _async_call(*args, **kwargs)
            if mode == "sync":
                try:
                    asyncio.get_running_loop()
                    raise RuntimeError("mode='sync' cannot run inside an active event loop; use mode='async' and await.")
                except RuntimeError:
                    pass
                return asyncio.run(_async_call(*args, **kwargs))
            # auto
            try:
                asyncio.get_running_loop()
                return _async_call(*args, **kwargs)
            except RuntimeError:
                return asyncio.run(_async_call(*args, **kwargs))

        return wrapper
    return deco

oops_moment = oops_moment_auto
