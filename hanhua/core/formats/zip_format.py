"""ZIP 容器：提取内部文本文件并整包写回。

游戏常把本地化表/剧情脚本打进 .zip/.pak（StreamingAssets、Mods）。
extract 递归入口（zip-in-zip ≤2 层）把每个文本条目标记为
「zip 内路径 + 原格式定位键」，写回时按条目重建内层文本并重建整个
ZIP（保留原始条目顺序与压缩方式）。二进制条目原样拷贝。
"""
from __future__ import annotations
import io
import os
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote

import chardet

from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.scanner import _BINARY_SUFFIXES, _looks_like_text, _NOISY_PROBE_EXTS

MAX_ZIP_ENTRIES = 4000
MAX_ENTRY_UNCOMPRESSED = 8 * 1024 * 1024   # 单条目解压上限 8MB
MAX_TOTAL_UNCOMPRESSED = 400 * 1024 * 1024  # 总解压上限 400MB（压缩炸弹防护）
MAX_DEPTH = 2                                # zip 内 zip 嵌套深度
_INNER_PREFIX = "zip!"


def _entry_file_id(zip_fid: str, entry_name: str, depth: int = 0) -> str:
    return f"{zip_fid}/{_INNER_PREFIX}{'nested/' * depth}{quote(entry_name, safe='')}"


def _decode(raw: bytes) -> str:
    """按 chardet 解码 zip 条目字节（与 read_text 同策略）。

    chardet 只喂头部样本（2026-08-19 扫描性能修复，见 extractor
    ._detect_encoding——全量 chardet 是大文件内存暴涨源头）；zip
    条目已有 8MB 解压上限，此处再保险截断。"""
    sample = raw[:65536] if len(raw) > 65536 else raw
    det = chardet.detect(sample)
    encoding = (det.get("encoding") or "utf-8").lower()
    if raw.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    elif encoding == "ascii":
        encoding = "utf-8"
    try:
        return raw.decode(encoding, errors="strict")
    except (UnicodeDecodeError, LookupError):
        for fallback in ("gbk", "latin-1"):
            try:
                return raw.decode(fallback, errors="strict")
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace")


def extract_zip(path: str | Path, file_id: str | None = None,
                depth: int = 0) -> tuple[list[TextEntry], dict]:
    """返回 (条目, 元数据)。元数据记录条目名列表供写回重建。"""
    p = Path(path)
    fid = file_id or p.name
    entries: list[TextEntry] = []
    entry_names: list[str] = []
    total = 0
    try:
        zf = zipfile.ZipFile(p)
    except (zipfile.BadZipFile, OSError):
        return [], {"kind": "zip", "entry_names": [], "depth": depth}
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if len(entry_names) >= MAX_ZIP_ENTRIES:
                break
            entry_names.append(info.filename)
            if info.file_size > MAX_ENTRY_UNCOMPRESSED:
                continue
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED:
                break
            _collect_entry(zf, info, entries, fid, depth)
    return entries, {"kind": "zip", "entry_names": entry_names, "depth": depth}


def _collect_entry(zf: zipfile.ZipFile, info: zipfile.ZipInfo,
                   entries: list[TextEntry], zip_fid: str, depth: int) -> None:
    name = info.filename
    suffix = Path(name).suffix.lower()
    try:
        raw = zf.read(info)
    except (zipfile.BadZipFile, OSError, RuntimeError, EOFError):
        return
    # 嵌套 zip
    if suffix == ".zip" and depth < MAX_DEPTH and raw.startswith(b"PK\x03\x04"):
        inner_entries, _ = extract_zip_bytes(
            raw, _entry_file_id(zip_fid, name, depth), depth + 1)
        entries.extend(inner_entries)
        return
    # 已知二进制/媒体后缀 → 跳过；其余做文本判定
    if suffix in _BINARY_SUFFIXES or suffix in _NOISY_PROBE_EXTS:
        return
    if not _looks_like_text(raw[:4096]):
        return
    parsed = _parse_zip_entry(raw, name, _entry_file_id(zip_fid, name, depth))
    if parsed is None:
        return
    inner_fmt, inner_entries = parsed
    for e in inner_entries:
        e.meta = {**e.meta, "zip_inner": name, "zip_fmt": inner_fmt,
                  "zip_depth": depth}
    entries.extend(inner_entries)


def extract_zip_bytes(raw: bytes, file_id: str, depth: int) -> tuple[list[TextEntry], dict]:
    """zip-in-zip 递归：从字节加载内层包。"""
    entries: list[TextEntry] = []
    total = 0
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, OSError):
        return entries, {}
    with zf:
        for info in zf.infolist():
            if info.is_dir() or info.file_size > MAX_ENTRY_UNCOMPRESSED:
                continue
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED:
                break
            _collect_entry(zf, info, entries, file_id, depth)
    return entries, {}


def _parse_zip_entry(raw: bytes, name: str, entry_file_id: str):
    """按后缀/内容把 zip 内条目路由到文本解析器（经临时文件复用解析链路）。"""
    from hanhua.core.extractor import parse_file
    suffix = Path(name).suffix.lower()
    handle = None
    try:
        handle = tempfile.NamedTemporaryFile(
            prefix="hanhua_zip_", suffix=suffix or ".txt", delete=False)
        handle.write(raw)
        handle.close()
        parsed = parse_file(handle.name, file_id=entry_file_id)
        if parsed.noise or not parsed.entries:
            return None
        return parsed.format, parsed.entries
    except Exception:  # noqa: BLE001 —— 单个 zip 条目失败不影响整包
        return None
    finally:
        if handle is not None:
            try:
                os.unlink(handle.name)
            except OSError:
                pass


def apply_zip(src_path: Path, entries: list[TextEntry]) -> bytes:
    """重建 ZIP：有译文的内部文本条目重新渲染，其余条目原样拷贝。"""
    by_inner: dict[str, tuple[str, list[TextEntry]]] = {}
    for e in entries:
        inner = e.meta.get("zip_inner")
        if not isinstance(inner, str):
            continue
        fmt = e.meta.get("zip_fmt", "txt")
        by_inner.setdefault(inner, (fmt, []))[1].append(e)
    output = io.BytesIO()
    with zipfile.ZipFile(src_path) as src_zip:
        with zipfile.ZipFile(output, "w") as out_zip:
            for info in src_zip.infolist():
                raw = src_zip.read(info)
                group = by_inner.get(info.filename)
                if group is None or info.file_size > MAX_ENTRY_UNCOMPRESSED:
                    out_zip.writestr(info, raw)
                    continue
                fmt, inner_entries = group
                translated = [e for e in inner_entries
                              if e.status != STATUS_SKIPPED and e.translation]
                if not translated:
                    out_zip.writestr(info, raw)
                    continue
                text = _decode(raw)
                from hanhua.core.formats import apply_format_text
                body = apply_format_text(fmt, inner_entries, text, {})
                out_zip.writestr(info, body.encode("utf-8"))
    return output.getvalue()
