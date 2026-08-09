# -*- coding: utf-8 -*-
"""阶段二 P1 加固单元测试：F3 TextAsset strict、F7 XML CDATA/DOCTYPE、
CSV EOL 保留、省略号可配置。

- F3：写回侧 _patch_textasset 对非 UTF-8 字节整文件拒绝（返回原 bytes、
  全部 note_rejected，绝不用 errors="replace" 静默损坏）；
  提取侧 _textasset_entries 对非 UTF-8 字节不产生条目。
- F7：apply_xml 检测 CDATA/DOCTYPE 抛 XmlRewriteUnsafeError；
  _patch_textasset 捕获后整文件拒绝。
- CSV EOL：CRLF 源文件写回后仍 CRLF。
- 省略号：TRUNCATION_ELLIPSIS 可整体替换（TMP 字体缺字形兜底）。
"""
import json

import pytest

from hanhua.core.formats.csv_format import apply_csv
from hanhua.core.formats.xml_format import XmlRewriteUnsafeError, apply_xml
from hanhua.core.unity.extractor import _textasset_entries
from hanhua.core.unity.writer import (
    WriteResult, TRUNCATION_ELLIPSIS, _fit_bytes, _patch_textasset,
)


def _line_entry(line: int, original: str, translation: str) -> tuple[dict, dict]:
    meta = {"kind": "textasset", "line": line, "disposition": "translate"}
    entry = {
        "file_id": "ta", "key_path": f"line/{line}",
        "original": original, "translation": translation,
        "status": "pending", "meta": json.dumps(meta),
    }
    return entry, meta


# --------------------------------------------------------------------------
# F3：TextAsset strict decode
# --------------------------------------------------------------------------

def test_textasset_write_rejects_non_utf8_script(tmp_path):
    """写回侧：script 非合法 UTF-8（GBK/Latin-1 等误判）→ 整文件拒绝，
    返回原字节零改动，全部条目 note_rejected。"""
    script = "欢迎\nHello".encode("gbk")           # GBK 字节对 strict UTF-8 非法
    result = WriteResult()
    patched = _patch_textasset(script, [
        _line_entry(1, "Hello", "你好"),
    ], [], result)
    assert patched == script                        # 原样返回
    assert result.written == 0
    assert len(result.rejected) == 1
    assert "UTF-8" in result.rejected[0].reason


def test_textasset_write_rejects_structured_items_on_non_utf8(tmp_path):
    script = b"<root>\xff\xfe</root>"
    result = WriteResult()
    entry = {
        "file_id": "ta", "key_path": "root",
        "original": "Hello", "translation": "你好",
        "status": "pending",
    }
    patched = _patch_textasset(
        script, [], [(entry, {"kind": "textasset", "textasset_format": "xml"})], result)
    assert patched == script
    assert result.written == 0
    assert len(result.rejected) == 1


def test_textasset_write_valid_utf8_still_patches(tmp_path):
    """正常路径不受影响：合法 UTF-8 行级替换照常。"""
    script = "Hello\nWorld".encode("utf-8")
    result = WriteResult()
    patched = _patch_textasset(script, [
        _line_entry(0, "Hello", "你好"),
    ], [], result)
    assert patched.decode("utf-8") == "你好\nWorld"
    assert result.attempted == 1                  # note_written 由调用方原子替换后执行


def test_textasset_extract_skips_non_utf8_raw():
    """提取侧：非 UTF-8 字节不产生条目（mojibake 源头过滤）。"""
    raw = "欢迎\nHello".encode("gbk")
    assert _textasset_entries("f", 1, raw) == []


def test_textasset_extract_valid_utf8_unchanged():
    raw = "Hello\nWorld".encode("utf-8")
    entries = _textasset_entries("f", 1, raw)
    assert any("World" in e.original for e in entries)


# --------------------------------------------------------------------------
# F7：XML CDATA/DOCTYPE 拒绝重序列化
# --------------------------------------------------------------------------

def test_apply_xml_rejects_cdata():
    xml = '<?xml version="1.0"?>\n<root><data><![CDATA[raw <script>]]></data></root>'
    with pytest.raises(XmlRewriteUnsafeError, match="CDATA"):
        apply_xml([], xml)


def test_apply_xml_rejects_doctype():
    xml = ('<?xml version="1.0"?>\n<!DOCTYPE root SYSTEM "game.dtd">\n'
           "<root><text>Hello</text></root>")
    with pytest.raises(XmlRewriteUnsafeError, match="DOCTYPE"):
        apply_xml([], xml)


def test_apply_xml_normal_file_still_works():
    xml = '<root><text>Hello</text></root>'
    from hanhua.core.models import TextEntry
    out = apply_xml([TextEntry(file_id="f", key_path="/root/text",
                               original="Hello", translation="你好")], xml)
    assert "你好" in out


def test_textasset_write_rejects_cdata_xml(tmp_path):
    """写回侧：TextAsset 内嵌 XML 含 CDATA → 整文件拒绝，条目全部警示。"""
    script = b"<root><data><![CDATA[raw]]></data><text>Hello</text></root>"
    result = WriteResult()
    entry = {
        "file_id": "ta", "key_path": "root/text",
        "original": "Hello", "translation": "你好",
        "status": "pending",
    }
    patched = _patch_textasset(
        script, [], [(entry, {"kind": "textasset", "textasset_format": "xml"})], result)
    assert patched == script
    assert result.written == 0
    assert len(result.rejected) == 1
    assert "cdata" in result.rejected[0].reason.lower()


# --------------------------------------------------------------------------
# CSV EOL 保留
# --------------------------------------------------------------------------

def test_apply_csv_preserves_crlf():
    from hanhua.core.models import TextEntry
    text = "key,en\r\nhello,Hello\r\nworld,World\r\n"
    entries = [
        TextEntry(file_id="f", key_path="row/1", original="Hello",
                  translation="你好", meta={"row": 1}),
    ]
    out = apply_csv(entries, text, ",", "zh-CN", 1)
    assert "\r\n" in out
    assert "\n" not in out.replace("\r\n", "")     # 无孤立 LF


def test_apply_csv_preserves_lf():
    from hanhua.core.models import TextEntry
    text = "key,en\nhello,Hello\nworld,World\n"
    entries = [
        TextEntry(file_id="f", key_path="row/1", original="Hello",
                  translation="你好", meta={"row": 1}),
    ]
    out = apply_csv(entries, text, ",", "zh-CN", 1)
    assert "\r\n" not in out


# --------------------------------------------------------------------------
# 省略号字符可配置
# --------------------------------------------------------------------------

def test_truncation_ellipsis_switchable(monkeypatch):
    """TMP 字体缺「…」字形时可将提示符整体替换为 ASCII 兜底。"""
    monkeypatch.setattr("hanhua.core.unity.writer.TRUNCATION_ELLIPSIS", "...")
    data, truncated = _fit_bytes("超长译文内容", 12, "utf-8", pad=False)
    assert truncated
    assert data.decode("utf-8").endswith("...")
    assert len(data) <= 12


def test_truncation_ellipsis_default():
    data, truncated = _fit_bytes("超长译文内容", 12, "utf-8", pad=False)
    assert truncated and data.decode("utf-8").endswith(TRUNCATION_ELLIPSIS)
