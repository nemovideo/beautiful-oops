import random
from beautiful_oops import (
    oops_moment, Adventure, SimpleBackoffElf, OopsSolution,
    StorybookPlugin, StorybookConsoleSinkPlugin
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
            StorybookPlugin(),
            StorybookConsoleSinkPlugin(  # 同步/异步开关按需设定
                background=False,  # 同步脚本/单测建议 False，确保不会丢日志
                show_duration=True,
                only_when=lambda a: True
            ),
        ],
        debug=True,
    )
    with Adventure.auto(adv):
        try:
            print("Scroll:", decode_scroll())
            print("Mirror:", reflect_illusion())
            print("Bridge:", cross_bridge())
        except Exception as e:
            print("Adventure ended with:", e)
