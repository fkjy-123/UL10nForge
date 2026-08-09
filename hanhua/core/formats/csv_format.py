from __future__ import annotations
import csv
import io
from pathlib import Path
from hanhua.core.models import TextEntry
from hanhua.core.formats import read_text

TARGET_LANG_ALIASES = {
    "zh-CN": ("ChineseSimplified", "zh-CN", "zh_Hans", "简体中文",
              "Simplified Chinese", "cn", "zh"),
}

NON_LANG_HEADERS = {"key", "id", "type", "category", "comment", "notes"}


def pick_target_col(header: list[str], target_lang: str) -> int | None:
    aliases = TARGET_LANG_ALIASES.get(target_lang, (target_lang,))
    for i, name in enumerate(header):
        if name.strip() in aliases:
            return i
    return None


def _detect_delimiter(text: str, suffix: str) -> str:
    if suffix == ".tsv":
        return "\t"
    if suffix == ".psv":
        return "|"
    head = text.splitlines()[0] if text.splitlines() else ""
    if "\t" in head:
        return "\t"
    counts = {",": head.count(","), "|": head.count("|"), ";": head.count(";")}
    best = max(counts, key=counts.get)
    # 分号分隔（key;english;russian;german 实证 incremental-rts）：只有
    # 分号时用分号；逗号存在时逗号优先（CSV 字段内的分号更常见）
    if best == ";" and counts[";"] > 0 and counts[","] == 0:
        return ";"
    if counts["|"] > counts[","]:
        return "|"
    return ","


def _read_rows(text: str, delimiter: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def extract_csv(path: str | Path, target_lang: str = "zh-CN", file_id: str | None = None
                ) -> tuple[list[TextEntry], int | None]:
    """I2 Localization 风格（Key 列 + 语言列）或两列 key,value。返回 (条目, 目标列索引或None)。"""
    p = Path(path)
    return extract_csv_text(read_text(p), file_id or p.name,
                            p.suffix.lower(), target_lang)


def looks_like_csv_text(text: str) -> bool:
    """TextAsset 内嵌 CSV 判据：≥2 行且各行列数一致（首行含分隔符）。

    空行（width=0）不计入宽度判定（incremental-rts 实证：695 行 4 列 +
    31 空行，空行会破坏 len(widths)==1）。
    """
    if "\n" not in text and "\r" not in text:
        return False
    delimiter = _detect_delimiter(text, "")
    rows = [r for r in _read_rows(text, delimiter) if r]
    if len(rows) < 2:
        return False
    widths = {len(row) for row in rows}
    return len(widths) == 1 and len(rows[0]) >= 2


def extract_csv_text(text: str, file_id: str | None = None, suffix: str = "",
                     target_lang: str = "zh-CN") -> tuple[list[TextEntry], int | None]:
    """文本直取（TextAsset / zip 内层 / 伪装文件复用）。"""
    fid = file_id or "csv"
    rows = _read_rows(text, _detect_delimiter(text, suffix))
    if not rows:
        return [], None
    header = [h.strip() for h in rows[0]]
    target_col = pick_target_col(header, target_lang)
    lang_cols = [i for i, h in enumerate(header) if h and h.lower() not in NON_LANG_HEADERS]
    # 源语言列选择：语言列中「非空行最多」者（faerie-afterlight 实证：
    # header=key,voice,en,id,sp,... 时 voice 列几乎全空，lang_cols[0] 选错
    # → 0 条目。en 列非空最多才是真正的源文本列）
    if lang_cols:
        source_col = max(
            lang_cols,
            key=lambda c: sum(1 for r in range(1, len(rows))
                              if len(rows[r]) > c and rows[r][c].strip()))
    else:
        source_col = 1
    entries: list[TextEntry] = []
    for r in range(1, len(rows)):
        row = rows[r]
        if len(row) <= source_col or not row[source_col].strip():
            continue
        key = row[0].strip() if row and row[0].strip() else f"row{r}"
        entries.append(TextEntry(
            file_id=fid, key_path=f"row/{r}", original=row[source_col].strip(),
            meta={"row": r, "key": key, "source_col": source_col, "target_col": target_col}))
    return entries, target_col


def apply_csv(entries: list[TextEntry], source_text: str, delimiter: str = ",",
              target_lang: str = "zh-CN", target_col: int | None = None) -> str:
    """重建 CSV：无目标列时在表头追加目标语言列。"""
    rows = _read_rows(source_text, delimiter)
    new_col = target_col is None
    if new_col:
        target_col = len(rows[0])
        alias = TARGET_LANG_ALIASES.get(target_lang, (target_lang,))[0]
        rows[0].append(alias)
    by_row = {e.meta["row"]: e for e in entries}
    for r in range(1, len(rows)):
        e = by_row.get(r)
        if not e or not e.translation:
            if new_col:
                rows[r].append("")
            continue
        if new_col:
            rows[r].append(e.translation)
        else:
            while len(rows[r]) <= target_col:
                rows[r].append("")
            rows[r][target_col] = e.translation
    out = io.StringIO()
    # 保留原始行终止符（与 detect_eol 同判据）：CRLF 文件写回 CRLF，
    # 避免行终止符变化被版本控制/脚本误判（调查报告 2.6 新发现）
    eol = "\r\n" if source_text.count("\r\n") > source_text.count("\n") / 2 else "\n"
    writer = csv.writer(out, delimiter=delimiter, lineterminator=eol)
    writer.writerows(rows)
    return out.getvalue()
