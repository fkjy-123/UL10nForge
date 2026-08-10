from __future__ import annotations
import gzip
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from hanhua.core.engine_strings import is_engine_string
from hanhua.core.formats import (json_format, txt_format, csv_format, xml_format,
                                 yaml_format, subtitle_format, po_format,
                                 ink_yarn_format, zip_format, sqlite_format,
                                 read_text, detect_eol)
from hanhua.core.models import TextEntry, STATUS_SKIPPED
from hanhua.core.placeholders import should_skip
from hanhua.core.scanner import probe_head_kind


@dataclass
class ParsedFile:
    file_id: str
    rel_path: str
    format: str
    entries: list[TextEntry]
    encoding: str = "utf-8"
    eol: str = "\n"
    meta: dict = field(default_factory=dict)
    noise: bool = False      # True = 整个文件被判定为运行时噪音，不入库


# 无空格标识符风格（如 NavMeshLink、UnityEngine、Assembly-CSharp）——大概率不是显示文本
_NO_SPACE_TOKEN = re.compile(r"^[A-Za-z0-9_.\-/]{2,60}$")


def looks_like_noise_file(entries: list[TextEntry]) -> bool:
    """文件级噪音判定：
    1) 没有任何可译条目 → 噪音（纯配置/清单）
    2) ≥3 条可译条目且 ≥80% 为无空格标识符 → 噪音（Unity 运行时标识符文本）
    """
    pending = [e for e in entries if e.status == "pending"]
    if not pending:
        return True
    # 无空格且 ≥10 字符才是标识符特征（短单词如 Hi/OK 是正常 UI 文本）
    tokens = sum(1 for e in pending
                 if _NO_SPACE_TOKEN.match(e.original.strip()) and len(e.original.strip()) >= 10)
    ratio = tokens / len(pending)
    if len(pending) >= 3 and ratio >= 0.8:
        return True
    if len(pending) <= 2 and ratio == 1.0:
        return True
    return False


def _detect_encoding(raw: bytes) -> str:
    import chardet
    det = chardet.detect(raw)
    enc = (det.get("encoding") or "utf-8").lower()
    if enc in ("ascii",):
        return "utf-8"
    return enc


def parse_file(path: str | Path, file_id: str | None = None) -> ParsedFile:
    p = Path(path)
    suffix = p.suffix.lower()
    fid = file_id or p.name
    raw = p.read_bytes()
    encoding = _detect_encoding(raw)
    eol = detect_eol(raw)
    if suffix in (".gz",):
        entries, fmt, meta = _parse_compressed(raw, p, fid)
    elif suffix in (".json", ".json5", ".jsonl", ".ndjson", ".arb"):
        entries = json_format.extract_json(p, fid)
        fmt, meta = "json", {}
    elif suffix in (".csv", ".tsv", ".psv"):
        entries, target_col = csv_format.extract_csv(p, target_lang="zh-CN", file_id=fid)
        fmt, meta = "csv", {"target_col": target_col}
    elif suffix in (".xml", ".resx", ".xlf", ".xliff", ".tmx", ".ttml"):
        entries = xml_format.extract_xml(p, fid)
        fmt, meta = "xml", {}
    elif suffix in (".yaml", ".yml"):
        entries = yaml_format.extract_yaml(p, fid)
        fmt, meta = "yaml", {}
    elif suffix in (".srt", ".vtt", ".ass", ".ssa", ".lrc"):
        entries = subtitle_format.extract_subtitle(p, fid, kind=suffix.lstrip("."))
        fmt, meta = "subtitle", {}
    elif suffix == ".po":
        entries = po_format.extract_po(p, fid)
        fmt, meta = "po", {}
    elif suffix in (".ink", ".yarn"):
        entries = ink_yarn_format.extract_ink_yarn(p, fid, kind=suffix.lstrip("."))
        fmt, meta = "ink_yarn", {}
    elif suffix == ".zip":
        entries, meta = zip_format.extract_zip(p, fid)
        fmt = "zip"
    elif suffix in (".db", ".sqlite", ".sqlite3"):
        entries = sqlite_format.extract_sqlite(p, fid)
        fmt, meta = "sqlite", {}
    elif suffix in (".bytes", ".dat", ".bin", ".save", ".datas", ""):
        # 伪装/无扩展名：按内容路由（魔数 → 文本/容器；其余回退 txt）
        entries, fmt, meta = _parse_by_content(raw, p, fid)
    else:
        # 未知扩展名（.subs/.langs/自定义文本变体等）：扩展名不是唯一
        # 依据——按内容路由，JSON/XML 内容按结构化解析（否则 txt 行
        # 拆分会把 JSON 行拆成半行条目，写回破坏文件）
        entries, fmt, meta = _parse_by_content(raw, p, fid)
    # 智能过滤：纯数字/URL/路径/程序集名/引擎字符串等标记为跳过（保留条目保证写回完整性）
    for e in entries:
        if e.status == "pending" and (should_skip(e.original) or is_engine_string(e.original)):
            e.status = STATUS_SKIPPED
    noise = looks_like_noise_file(entries)
    return ParsedFile(fid, str(p), fmt, entries, encoding, eol, meta, noise)


