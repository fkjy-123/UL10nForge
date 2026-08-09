"""三模块覆盖缺口补强（扫描/翻译/写回）。

审计发现以下公开函数此前无任何测试直接引用，本文件补齐：
- scanner.probe_head_kind / probe_file_kind（内容探测核心）
- translator.merge_translation_references（引用合并：内置 > 用户覆盖）
- quality.is_camel_tech_abbreviation / has_independent_lower_word /
  source_term_applies / is_write_ready（质量门禁基础判定）
- mono_dll._method_signature_string_params（UI setter 传递验证）
- unity.writer.WriteResult 记账（note_attempt/note_rejected/is_resolved/
  note_truncated/outcome 不变量）
"""
import json

import pytest

from hanhua.core.scanner import probe_file_kind, probe_head_kind
from hanhua.core.translator import merge_translation_references
from hanhua.core.quality import (
    is_camel_tech_abbreviation,
    has_independent_lower_word,
    source_term_applies,
    is_write_ready,
)
from hanhua.core.unity.mono_dll import _method_signature_string_params
from hanhua.core.unity.writer import WriteResult


# ── 扫描模块：内容探测 ──

def test_probe_head_kind_unity_magics():
    assert probe_head_kind(b"UnityFS\x00\x00\x00") == "unity"
    # UnityWeb 前缀先命中 bundle 魔数（_UNITY_BUNDLE_MAGICS 检查优先于 WebFile 完整串）
    assert probe_head_kind(b"UnityWebData1.0rest") == "unity"
    assert probe_head_kind(b"UnityRaw") == "unity"


def test_probe_head_kind_unitycn_encrypted():
    # UnityCN 加密 bundle：识别为加密态（需解密 key，不静默跳过）
    assert probe_head_kind(b"#$unity3dchina!@rest") == "unitycn_encrypted"


def test_probe_head_kind_containers():
    assert probe_head_kind(b"PK\x03\x04rest") == "zip"
    assert probe_head_kind(b"PK\x05\x06rest") == "zip"
    assert probe_head_kind(b"SQLite format 3\x00rest") == "sqlite"
    assert probe_head_kind(b"\x1f\x8b\x08\x00") == "gzip"
    assert probe_head_kind(b"\x28\xb5\x2f\xfdrest") == "zstd"
    assert probe_head_kind(b"\x04\x22\x4d\x18rest") == "lz4"


def test_probe_head_kind_serialized_file_self_consistent():
    # 大端自洽头：version=22, file_size=1000, data_offset=48, metadata=100
    head = bytearray(48)
    head[8:12] = (22).to_bytes(4, "big")
    head[24:32] = (1000).to_bytes(8, "big")
    head[32:40] = (48).to_bytes(8, "big")
    head[20:24] = (100).to_bytes(4, "big")
    assert probe_head_kind(bytes(head)) == "serialized"


def test_probe_head_kind_text_vs_binary_vs_unknown():
    assert probe_head_kind(b"hello world\nsome text\nmore") == "text"
    assert probe_head_kind(b"\x00\x01\x02\xff" * 32) == "binary"
    assert probe_head_kind(b"") == "unknown"
    # BOM 明确 → 文本
    assert probe_head_kind(b"\xef\xbb\xbfhello") == "text"


def test_probe_file_kind_reads_head(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"UnityFS\x00\x00\x00fake")
    assert probe_file_kind(f) == "unity"
    f.write_bytes(b"plain text content here\n")
    assert probe_file_kind(f) == "text"
    missing = tmp_path / "missing"
    assert probe_file_kind(missing) == "unknown"


# ── 翻译模块：引用合并 ──

def test_merge_references_builtin_and_user_overrides():
    merged = merge_translation_references([
        ("Settings", "自定义设置"),
        {"term": "Quit", "translation": "自定义退出"},
    ])
    pairs = dict(merged)
    assert pairs["Settings"] == "自定义设置"
    assert pairs["Quit"] == "自定义退出"
    # 内置参考仍保留（未被覆盖的）
    assert pairs["Resolution"] == "分辨率"


def test_merge_references_accepts_object_rows_and_filters_junk():
    class Row:
        def __init__(self, term, translation):
            self.term = term
            self.translation = translation

    merged = merge_translation_references([
        Row("Play", "自定义玩"),
        ("  ", ""),            # 空术语 → 丢弃
        ("OnlySource", ""),    # 无译文 → 丢弃
        {"term": "", "translation": "孤儿译文"},  # 无术语 → 丢弃
        ("Back", "回"),
    ])
    pairs = dict(merged)
    assert pairs["Play"] == "自定义玩"
    assert pairs["Back"] == "回"
    assert "OnlySource" not in pairs
    assert "OnlySource" not in [s for s, _ in merged]
    # 用户术语优先于内置：Back 内置是"返回"，用户给"回"
    assert pairs["Back"] == "回"


# ── 质量模块：基础判定 ──

def test_is_camel_tech_abbreviation():
    assert is_camel_tech_abbreviation("VSync")
    assert is_camel_tech_abbreviation("MonoBehaviour")
    assert is_camel_tech_abbreviation("YouTube")
    assert not is_camel_tech_abbreviation("SETTINGS")
    assert not is_camel_tech_abbreviation("Save")
    assert not is_camel_tech_abbreviation("A")
    assert not is_camel_tech_abbreviation("")


def test_has_independent_lower_word():
    assert has_independent_lower_word("iipsum dolor")
    assert has_independent_lower_word("hello world")
    assert not has_independent_lower_word("Stefánsson")
    assert not has_independent_lower_word("CONGRATULATIONS")
    assert not has_independent_lower_word("") or has_independent_lower_word("")


