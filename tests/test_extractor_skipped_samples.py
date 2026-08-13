"""识别 L1 测试：静默 continue 限量样本留档（R5 可见化升级）。

mono_dll.py 3 处与 il2cpp.py 3 处 continue 从「纯计数」升级为
「计数 + 限量样本条目」——skipped 样本以 key_path 加 skip/ 前缀
与真实条目定位隔离（写回端只处理 translated、noise 判定只看 pending，
样本天然不可写回、不可触发噪声判定）。
"""
import json
import struct
import tempfile
from pathlib import Path

from hanhua.core.extractor import ParsedFile
from hanhua.core.models import STATUS_SKIPPED
from hanhua.core.unity.extractor import _PREFILTER_SAMPLE_LIMIT, _skipped_sample_entry


# ── _skipped_sample_entry 纯函数 ──────────────────────────────

def test_skipped_sample_entry_basic():
    e = _skipped_sample_entry("f1", "skip/us#12", "Assets/a.png",
                              kind="us", reason="hard_structural", count=3)
    assert e is not None
    assert e.file_id == "f1"
    assert e.key_path == "skip/us#12"
    assert e.original == "Assets/a.png"
    assert e.status == STATUS_SKIPPED
    meta = e.meta
    assert meta["kind"] == "us"
    assert meta["confidence"] == "low"
    assert meta["role"] == "structural"
    assert meta["disposition"] == "structural"
    assert meta["reason"] == "hard_structural"
    assert meta["skipped_count"] == 3


def test_skipped_sample_entry_limited_to_prefilter_quota():
    """限量：count > _PREFILTER_SAMPLE_LIMIT 返回 None（≤10 条/原因）。"""
    at_limit = _skipped_sample_entry(
        "f1", "skip/meta#1", "v", kind="il2cpp", reason="r",
        count=_PREFILTER_SAMPLE_LIMIT)
    assert at_limit is not None
    over = _skipped_sample_entry(
        "f1", "skip/meta#11", "v", kind="il2cpp", reason="r",
        count=_PREFILTER_SAMPLE_LIMIT + 1)
    assert over is None


def test_skipped_sample_entry_merges_extra_meta():
    e = _skipped_sample_entry(
        "f1", "skip/us#5", "p", kind="us", reason="r", count=2,
        extra_meta={"record_offset": 100})
    assert e.meta["record_offset"] == 100
    assert e.meta["reason"] == "r"


# ── IL2CPP 集成：3 处 continue 形态 ───────────────────────────

def _fake_metadata(literals: list[str]) -> bytes:
    """构造 v29 metadata：魔数 + 字面量记录表 + 数据区（test_v2 同款）。"""
    data = b"".join(s.encode("utf-8") for s in literals)
    offsets = []
    pos = 0
    for s in literals:
        n = len(s.encode("utf-8"))
        offsets.append((pos, n))
        pos += n
    header = bytearray(0x30)
    struct.pack_into("<II", header, 0, 0xFAB11BAF, 29)
    table_size = len(literals) * 8
    struct.pack_into("<II", header, 0x08, 0x100, table_size)
    struct.pack_into("<II", header, 0x10, 0x200, len(data))
    lit_arr = b"".join(struct.pack("<II", ln, off) for off, ln in offsets)
    buf = bytes(header) + b"\x00" * (0x100 - 0x30) + lit_arr
    return buf + b"\x00" * (0x200 - len(buf)) + data


def _extract_il2cpp(tmp_path, literals):
    from hanhua.core.unity.il2cpp import extract_metadata_strings
    p = Path(tmp_path) / "global-metadata.dat"
    p.write_bytes(_fake_metadata(literals))
    return extract_metadata_strings(p, "m.dat")


def test_il2cpp_samples_recorded_for_each_skip_reason(tmp_path):
    """三种 continue 形态各产样本：illegal_controls/code_identifier/
    engine_morph；正常字面量仍是真实条目（key_path 无 skip/ 前缀）。"""
    pf = _extract_il2cpp(tmp_path, [
        "ab\x01cd",              # illegal_controls
        "PlayerController",      # code_identifier
        "  depth level",         # engine_morph（行首空白调试输出）
        "Hello player",          # 真实条目
    ])
    samples = [e for e in pf.entries if e.key_path.startswith("skip/")]
    real = [e for e in pf.entries if not e.key_path.startswith("skip/")]
    by_reason = {e.meta["reason"]: e for e in samples}
    assert set(by_reason) == {"illegal_controls", "code_identifier",
                              "engine_morph"}
    for e in samples:
        assert e.status == STATUS_SKIPPED
        assert e.meta["kind"] == "il2cpp"
        assert e.meta["skipped_count"] == 1
        assert e.meta["confidence"] == "low"
        assert not e.meta.get("file_offset")  # 样本不伪装真实条目定位
    assert len(real) == 1
    # data_index 是数据区字节偏移：5(\x01cd 前) + 16(PlayerController)
    # + 13("  depth level") = 34——与真实条目定位语义一致，未被样本挤占
    assert real[0].key_path == "meta#34"
    assert real[0].meta["file_offset"] >= 0
    assert real[0].original == "Hello player"
    # 样本 key_path 保留原 data_index 可追溯
    assert "meta#0" in by_reason["illegal_controls"].key_path


