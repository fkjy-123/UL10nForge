"""本地 GGUF 推理显存预估：模型权重 + KV cache + 计算缓冲。

KV cache 是「并发槽位 × 上下文」的显存主力 —— 槽位翻倍显存翻倍，
这正是把默认并发压到 1 的原因。设置页高级设置据此实时展示调节效果。
"""
from __future__ import annotations

import os
import re
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

# 计算缓冲（graph 内存 / mmq 工作区 / CUDA 上下文）经验占用
_COMPUTE_BUFFER_GB = 1.0


def read_gguf_metadata(path: str | Path) -> dict:
    """读取 GGUF v2/v3 元数据为扁平 dict（数值/字符串/数组值）。

    只读文件头（1MiB 足够覆盖全部 metadata KV）——GGUF 权重区从头部
    之后才开始，全文件 read_bytes 对大模型（1GB+）白白读入内存。
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read(1 << 20)
    except OSError:
        return {}
    if raw[:4] != b"GGUF" or len(raw) < 24:
        return {}
    version = struct.unpack_from("<I", raw, 4)[0]
    if version not in (2, 3):
        return {}
    _tensor_count, metadata_count = struct.unpack_from("<QQ", raw, 8)
    offset = 24
    meta: dict = {}
    try:
        for _ in range(metadata_count):
            key_len = struct.unpack_from("<Q", raw, offset)[0]
            offset += 8
            key = raw[offset:offset + key_len].decode("utf-8", "replace")
            offset += key_len
            value, consumed = _read_gguf_value(raw, offset)
            offset += consumed
            meta[key] = value
    except struct.error:
        return {}
    return meta


def _read_gguf_value(raw: bytes, offset: int) -> tuple:
    """读取一个带类型标签的 GGUF 值，返回 (value, bytes_consumed)。"""
    start = offset                       # consumed 含类型标签本身
    kind = struct.unpack_from("<I", raw, offset)[0]
    offset += 4
    if kind == 0:
        return struct.unpack_from("<B", raw, offset)[0], 5
    if kind == 1:
        return struct.unpack_from("<b", raw, offset)[0], 5
    if kind == 2:
        return struct.unpack_from("<H", raw, offset)[0], 6
    if kind == 3:
        return struct.unpack_from("<h", raw, offset)[0], 6
    if kind == 4:
        return struct.unpack_from("<I", raw, offset)[0], 8
    if kind == 5:
        return struct.unpack_from("<i", raw, offset)[0], 8
    if kind == 6:
        return struct.unpack_from("<f", raw, offset)[0], 8
    if kind == 7:
        return bool(struct.unpack_from("<B", raw, offset)[0]), 5
    if kind == 8:
        size = struct.unpack_from("<Q", raw, offset)[0]
        return raw[offset + 8:offset + 8 + size].decode(
            "utf-8", "replace"), 12 + size
    if kind == 9:  # array（元素无类型标签，均同 kind）
        item_kind = struct.unpack_from("<I", raw, offset)[0]
        offset += 4
        count = struct.unpack_from("<Q", raw, offset)[0]
        offset += 8
        items: list = []
        for _ in range(count):
            item, consumed = _read_gguf_value_at_kind(raw, offset, item_kind)
            offset += consumed
            items.append(item)
        return items, offset - start
    if kind == 10:
        return struct.unpack_from("<Q", raw, offset)[0], 12
    if kind == 11:
        return struct.unpack_from("<q", raw, offset)[0], 12
    if kind == 12:
        return struct.unpack_from("<d", raw, offset)[0], 12
    raise struct.error(f"unknown gguf kind {kind}")


def _read_gguf_value_at_kind(raw: bytes, offset: int, kind: int) -> tuple:
    """读取数组元素（无类型标签）。"""
    if kind == 0:
        return struct.unpack_from("<B", raw, offset)[0], 1
    if kind == 1:
        return struct.unpack_from("<b", raw, offset)[0], 1
    if kind == 2:
        return struct.unpack_from("<H", raw, offset)[0], 2
    if kind == 3:
        return struct.unpack_from("<h", raw, offset)[0], 2
    if kind == 4:
        return struct.unpack_from("<I", raw, offset)[0], 4
    if kind == 5:
        return struct.unpack_from("<i", raw, offset)[0], 4
    if kind == 6:
        return struct.unpack_from("<f", raw, offset)[0], 4
    if kind == 7:
        return bool(struct.unpack_from("<B", raw, offset)[0]), 1
    if kind == 8:
        size = struct.unpack_from("<Q", raw, offset)[0]
        return raw[offset + 8:offset + 8 + size].decode(
            "utf-8", "replace"), 8 + size
    if kind == 10:
        return struct.unpack_from("<Q", raw, offset)[0], 8
    if kind == 11:
        return struct.unpack_from("<q", raw, offset)[0], 8
    if kind == 12:
        return struct.unpack_from("<d", raw, offset)[0], 8
    raise struct.error(f"unknown gguf array kind {kind}")


@dataclass(frozen=True)
class VramEstimate:
    model_gb: float          # 模型权重（≈ GGUF 文件大小）
    kv_gb: float             # KV cache 总量（槽位 × 每槽）
    kv_per_slot_gb: float
    compute_gb: float        # 计算缓冲经验值
    total_gb: float
    layers: int = 0          # transformer 层数（GGUF block_count；部分
                             # 卸载按层分摊权重用，几何未知为 0）

    def __bool__(self) -> bool:
        return self.total_gb > 0


def estimate_vram(model_path: str | Path, *, context_size: int = 4096,
                  slots: int = 1) -> VramEstimate:
    """预估 GPU 显存占用（GiB）。几何未知时 KV 按 0 计，权重仍给出。"""
    meta = read_gguf_metadata(model_path)
    archs = ("llama", "gptneox", "qwen2", "hunyuan-dense")

    def first(*keys: str) -> object:
        return next((meta[k] for k in keys if k in meta), None)

    layers = int(first(*(f"{a}.block_count" for a in archs)) or 0)
    heads = int(first(*(f"{a}.attention.head_count" for a in archs)) or 0)
    kv_heads = int(first(*(f"{a}.attention.head_count_kv" for a in archs))
                   or heads)
    # embedding_length 前缀不统一（llama/qwen2 带 attention.，hunyuan 不带）
    dim = int(first(*(f"{a}.attention.embedding_length" for a in archs),
                    *(f"{a}.embedding_length" for a in archs)) or 0)
    head_dim = dim // heads if heads else 0
    # fp16 KV：K 与 V 各 2 字节 → 每 token 每层 2×2×kv_heads×head_dim
    kv_per_slot = 4 * layers * kv_heads * head_dim * max(0, int(context_size))
    try:
        model_gb = Path(model_path).stat().st_size / 2**30
    except OSError:
        model_gb = 0.0
    kv_gb = kv_per_slot * max(1, slots) / 2**30
    compute_gb = _COMPUTE_BUFFER_GB
    return VramEstimate(
        model_gb=model_gb, kv_gb=kv_gb,
        kv_per_slot_gb=kv_per_slot / 2**30, compute_gb=compute_gb,
        total_gb=model_gb + kv_gb + compute_gb, layers=layers,
    )


def gpu_memory_info() -> tuple[float, float] | None:
    """返回 (total_gb, free_gb)；nvidia-smi 不可用时返回 None。"""
    # 弹窗根因（2026-08-13 用户实证：语义审核期间终端窗口反复闪出又
    # 消失几十次）——nvidia-smi 探测缺 CREATE_NO_WINDOW，GUI 进程每次
    # probe_hardware（送审 ensure_running 每轮都探测）都闪控制台窗口。
    # 与 #14 netstat/taskkill 同类缺陷，对齐补标志（行为不变）。
    nowindow = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if os.name == "nt" else 0)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=False,
            creationflags=nowindow,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    parts = re.split(r"[,\s]+", result.stdout.strip())
    if len(parts) < 2:
        return None
    try:
        return float(parts[0]) / 1024, float(parts[1]) / 1024
    except ValueError:
        return None