def _parse_compressed(raw: bytes, p: Path, fid: str):
    """GZip 内容：解压（≤100MB）后按内容路由；二进制解压产物降级为空。"""
    try:
        data = gzip.decompress(raw)
    except (OSError, EOFError):
        return [], "txt", {}
    if len(data) > 100 * 1024 * 1024:
        return [], "txt", {}
    return _parse_by_content(data, p, fid)


def _parse_by_content(raw: bytes, p: Path, fid: str):
    """内容路由：文本 → JSON/XML/TXT；容器 → ZIP/SQLite；其余为空。"""
    kind = probe_head_kind(raw[:8192])
    if kind == "zip":
        entries, meta = zip_format.extract_zip(io.BytesIO(raw), fid)
        return entries, "zip", meta
    if kind == "sqlite":
        return _extract_sqlite_bytes(raw, p, fid)
    if kind == "text":
        text = _decode_text(raw)
        stripped = text.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                return json_format.extract_json_text(text, fid), "json", {}
            except Exception:  # noqa: BLE001
                pass
        if stripped.startswith("<") and "<" in text[:512]:
            try:
                entries = xml_format.extract_xml_text(text, fid)
                if entries:
                    return entries, "xml", {}
            except Exception:  # noqa: BLE001
                pass
        return _extract_txt_text(text, fid), "txt", {}
    return [], "txt", {}


def _extract_sqlite_bytes(raw: bytes, p: Path, fid: str):
    import tempfile
    import os
    handle = None
    try:
        handle = tempfile.NamedTemporaryFile(prefix="hanhua_sql_", suffix=".db",
                                             delete=False)
        handle.write(raw)
        handle.close()
        return sqlite_format.extract_sqlite(handle.name, fid), "sqlite", {}
    except Exception:  # noqa: BLE001
        return [], "sqlite", {}
    finally:
        if handle is not None:
            try:
                os.unlink(handle.name)
            except OSError:
                pass


def _decode_text(raw: bytes) -> str:
    import chardet
    det = chardet.detect(raw)
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


def _extract_txt_text(text: str, fid: str) -> list[TextEntry]:
    """txt 文本直取（无临时文件）：与 txt_format.extract_txt 相同的行分类。"""
    entries: list[TextEntry] = []
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        meta = {"line_no": i, "raw": line}
        if not stripped:
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "blank"}))
        elif stripped.startswith("#") or stripped.startswith(";"):
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "comment"}))
        elif (stripped.startswith("//")
              and (len(stripped) == 2 or stripped[2].isspace())):
            # C# 风格注释行（与 txt_format 对齐；// 后跟空白才是注释，
            # 协议相对 URL //host 无空白已在 is_hard_structural 处理）
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "comment"}))
        elif stripped.startswith("[") and stripped.endswith("]"):
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "section"}))
        else:
            from hanhua.core.formats import txt_format as _txt
            m = _txt._TAB.match(line) or _txt._KV.match(line)
            if m:
                value = m.group("value").strip()
                delim = "\t" if m.re is _txt._TAB else m.group("delim")
                if not value:
                    # 空值 kv 行（nolog= / key= 空参数）：配置项置空，不是文本。
                    # 与 txt_format.extract_txt 对齐（否则 nolog= 落 plain 被模型
                    # 回显 → untranslated_text 恒败，backrooms boot.config 实证）。
                    entries.append(TextEntry(
                        file_id=fid, key_path=f"kv/{m.group('key').strip()}/{i}",
                        original=value, status=STATUS_SKIPPED,
                        meta={**meta, "kind": "kv_empty",
                              "key": m.group("key"), "delim": delim}))
                elif should_skip(value):
                    # _TAB 正则无 delim 组，不能无条件 group("delim")
                    # （Daggerfall Unity 的 TAB 分隔 kv 行实测 IndexError）
                    entries.append(TextEntry(
                        file_id=fid, key_path=f"kv/{m.group('key').strip()}/{i}",
                        original=value, status=STATUS_SKIPPED,
                        meta={**meta, "kind": "kv_structural",
                              "key": m.group("key"), "delim": delim}))
                else:
                    entries.append(TextEntry(
                        file_id=fid, key_path=f"kv/{m.group('key').strip()}/{i}",
                        original=value,
                        meta={**meta, "kind": "kv", "key": m.group("key"), "delim": delim}))
            else:
                entries.append(TextEntry(file_id=fid, key_path=f"plain/{i}",
                                         original=line.rstrip("\r"),
                                         meta={**meta, "kind": "plain"}))
    return entries
