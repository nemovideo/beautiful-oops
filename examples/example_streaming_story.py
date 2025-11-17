# example_streaming_story.py
from __future__ import annotations
import asyncio
import random
from typing import AsyncGenerator

from beautiful_oops import (
    oops_moment,
    Adventure,
    SimpleBackoffElf,
    OopsSolution,
    StorybookPlugin,
    StorybookConsoleSinkPlugin,
    TracingStackPlugin,
)


# ---------------------------------------------------------------------
# 1. Moments：每一步动作还是很“冒险”
# ---------------------------------------------------------------------


@oops_moment(chapter="Chapter I", stage="decode_scroll")
async def decode_scroll() -> str:
    """
    阅读一张古老卷轴。
    这里直接写成 async，方便在 async 流里统一 await。
    """
    # 如果你想模拟一点 IO，也可以加个 sleep：
    # await asyncio.sleep(0.05)
    return "The ruins remember those who dare to ask."


@oops_moment(
    chapter="Chapter II",
    stage="reflect_illusion",
    elf=SimpleBackoffElf(
        rules={ValueError: OopsSolution.RETRY},
        retries=3,
    ),
)
async def reflect_illusion(layer: int) -> str:
    """
    破除镜像幻象。
    - 有几率失败（抛 ValueError），交给 SimpleBackoffElf 自动重试；
    - 模拟异步 IO，用 sleep 表示“施法时间”。
    """
    await asyncio.sleep(random.uniform(0.2, 0.6))

    # 70% 概率失败，模拟“幻象太浓，看不清”
    if random.random() < 0.7:
        raise ValueError(f"Illusion fog on layer {layer}")

    return f"On layer {layer}, the mirror shows a hidden corridor."


@oops_moment(
    chapter="Chapter III",
    stage="cross_bridge",
    elf=SimpleBackoffElf(
        rules={RuntimeError: OopsSolution.RETRY},
        retries=2,
    ),
)
async def cross_bridge(index: int) -> str:
    """
    通过一座摇摇欲坠的石桥。
    有一定概率直接塌掉（抛 RuntimeError），Elf 会尝试重试几次。
    """
    await asyncio.sleep(random.uniform(0.3, 0.7))

    if random.random() < 0.5:
        raise RuntimeError(f"Bridge #{index} collapsed into the mist.")
    return f"Bridge #{index} holds. The party crosses safely."


@oops_moment(
    chapter="Chapter IV",
    stage="open_chest",
)
async def open_chest() -> str:
    """
    打开最终的宝箱，可能是宝物，也可能是……别的东西。
    """
    outcomes = [
        "A gentle light: an old relic that hums with forgotten magic.",
        "Dust only. Someone has been here long before you.",
        "A sleeping spirit opens one eye… and smiles.",
    ]
    # await asyncio.sleep(0.05)
    return random.choice(outcomes)


# ---------------------------------------------------------------------
# 2. Streaming 冒险：对外暴露 async generator
# ---------------------------------------------------------------------


async def stream_adventure(
        quest_name: str = "Echoes of the Fallen Ruins",
        illusion_layers: int = 3,
        bridges: int = 2,
) -> AsyncGenerator[str, None]:
    """
    一次完整的“地城长线冒险”，以 async generator 的形式暴露。
    """

    adv = Adventure(
        name=f"quest: {quest_name}",
        debug=True,
        plugins=[
            TracingStackPlugin(),
            StorybookPlugin(),
            StorybookConsoleSinkPlugin(),
        ],
    )

    async with Adventure.auto(adv):
        # 1) 读卷轴：任务开场
        intro = await decode_scroll()
        yield f"📜 A new quest begins: {quest_name}\n"
        yield f"📖 The scroll whispers: {intro}\n\n"

        # 2) 一层层破除幻象
        for layer in range(illusion_layers):
            layer_id = layer + 1
            try:
                yield f"🌫 Entering illusion layer {layer_id}...\n"
                vision = await reflect_illusion(layer_id)
                yield f"🔍 {vision}\n\n"
            except Exception as e:
                # 即使 Elf 已经重试过，最终还是失败，就在剧情里写出来
                yield f"❌ The illusion on layer {layer_id} refuses to break: {e!r}\n"
                yield "⚠️ The party decides not to force the magic and moves on.\n\n"

        # 3) 过几座桥
        for i in range(1, bridges + 1):
            try:
                yield f"🌉 Approaching stone bridge #{i}...\n"
                result = await cross_bridge(i)
                yield f"✅ {result}\n\n"
            except Exception as e:
                yield f"💀 Bridge #{i} fails beyond repair: {e!r}\n"
                yield "The party looks for another path along the cliff.\n\n"

        # 4) 最终宝箱
        yield "🧰 At the deepest chamber, a lonely chest awaits.\n"
        try:
            treasure = await open_chest()
            yield f"🎁 The chest reveals: {treasure}\n"
        except Exception as e:
            yield f"🧨 The chest reacts violently to your touch: {e!r}\n"

        yield "\n🏁 The adventure ends. The Storybook remembers every step.\n"


# ---------------------------------------------------------------------
# 3. Entrypoint：本地直接跑一下看效果
# ---------------------------------------------------------------------


async def _main():
    print("\n=== Streaming Dungeon Adventure ===\n")
    async for line in stream_adventure(
            quest_name="Echoes of the Fallen Ruins",
            illusion_layers=3,
            bridges=2,
    ):
        print(line, end="")  # line 已经自带换行

    print("\n=== Done. Check Storybook ASCII tree above. ===\n")


if __name__ == "__main__":
    asyncio.run(_main())
