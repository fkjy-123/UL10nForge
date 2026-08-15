from __future__ import annotations
from pathlib import Path

import chardet


def read_text(path: str | Path) -> str:
    """按 chardet 检测的编码读取文本文件（含 BOM 处理）。"""
    p = Path(path)
    raw = p.read_bytes()
    det = chardet.detect(raw)
    encoding = (det.get("encoding") or "utf-8").lower()
    if raw.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    elif encoding in ("ascii",):
        encoding = "utf-8"
    try:
        return raw.decode(encoding, errors="strict")
    except (UnicodeDecodeError, LookupError):
        # 兜底：gbk → latin-1
        for fallback in ("gbk", "latin-1"):
            try:
                return raw.decode(fallback, errors="strict")
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace")


def detect_eol(raw: bytes) -> str:
    """\r\n 计数超过 \n 一半时视为 CRLF。"""
    crlf = raw.count(b"\r\n")
    if raw.count(b"\n") > 0 and crlf > raw.count(b"\n") / 2:
        return "\r\n"
    return "\n"


def apply_format_text(fmt: str, entries, text: str, meta: dict) -> str:
    """按格式名把译文渲染回文本（writer 与 zip 内层共用）。

    meta 需含 csv 的 delimiter/target_col 等格式写回参数。
    """
    from hanhua.core.formats import (csv_format, json_format, txt_format,
                                     xml_format, yaml_format, subtitle_format,
                                     po_format, ink_yarn_format)
    if fmt == "kv":
        from hanhua.core.formats.kv_format import apply_kv
        return apply_kv(entries, text)
    if fmt == "json":
        return json_format.apply_json(entries, text)
    if fmt == "csv":
        suffix = meta.get("source_suffix")
        delimiter = meta.get("delimiter") or {
            ".tsv": "\t", ".psv": "|", None: ",", "": ",",
        }.get(suffix, ",")
        return csv_format.apply_csv(entries, text, delimiter, "zh-CN",
                                    meta.get("target_col"))
    if fmt == "xml":
        return xml_format.apply_xml(entries, text)
    if fmt == "yaml":
        return yaml_format.apply_yaml(entries)
    if fmt in ("srt", "vtt", "ass", "ssa", "lrc"):
        return subtitle_format.apply_subtitle(entries)
    if fmt == "po":
        return po_format.apply_po(entries, text)
    if fmt in ("ink", "yarn"):
        return ink_yarn_format.apply_ink_yarn(entries)
    return txt_format.apply_txt(entries)
