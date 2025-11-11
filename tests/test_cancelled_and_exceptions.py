import pytest
import asyncio

from beautiful_oops import Adventure
from beautiful_oops.core.moment import Moment, StageInfo
from beautiful_oops.core.elf import SimpleBackoffElf
from beautiful_oops.core.oops import OopsSolution


@pytest.mark.asyncio
async def test_cancelled_error_propagates():
    async def canceller():
        raise asyncio.CancelledError()

    adv = Adventure()
    elf = SimpleBackoffElf(rules={Exception: OopsSolution.RETRY}, retries=2)
    m = Moment(adv=adv, stage=StageInfo("C", "S"), elf=elf, fn=canceller)

    await adv.start()
    with pytest.raises(asyncio.CancelledError):
        await adv.enter_moment(m)
    await adv.end()
