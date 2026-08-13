from __future__ import annotations

import struct

from hanhua.core.vram import (estimate_vram, gpu_memory_info,
                              read_gguf_metadata)


def _write_gguf(path, meta: dict) -> None:
    """构造最小 GGUF v3 文件（0 tensor，带给定 metadata）。"""
    buf = bytearray(b"GGUF")
    buf += struct.pack("<I", 3)
    buf += struct.pack("<Q", 0)               # tensor_count
    buf += struct.pack("<Q", len(meta))
    for key, value in meta.items():
        key_bytes = key.encode("utf-8")
        buf += struct.pack("<Q", len(key_bytes))
        buf += key_bytes
        if isinstance(value, bool):
            buf += struct.pack("<IB", 7, int(value))
        elif isinstance(value, int):
            buf += struct.pack("<IQ", 11, value)
        elif isinstance(value, float):
            buf += struct.pack("<If", 6, value)
        elif isinstance(value, str):
            raw = value.encode("utf-8")
            buf += struct.pack("<IQ", 8, len(raw))
            buf += raw
        elif isinstance(value, list):
            # 字符串数组（GGUF array kind 9，元素同为 kind 8）
            buf += struct.pack("<IIQ", 9, 8, len(value))
            for item in value:
                raw = str(item).encode("utf-8")
                buf += struct.pack("<Q", len(raw))
                buf += raw
        else:
            raise ValueError(f"unsupported value: {value!r}")
    path.write_bytes(bytes(buf))


def test_read_gguf_metadata_extracts_model_geometry(tmp_path):
    model = tmp_path / "model.gguf"
    _write_gguf(model, {
        "general.architecture": "llama",
        "llama.block_count": 24,
        "llama.attention.head_count": 16,
        "llama.attention.head_count_kv": 8,
        "llama.attention.embedding_length": 1536,
        "llama.attention.layer_norm_rms_epsilon": 1e-5,
    })

    meta = read_gguf_metadata(model)

    assert meta["general.architecture"] == "llama"
    assert meta["llama.block_count"] == 24
    assert meta["llama.attention.head_count_kv"] == 8
    assert meta["llama.attention.embedding_length"] == 1536
    assert abs(meta["llama.attention.layer_norm_rms_epsilon"] - 1e-5) < 1e-9


def test_read_gguf_metadata_rejects_truncated_file(tmp_path):
    bad = tmp_path / "bad.gguf"
    bad.write_bytes(b"GGUF\x03\x00\x00\x00")     # 头未完成
    assert read_gguf_metadata(bad) == {}


def test_estimate_vram_scales_kv_with_slots_and_context(tmp_path):
    model = tmp_path / "model.gguf"
    # 1.8B 结构：24 层、8 KV 头、16 Q 头、dim 1536 → head_dim 96
    meta = {
        "llama.block_count": 24,
        "llama.attention.head_count": 16,
        "llama.attention.head_count_kv": 8,
        "llama.attention.embedding_length": 1536,
    }
    _write_gguf(model, meta)
    with model.open("ab") as stream:
        stream.write(b"\x00" * (1500 * 1024 * 1024))    # 1.5 GiB 权重占位

    single = estimate_vram(model, context_size=4096, slots=1)
    four = estimate_vram(model, context_size=4096, slots=4)
    half_ctx = estimate_vram(model, context_size=2048, slots=1)

    # KV per slot（fp16）: 4B × layers × kv_heads × head_dim × ctx
    kv_slot = 4 * 24 * 8 * 96 * 4096
    assert single.kv_per_slot_gb == kv_slot / 2**30
    assert single.kv_gb == single.kv_per_slot_gb
    assert four.kv_gb == single.kv_per_slot_gb * 4
    assert half_ctx.kv_per_slot_gb == single.kv_per_slot_gb / 2
    assert single.model_gb > 1.0
    assert single.total_gb == single.model_gb + single.kv_gb + single.compute_gb


def test_estimate_vram_falls_back_when_geometry_unknown(tmp_path):
    model = tmp_path / "plain.gguf"
    model.write_bytes(b"\x00" * (2 * 1024 * 1024))
    _write_gguf(model, {"general.architecture": "llama"})

    est = estimate_vram(model, context_size=4096, slots=1)

    assert est.kv_gb == 0.0          # 几何未知 → KV 无法估算，模型权重仍给出
    assert est.model_gb > 0


def test_read_gguf_metadata_keeps_parsing_after_array_values(tmp_path):
    """数组值（如 tokenizer.ggml.tokens）之后的键必须继续正确解析。"""
    model = tmp_path / "array.gguf"
    _write_gguf(model, {
        "general.architecture": "hunyuan-dense",
        "tokenizer.ggml.tokens": [f"tok-{i}" for i in range(300)],
        "hunyuan-dense.block_count": 32,
        "tokenizer.ggml.merges": ["a b", "c d"],
    })

    meta = read_gguf_metadata(model)

    assert meta["general.architecture"] == "hunyuan-dense"
    assert meta["tokenizer.ggml.tokens"][0] == "tok-0"
    assert meta["tokenizer.ggml.tokens"][299] == "tok-299"
    assert meta["hunyuan-dense.block_count"] == 32      # 数组之后的键
    assert meta["tokenizer.ggml.merges"] == ["a b", "c d"]  # 数组之后的数组


def test_estimate_vram_reads_hunyuan_dense_geometry(tmp_path):
    """真实模型（Hy-MT2）为 hunyuan-dense 架构，KV 必须按该前缀估算。
    embedding_length 不带 attention. 前缀（与 llama/qwen2 不同）。"""
    model = tmp_path / "hy.gguf"
    _write_gguf(model, {
        "hunyuan-dense.block_count": 32,
        "hunyuan-dense.attention.head_count": 16,
        "hunyuan-dense.attention.head_count_kv": 4,
        "hunyuan-dense.embedding_length": 2048,
    })

    est = estimate_vram(model, context_size=4096, slots=4)

    # head_dim = 2048 / 16 = 128 → kv/slot = 4×32×4×128×4096 = 2^28 B = 0.25 GiB
    assert est.kv_per_slot_gb == 2**28 / 2**30
    assert est.kv_gb == 2**28 / 2**30 * 4
    assert est.total_gb == est.model_gb + est.kv_gb + est.compute_gb


def test_gpu_memory_info_returns_none_without_nvidia_smi(monkeypatch):
    import subprocess

    def fake_run(_cmd, **_kwargs):
        raise FileNotFoundError("nvidia-smi not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gpu_memory_info() is None


def test_gpu_memory_info_suppresses_console_window(monkeypatch):
    """#18 回归：nvidia-smi 探测必须带 CREATE_NO_WINDOW（2026-08-13
    实证：审核期间终端窗口反复闪出又消失几十次）。"""
    import os
    import subprocess

    if os.name != "nt":
        monkeypatch.setattr(os, "name", "nt")
    calls = {}

    def fake_run(cmd, **kwargs):
        calls.update(kwargs)
        return type("Result", (), {"returncode": 1, "stdout": ""})()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gpu_memory_info() is None
    assert calls["creationflags"] == getattr(
        subprocess, "CREATE_NO_WINDOW", 0)
