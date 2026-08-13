"""#14 实时渲染文本加强：IL2CPP 格式模板细粒度分类。

真实样本（~/.hanhua_sweep/254361268a，minato 同池）证明含 {0}
占位符的字符串不全是引擎/调试形态——"HP: {0}/{1}"、
"<color=#00FF00>+{0} HP</color>" 是游戏 HUD/飘字实时渲染文本，
旧逻辑无条件跳过（哑信号，见 memory recognition-silent-miss-lesson）。

细分类设计（il2cpp.py _is_display_template）：
- 显示模板（TMP 标签/HUD 冒号/比值/加减值/按键交互）→ pending/
  medium/display/translate —— 可自动翻译（质量门禁放行）
- 其他含字母模板（引擎异常消息、键值模板）→ pending/low/display
  —— 留档可见，不浪费模型调用
- 无字母纯格式串 → 仍 engine_morph 跳过
"""
from pathlib import Path
import struct

import pytest


def _fake_metadata(literals: list[str]) -> bytes:
    """构造 v29 metadata（test_extractor_skipped_samples 同款）。"""
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


def _extract(tmp_path, literals):
    from hanhua.core.unity.il2cpp import extract_metadata_strings
    p = Path(tmp_path) / "global-metadata.dat"
    p.write_bytes(_fake_metadata(literals))
    return extract_metadata_strings(p, "m.dat")


def _real(entries):
    return [e for e in entries if not e.key_path.startswith("skip/")]


def _by_original(pf):
    return {e.original: e for e in _real(pf.entries)}


# ── 显示模板 → pending/medium（可自动翻译） ───────────────────

@pytest.mark.parametrize("text", [
    "HP: {0}/{1}",                    # HUD 冒号 + 比值（minato 真实样本）
    "Potions: {0}/{1}",
    "MP: {0}/{1}",
    "Playtime: {0}",                  # HUD 冒号单占位符
    "<color=#00FF00>+{0} HP</color>",  # TMP 富文本飘字（真实样本）
    "<color=#0000FF>+{0} MP</color>",
    "+{0} 经验",                       # 数值加减（无标签裸形态）
    "-{0} HP",
    "Press {0} to interact",          # 按键交互模板
    "Hold {0} to sprint",
    "Level {0}/{1}",                  # 比值形态
])
def test_display_templates_classified_medium(tmp_path, text):
    """游戏实时渲染显示模板 → pending/medium，进入自动翻译链。"""
    pf = _extract(tmp_path, [text])
    e = _by_original(pf)[text]
    assert e.status == "pending"
    assert e.meta["confidence"] == "medium"
    assert e.meta["role"] == "display"
    assert e.meta["disposition"] == "translate"
    assert e.meta["reason"] == "il2cpp_display_template"
    assert e.meta["file_offset"] >= 0  # 真实条目定位（可写回）


# ── 引擎消息/键值模板 → pending/low（留档可见，不自动翻译） ───

@pytest.mark.parametrize("text", [
    "Invalid token '{0}' in input string",   # dcdb50a165 真实样本
    "Can't assign null to an instance of type {0}",
    "Exception caught: {0}",
    "value={0}",                              # 键值模板（调试输出形态）
    "Argument '{0}' must be non-negative",
    "Format: expected {0} bytes, got {1}",
])
def test_engine_messages_archived_low(tmp_path, text):
    """引擎异常/键值模板 → pending/low 留档：可见不哑跳，且
    质量门禁（confidence≠low）不自动翻译——批量引擎消息不浪费模型调用。"""
    pf = _extract(tmp_path, [text])
    e = _by_original(pf)[text]
    assert e.status == "pending"
    assert e.meta["confidence"] == "low"
    assert e.meta["role"] == "display"
    assert e.meta["disposition"] == "translate"
    assert e.meta["reason"] == "il2cpp_format_template"


def test_pure_format_strings_still_skipped(tmp_path):
    """无字母纯格式串（"{0} - {1}"）仍被跳过（should_skip 的
    纯符号规则在分类链前吸收，不产生条目也不细分类）。"""
    pf = _extract(tmp_path, ["{0} - {1}"])
    assert not _real(pf.entries)
    assert pf.skipped_reasons  # 有跳过留档


def test_display_vs_engine_template_contrast(tmp_path):
    """区分度对照（真实样本）：HUD 比值模板 medium 可自动翻译，
    引擎异常模板（多词前缀 + 冒号）low 留档不浪费模型调用。"""
    pf = _extract(tmp_path, ["HP: {0}/{1}", "Exception caught: {0}"])
    hud = _by_original(pf)["HP: {0}/{1}"]
    assert hud.meta["reason"] == "il2cpp_display_template"
    assert hud.meta["confidence"] == "medium"
    engine = _by_original(pf)["Exception caught: {0}"]
    assert engine.meta["reason"] == "il2cpp_format_template"
    assert engine.meta["confidence"] == "low"


def test_placeholder_validation_preserved_in_pipeline(tmp_path):
    """显示模板条目与原分类链共用同一 TextEntry 形态：翻译/审校/
    写回端占位符校验（{0} 缺失会拦截）对 display 条目照常生效——
    此处验证条目进入待译池后占位符校验可访问。"""
    from hanhua.core.placeholders import extract_placeholders
    pf = _extract(tmp_path, ["HP: {0}/{1}"])
    e = _by_original(pf)["HP: {0}/{1}"]
    ph = extract_placeholders(e.original)
    assert "{0}" in ph and "{1}" in ph
    # 坏译文缺 {0} → 校验失败（写回前规则层拦截，见 quality 层测试）
    from hanhua.core.placeholders import validate_translation
    ok, _missing, _extra = validate_translation(e.original, "生命：/1")
    assert not ok
