import pytest

from beautiful_oops import Adventure
from beautiful_oops.core.moment import Moment, StageInfo
from beautiful_oops.core.elf import SimpleBackoffElf
from beautiful_oops.core.oops import OopsSolution


async def failing():
    raise ValueError("boom")


@pytest.mark.asyncio
async def test_retry_stops_at_limit():
    adv = Adventure()
    elf = SimpleBackoffElf(
        rules={Exception: OopsSolution.RETRY},
        default=OopsSolution.ABORT,
        retries=3,
    )
    st = StageInfo(chapter="C", stage="S")
    m = Moment(adv=adv, stage=st, elf=elf, fn=failing)

    await adv.start()
    with pytest.raises(Exception):
        await adv.enter_moment(m)
    await adv.end()
