import random

from beautiful_oops import (
    oops_moment, Adventure, SimpleBackoffElf, OopsSolution,
    StorybookPlugin, StorybookConsoleSinkPlugin, TracingStackPlugin
)


@oops_moment(chapter="Chapter I", stage="decode_scroll")
def decode_scroll():
    return "ancient wisdom"


@oops_moment(chapter="Chapter II", stage="reflect_illusion",
             elf=SimpleBackoffElf(rules={ValueError: OopsSolution.RETRY}))
def reflect_illusion():
    if random.random() < 0.7:
        raise ValueError("mirror fog")
    return "clear vision"


@oops_moment(chapter="Chapter III", stage="cross_bridge",
             elf=SimpleBackoffElf(rules={TypeError: OopsSolution.RETRY}))
def cross_bridge():
    raise TypeError("bridge vanished")


if __name__ == "__main__":
    adv = Adventure(
        name="my first adventure",
        plugins=[
            TracingStackPlugin(),
            StorybookPlugin(),
            StorybookConsoleSinkPlugin(),
        ],
        debug=True,
    )
    with Adventure.auto(adv):
        for i in range(5):
            try:
                print("Scroll:", decode_scroll())
                print("Mirror:", reflect_illusion())
                print("Bridge:", cross_bridge())
            except Exception as e:
                print("Adventure ended with:", e)
