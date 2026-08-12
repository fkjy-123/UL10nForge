"""识别 L3 测试：IL2CPP 字面量池接入类型/方法上下文（字符串区交叉）。

评估报告：il2cpp.py 仅 sentence_like 与 interaction 两档，无类型/方法
上下文（对比 mono 有 IL 验证链）；metadata 字面量池缺「消费位置」证据。
建议：用 Il2CppDumper 已交叉验证的布局把 method 表/类型表关联到字面量，
做类名上下文判定。

落地：字符串区（header 0x18/0x1C，Il2CppDumper 跨 v24-v31 稳定布局）=
类型名/方法名/namespace/字段名全集；字面量与成员相等是反射/代码引用键
的确定性证据（typeof/GetMethod 参数等运行时按名查找），reason 细分
reflection_key 且优先于 engine_morph 长度猜测；解析失败一律降级空集。
v39 字符串区偏移未验证（Il2CppDumper 6.7.46 不支持），不启用。
"""
import struct

import pytest

from hanhua.core.unity.il2cpp import (
    _MAX_POOL_ENTRIES, _STRING_POOL_VERSION_OK, _metadata_string_pool)


def _fake_metadata(literals: list[str], strings: tuple[str, ...] = ()) -> bytes:
    """构造 v29 metadata：字面量记录表 + 数据区 + 字符串区（识别 L3）。"""
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
    buf += b"\x00" * (0x200 - len(buf)) + data
    if strings:
        str_blob = b"\x00".join(s.encode("utf-8") for s in strings) + b"\x00"
        str_off = len(buf)
        struct.pack_into("<II", header, 0x18, str_off, len(str_blob))
        buf = bytes(header) + buf[len(header):] + str_blob
    return buf


def _extract_il2cpp(tmp_path, literals, strings=()):
    from hanhua.core.unity.il2cpp import extract_metadata_strings
    p = tmp_path / "global-metadata.dat"
    p.write_bytes(_fake_metadata(literals, strings))
    return extract_metadata_strings(p, "m.dat")


def _mutate_header(raw: bytes, pos: int, value: int) -> bytes:
    b = bytearray(raw)
    struct.pack_into("<I", b, pos, value)
    return bytes(b)


# ── _metadata_string_pool 纯函数 ────────────────────────────

def test_string_pool_parses_nul_separated_names():
    """字符串区正常 → 标识符全集（类型名/方法名/namespace 名）。"""
    raw = _fake_metadata(["UI"], strings=("PlayerController", "Start",
                                          "System.Collections"))
    pool = _metadata_string_pool(raw)
    assert pool == frozenset({"PlayerController", "Start",
                              "System.Collections"})


def test_string_pool_empty_when_no_string_section():
    """无字符串区（str_size=0）→ 空集（既有 metadata 不受影响）。"""
    raw = _fake_metadata(["Hello player"])
    assert _metadata_string_pool(raw) == frozenset()


def test_string_pool_empty_on_out_of_bounds():
    """字符串区偏移越界 → 空集（畸形布局降级）。"""
    raw = _fake_metadata(["UI"], strings=("Start",))
    bad = _mutate_header(raw, 0x18, len(raw) - 4)
    assert _metadata_string_pool(bad) == frozenset()


def test_string_pool_empty_on_unterminated_blob():
    """字符串区无 NUL 终结 → 空集（不是字符串数组布局）。"""
    raw = _fake_metadata(["UI"], strings=("Start",))
    bad = _mutate_header(raw, 0x1C, 3)  # 只含 "Sta" 无 NUL
    assert _metadata_string_pool(bad) == frozenset()


def test_string_pool_empty_on_undecodable_blob():
    """字符串区含非 UTF-8 → 空集（metadata 标识符区必须全可解码）。"""
    raw = _fake_metadata(["UI"], strings=("Start",))
    b = bytearray(raw)
    # 把字符串区第一字节改成 0xFF（非法 UTF-8 首字节）
    str_off = struct.unpack_from("<I", raw, 0x18)[0]
    b[str_off] = 0xFF
    assert _metadata_string_pool(bytes(b)) == frozenset()


def test_string_pool_disabled_for_unverified_versions():
    """v39 字符串区偏移未验证 → 不启用（空集），待真实样本校准。"""
    raw = _fake_metadata(["UI"], strings=("Start",))
    v39 = _mutate_header(raw, 0x04, 39)
    assert 39 not in _STRING_POOL_VERSION_OK
    assert _metadata_string_pool(v39) == frozenset()


