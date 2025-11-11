import pytest
from beautiful_oops import oops_moment, Adventure


@oops_moment(chapter="C1", stage="ok")
def ok_fn():
    return 42


@pytest.mark.asyncio
async def test_async_entry_decorator():
    res = await ok_fn()
    assert res == 42


def test_sync_entry_decorator():
    res = ok_fn()
    assert res == 42


@pytest.mark.asyncio
async def test_adventure_context_manager():
    adv = Adventure(name="ctx")
    await adv.start()
    try:
        @oops_moment(chapter="C2", stage="ok2")
        def ok2(): return "x"
        res = await ok2()
        assert res == "x"
    finally:
        await adv.end()