def test_il2cpp_sample_quota_capped_at_ten_per_reason(tmp_path):
    """同类跳过 15 条 → 样本 ≤10 条；提取器末尾把累计计数（1..10）
    回写为最终计数 15——报告聚合（按单元取 max）即真实总数
    （累计值被求和的 55 失真修复：聚合端 15 而非 1+2+…+10=55）。"""
    pf = _extract_il2cpp(tmp_path, ["  depth level"] * 15)
    samples = [e for e in pf.entries if e.key_path.startswith("skip/")]
    assert len(samples) == _PREFILTER_SAMPLE_LIMIT
    assert {e.meta["skipped_count"] for e in samples} == {15}
    assert all(e.status == STATUS_SKIPPED for e in samples)
    # 全 skipped 文件本判噪声（既有语义：无 pending 可译内容），
    # 样本机制不改变判定——与写回/噪声无关的纯留档
    assert pf.noise is True


def test_il2cpp_engine_morph_leading_ws(tmp_path):
    """engine_morph 可达路径（行首空白多词串）留档。

    超短/无字母/单词行首空白实际被 code_identifier 分支吸收（"ab"/
    "123"/"\n  depth" 命中 should_skip 或 is_code_identifier 先退出）。
    #14 之后含字母的 {0} 模板不再走 engine_morph：显示模板细分类为
    medium、其他模板 low 留档（见 test_il2cpp_display_templates）。
    """
    pf = _extract_il2cpp(tmp_path, ["  depth level"])
    samples = [e for e in pf.entries if e.key_path.startswith("skip/")]
    assert len(samples) == 1
    assert samples[0].meta["reason"] == "engine_morph"


# ── Mono 集成：3 处 continue 形态 ─────────────────────────────

def _mono_heap(strings: list[str]) -> bytes:
    """ECMA-335 #US 堆：offset 0 占位 + 每条记录（压缩长度 + UTF-16 + flag）。"""
    out = bytearray(b"\x00")
    for s in strings:
        encoded = s.encode("utf-16-le") + b"\x01"
        assert len(encoded) < 0x80  # 单字节压缩长度
        out += bytes([len(encoded)]) + encoded
    return bytes(out)


def _extract_mono(tmp_path, monkeypatch, strings):
    import dnfile
    from types import SimpleNamespace
    from hanhua.core.unity.mono_dll import extract_dll_user_strings

    heap = _mono_heap(strings)

    class FakeUserStrings:
        def sizeof(self):
            return len(heap)

        def get_data_at_offset(self, offset, size):
            assert (offset, size) == (0, len(heap))
            return heap

        def get_file_offset(self, offset):
            return 0x400

    fake_pe = SimpleNamespace(
        net=SimpleNamespace(
            user_strings=FakeUserStrings(),
            mdtables=SimpleNamespace(
                MemberRef=SimpleNamespace(rows=[]),
                MethodDef=SimpleNamespace(rows=[]),
            ),
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(dnfile, "dnPE", lambda _path: fake_pe)
    return extract_dll_user_strings(Path(tmp_path) / "Game.dll")


def test_mono_samples_recorded_for_each_skip_reason(tmp_path, monkeypatch):
    """mono 三种 continue 形态各产样本：hard_structural/engine_core/
    code_identifier；正常串仍是真实条目。"""
    pf = _extract_mono(tmp_path, monkeypatch, [
        "Assets/Textures/UI/button.png",   # hard_structural（路径）
        "Hidden/Post FX/FXAA",             # engine_core（Shader 查找键）
        "PlayerController",                # code_identifier（无 UI 证据）
        "Press W to jump",                 # 真实条目（交互提示 → pending）
    ])
    samples = [e for e in pf.entries if e.key_path.startswith("skip/")]
    real = [e for e in pf.entries if not e.key_path.startswith("skip/")]
    by_reason = {e.meta["reason"]: e for e in samples}
    assert set(by_reason) == {"hard_structural", "engine_core",
                              "code_identifier"}
    for e in samples:
        assert e.status == STATUS_SKIPPED
        assert e.meta["kind"] == "us"
        assert e.meta["skipped_count"] == 1
    assert len(real) == 1
    assert real[0].key_path.startswith("us#")  # 真实定位语义不变（无 skip/ 前缀）
    assert real[0].status == "pending"
    assert real[0].meta["record_offset"] > 0
    assert real[0].original == "Press W to jump"


def test_mono_sample_key_path_keeps_record_trace(tmp_path, monkeypatch):
    """样本 key_path 保留原 us#offset 可追溯（skip/ 前缀仅隔离定位）。"""
    pf = _extract_mono(tmp_path, monkeypatch, [
        "Assets/Textures/UI/button.png",
        "Hidden/Post FX/FXAA",
    ])
    samples = sorted(e.key_path for e in pf.entries)
    # key_path = 数据区偏移（与真实条目同语义）：offset 0 占位 + 记录1
    # （1 字节前缀 + 29 字符×2 + flag）→ 记录1 数据在 2、记录2 数据在 62
    assert samples == ["skip/us#2", "skip/us#62"]


def test_mono_real_entries_unaffected_by_samples(tmp_path, monkeypatch):
    """样本不干扰真实条目的 pending 流程：有真实 pending 时文件
    不判噪声，样本只做留档不改变既有语义。"""
    pf = _extract_mono(tmp_path, monkeypatch, [
        "Assets/Textures/UI/button.png",
        "Press W to jump",
    ])
    real = [e for e in pf.entries if not e.key_path.startswith("skip/")]
    assert len(real) == 1
    assert real[0].status == "pending"
    assert real[0].original == "Press W to jump"
    assert not pf.noise