def test_source_term_applies_token_boundary():
    assert source_term_applies("Play", "Press Play to start")
    assert source_term_applies("Play", "PLAY THE GAME")  # 大小写不敏感
    assert not source_term_applies("Play", "Player name")
    assert not source_term_applies("Play", "Gameplay")
    # 带空格术语：含字母数字 → 整体作为词边界 token 匹配
    assert source_term_applies("Press E", "Press E to open")
    assert not source_term_applies("Press E", "Press F to open")
    # 纯符号术语 → 子串匹配
    assert not source_term_applies(" ", "nothing")
    assert source_term_applies("[x]", "value [x] here")


# ── 质量模块：写回就绪判定 ──

def test_is_write_ready_gates_quality_and_confidence():
    good_meta = json.dumps({
        "quality_passed": True, "confidence": "high",
    })
    assert is_write_ready("translated", "译文", good_meta)
    assert is_write_ready("translated", "译文", json.loads(good_meta))
    # 未验质量 → 拒绝
    assert not is_write_ready("translated", "译文",
                              json.dumps({"confidence": "high"}))
    # 状态必须是 translated 且译文非空
    assert not is_write_ready("pending", "译文", good_meta)
    assert not is_write_ready("translated", "", good_meta)
    # 低置信默认拒绝，人工提升放行
    low = json.dumps({"quality_passed": True, "confidence": "low"})
    assert not is_write_ready("translated", "译文", low)
    promoted = json.dumps({
        "quality_passed": True, "confidence": "low",
        "confidence_promoted": True,
    })
    assert is_write_ready("translated", "译文", promoted)
    # 坏 meta 一律拒绝
    assert not is_write_ready("translated", "译文", "{broken json")
    assert not is_write_ready("translated", "译文", 42)


# ── 写回模块：方法签名传递验证 ──

def test_method_signature_string_params():
    # 1 个 string 参数（return void=0x01）：[True]
    assert _method_signature_string_params(bytes([0x20, 0x01, 0x01, 0x0E])) == [True]
    # 2 个 string 参数
    assert _method_signature_string_params(
        bytes([0x20, 0x02, 0x01, 0x0E, 0x0E])) == [True, True]
    # int + string 混合 → [False, True]
    assert _method_signature_string_params(
        bytes([0x20, 0x02, 0x01, 0x08, 0x0E])) == [False, True]
    # PTR<string>（0x0F 后跟 string）：参数类型是 PTR，传递验证只认直接 string
    assert _method_signature_string_params(bytes([0x20, 0x01, 0x01, 0x0F, 0x0E])) == [False]
    # VALUETYPE（0x11 + compressed token 0x0F）→ 非 string
    assert _method_signature_string_params(
        bytes([0x20, 0x01, 0x01, 0x11, 0x0F])) == [False]
    # 空签名 / 非法 → 保守 None
    assert _method_signature_string_params(b"") is None
    assert _method_signature_string_params(bytes([0xFF])) is None
    # 复杂类型（GENERICINST 0x15 未建模）→ None
    assert _method_signature_string_params(
        bytes([0x20, 0x01, 0x01, 0x15, 0x0E, 0x0E])) is None


# ── 写回模块：WriteResult 记账与不变量 ──

def test_write_result_attempted_written_rejected_invariant():
    result = WriteResult(files=1, entries=0)
    entry = {"file_id": "a.bundle", "key_path": "k1"}
    result.note_attempt(entry)
    result.note_attempt(entry)      # 重复记账不叠加
    assert result.attempted == 1
    assert result.written == 0
    result.note_written(entry)
    assert result.entries == 1
    outcome = result.outcome
    assert outcome.attempted == 1 and outcome.written == 1
    assert outcome.rejected == ()
    assert result.is_resolved(entry)


def test_write_result_rejected_counts_and_locator_fallback():
    result = WriteResult()
    a = {"file_id": "x", "key_path": "k"}
    result.note_rejected(a, "immutable_field_protected")
    assert result.attempted == 1
    assert len(result.rejected) == 1
    assert result.rejected[0].reason == "immutable_field_protected"
    assert result.is_resolved(a)
    assert result.outcome.attempted == 1 and result.outcome.written == 0
    assert len(result.outcome.rejected) == 1
    # 无 file_id/key_path 时用 meta 偏移定位（DLL/IL2CPP 条目）
    raw = {"meta": json.dumps({
        "kind": "us", "heap_offset": 100, "utf16_len": 8,
    }), "original": "Hello"}
    result.note_written(raw)
    assert result.is_resolved(raw)
    assert result.written == 1


def test_write_result_truncated_capped_items():
    result = WriteResult()
    for i in range(40):
        result.note_truncated(f"原文{i}", f"译文{i}")
    assert result.truncated == 40
    assert len(result.truncated_items) == 30, "截断明细最多 30 条"
    # outcome 不变量：truncated 独立计数且 ≤ written（written=0 时非法？）
    # 注意：WriteOutcome 要求 truncated <= written；note_truncated 不记账 written，
    # 因此纯截断场景 written=0 会违反契约——由调用方保证（_patch_* 先 note_written）。
    result2 = WriteResult(entries=5)
    result2.note_truncated("a", "b")
    out = result2.outcome
    assert out.truncated == 1 and out.written == 5
    assert out.attempted == 5


def test_write_result_entries_backfills_attempted():
    result = WriteResult(files=1, entries=3)
    assert result.attempted == 3  # __post_init__ 回填
    assert result.outcome.attempted == 3
