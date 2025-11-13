# example_concurrent_adventure.py
from __future__ import annotations
import asyncio
import random

from beautiful_oops import (
    oops_moment,
    Adventure,
    SimpleBackoffElf,
    OopsSolution,
    StorybookPlugin,
    StorybookConsoleSinkPlugin,
    TracingStackPlugin,
)


# --- Moments -----------------------------------------------------------

@oops_moment(chapter="I", stage="decode_scroll")
def decode_scroll():
    """总是成功的同步 moment"""
    return "ancient wisdom"


@oops_moment(
    chapter="II",
    stage="reflect_illusion",
    elf=SimpleBackoffElf(rules={ValueError: OopsSolution.RETRY}, retries=3),
)
async def reflect_illusion(i: int):
    """
    70% 概率抛错，剩下成功
    模拟异步 IO（真实应用中可能是 HTTP 请求）
    """
    await asyncio.sleep(random.uniform(0.2, 0.6))
    if random.random() < 0.7:
        raise ValueError(f"fog #{i}")
    return f"clear vision #{i}"


@oops_moment(
    chapter="III",
    stage="cross_bridge",
    elf=SimpleBackoffElf(rules={RuntimeError: OopsSolution.RETRY}, retries=3),
)
async def cross_bridge(i: int):
    """永远失败，模拟 fatal 错误"""
    await asyncio.sleep(random.uniform(0.3, 0.5))
    raise RuntimeError(f"bridge collapsed #{i}")


# --- Adventure Runner ---------------------------------------------------

async def run_concurrent():
    """
    同时执行多个 moment，gather 首个失败会 cancel 其他任务
    但每个 moment 都能被 StoryBook 正确记录（success / fail / cancelled）
    """

    # 创建 Adventure（开启 trace + stack tracking）
    adv = Adventure(
        name="concurrent-adventure",
        debug=True,
        plugins=[
            TracingStackPlugin(),         # 负责 span_id / parent_span_id（可视化 DAG）
            StorybookPlugin(),            # 记录所有 moment/attempt
            StorybookConsoleSinkPlugin(), # 打印 ASCII trace tree
        ],
    )

    async with Adventure.auto(adv):

        # 构造 10 个并发任务：
        tasks = []
        for i in range(10):
            tasks.append(decode_scroll())           # 同步 moment 会自动异步包装
            tasks.append(reflect_illusion(i))
            tasks.append(cross_bridge(i))           # 会导致 gather cancel

        try:
            # 任何一个任务失败都会让 gather 抛异常 -> 触发 cancel 其它
            await asyncio.gather(*tasks)
        except Exception as e:
            print(f"\n⚠️  gather failed due to: {e!r}\n")


# --- Entrypoint ---------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_concurrent())
