# trace_id_generator.py
from __future__ import annotations

import threading
import time
from typing import Optional

# 64/32 位掩码，模拟 Java 无符号 long/int 行为
_U64 = (1 << 64) - 1
_U32 = (1 << 32) - 1


def _u64(x: int) -> int:
    return x & _U64


def _u32(x: int) -> int:
    return x & _U32


def _mix64(z: int) -> int:
    """
    MurmurHash3 fmix64 风格，按 Java 无符号 long 逐步掩码。
    """
    z = _u64(z)
    z ^= (z >> 33)
    z = _u64(z * 0xff51afd7ed558ccd)
    z ^= (z >> 33)
    z = _u64(z * 0xc4ceb9fe1a85ec53)
    z ^= (z >> 33)
    return _u64(z)


def _mix32(z: int) -> int:
    """
    MurmurHash3 fmix32 风格，按 Java 无符号 int 逐步掩码。
    """
    # 先把 64 位降到 32 位（对应 Java 中 (int)(z ^ (z >>> 32))）
    x = _u32(z ^ (z >> 32))
    x ^= (x >> 16)
    x = _u32(x * 0x7feb352d)
    x ^= (x >> 15)
    x = _u32(x * 0x846ca68b)
    x ^= (x >> 16)
    return _u32(x)


def _fixed_hex32(value: int) -> str:
    """把 32-bit 整数输出为固定 8 个十六进制字符（高位在前，左补零）。"""
    return f"{_u32(value):08x}"


def _hex_long(value: int) -> str:
    """把 64-bit 整数输出为 16 个十六进制字符（高位在前）。"""
    return f"{_u64(value):016x}"


class TraceIdGenerator:
    """
    生成 TraceId：
      1) 版本位: '1'
      2) 秒级时间戳（8位hex）
      3) 计数器混洗生成的 12 字节（24位hex）
    形如：1-<8hex秒>-<24hex随机>  总长度=35
    """
    _lock = threading.Lock()
    # 初始值：time_ns 左移一位 ^ 类对象地址（类似 identityHashCode）
    _counter: int = ((time.time_ns() << 1) ^ (id(object) & _U32)) & _U64

    @classmethod
    def _next_counter(cls) -> int:
        with cls._lock:
            c = cls._counter
            cls._counter = _u64(cls._counter + 1)
            return c

    @staticmethod
    def looks_valid(s: Optional[str]) -> bool:
        if not s or not s.strip():
            return False
        return len(s) <= 128

    @classmethod
    def new_trace_id(cls) -> str:
        # 版本
        parts = ["1", "-"]

        # 秒级时间戳（固定 8 位 hex）
        sec = int(time.time())
        parts.append(_fixed_hex32(sec))
        parts.append("-")

        # “随机”段：基于无锁原子计数器（这里用锁保证线程安全）做两次混洗 → 12 字节 = 24 hex
        c = cls._next_counter()
        r1 = _mix64(c)  # 前 8 字节 → 16 hex
        r2 = _mix32(c + 0x9E3779B9)  # 后 4 字节（黄金分割常数扰动）→ 8 hex

        parts.append(_hex_long(r1))
        parts.append(_fixed_hex32(r2))

        tid = "".join(parts)
        # 可选：断言长度为 35（1 + 1 + 8 + 1 + 24）
        # assert len(tid) == 35, len(tid)
        return tid

    @classmethod
    def new_span_id(cls) -> str:
        c = cls._next_counter()
        r = _mix32(c + 0x9E3779B9)  # 4 字节（黄金分割常数扰动）→ 8 hex
        return _fixed_hex32(r)


if __name__ == "__main__":
    t0 = time.time()
    print(TraceIdGenerator.new_trace_id())
    print(f"cost_ms={int((time.time() - t0) * 1000)}")
    print(TraceIdGenerator.new_span_id())
    print(f"cost_ms={int((time.time() - t0) * 1000)}")