def test_string_pool_empty_on_bad_magic():
    """非 metadata 文件（魔数不符）→ 空集。"""
    raw = _fake_metadata(["UI"], strings=("Start",))
    bad = _mutate_header(raw, 0x00, 0xDEADBEEF)
    assert _metadata_string_pool(bad) == frozenset()


# ── 集成：反射键判定 + 样本留档 + 降级安全 ─────────────────

def test_reflection_key_skipped_with_sample(tmp_path):
    """字面量 == 字符串区成员（2 字符 "UI" 穿透形态正则）→
    reflection_key 跳过 + 限量样本 + 计数留档。"""
    pf = _extract_il2cpp(tmp_path, ["UI", "OK"], strings=("UI", "Start"))
    assert pf.skipped_reasons["reflection_key"] == 1
    skip = [e for e in pf.entries if e.original == "UI"][0]
    assert skip.status == "skipped"
    assert skip.meta["reason"] == "reflection_key"
    assert skip.meta["kind"] == "il2cpp"
    # "OK" 不在字符串区 → 不误判（长度 <3 走 engine_morph 兜底）
    ok = [e for e in pf.entries if e.original == "OK"][0]
    assert ok.meta["reason"] == "engine_morph"


def test_reflection_key_takes_priority_over_length_guess(tmp_path):
    """确定性集合命中优先于 engine_morph 的长度猜测（证据分层）：
    "UI"（2 字符本会因 <3 被 engine_morph 兜底）因字符串区命中细分。"""
    pf = _extract_il2cpp(tmp_path, ["UI"], strings=("UI",))
    skip = [e for e in pf.entries if e.original == "UI"][0]
    assert skip.meta["reason"] == "reflection_key"


def test_pool_failure_degrades_classification(tmp_path):
    """字符串区布局非法（越界）→ 降级：判定保持现状（"UI" 走长度兜底）。"""
    raw = _fake_metadata(["UI"], strings=("UI",))
    bad = _mutate_header(raw, 0x18, len(raw) - 4)
    p = tmp_path / "global-metadata.dat"
    p.write_bytes(bad)
    from hanhua.core.unity.il2cpp import extract_metadata_strings
    pf = extract_metadata_strings(p, "m.dat")
    assert pf.skipped_reasons.get("reflection_key") is None
    skip = [e for e in pf.entries if e.original == "UI"][0]
    assert skip.meta["reason"] == "engine_morph"


def test_sentence_literals_unaffected_by_pool(tmp_path):
    """句子形态字面量不在字符串区（标识符无空格）→ 分类链不变：
    交互提示仍 pending/medium，普通句子仍 pending/low。"""
    pf = _extract_il2cpp(
        tmp_path, ["Press W to jump", "hello player"],
        strings=("Start", "PlayerController"))
    prompt = [e for e in pf.entries if e.original == "Press W to jump"][0]
    assert prompt.status == "pending"
    assert prompt.meta["reason"] == "il2cpp_interaction_prompt"
    sentence = [e for e in pf.entries if e.original == "hello player"][0]
    assert sentence.status == "pending"
    assert sentence.meta["reason"] == "il2cpp_sentence"


def test_v39_pool_off_not_consumed(tmp_path):
    """v39 整体：字符串区不启用（偏移未验证），分类链按既有语义走。"""
    raw = _fake_metadata(["UI"], strings=("UI",))
    v39 = _mutate_header(raw, 0x04, 39)
    # v39 是 implicit 布局（4 字节记录）——但既有 parse 会对 declared
    # 计数 0x10 字段校验失败 → 空结果（与字符串区无关，行为不变）
    p = tmp_path / "global-metadata.dat"
    p.write_bytes(v39)
    from hanhua.core.unity.il2cpp import extract_metadata_strings
    pf = extract_metadata_strings(p, "m.dat")
    assert pf.skipped_reasons.get("reflection_key") is None


def test_pool_entry_limit_guards_dead_loop():
    """畸形无 NUL 区段受 _MAX_POOL_ENTRIES 上限保护（不无限循环）。"""
    assert _MAX_POOL_ENTRIES > 0
    # 在文件尾部追加无 NUL 区段（全 0x41）并指向它——解析必须受上限
    # 保护返回空集（而非死循环/超时）
    raw = _fake_metadata(["UI"])
    b = bytearray(raw)
    no_nul = b"\x41" * 64
    off = len(b)
    struct.pack_into("<I", b, 0x18, off)
    struct.pack_into("<I", b, 0x1C, len(no_nul))
    b += no_nul
    assert _metadata_string_pool(bytes(b)) == frozenset()
