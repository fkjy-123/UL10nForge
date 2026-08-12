"""TextAsset 不可提取分类：确认 miss 是数据文件（正确）还是真漏（需提取）。

对每个游戏不可提取的 TextAsset 分类：
- unity_linebreak: Unity 引擎换行字符表（107/269b 特征）
- embedded_zip: BOM + ZIP 容器（A* 导航图等，二进制内部数据）
- utf16: UTF-16 编码文本（可译！需提取）
- base64_data: 长 base64 数据块（二进制编码，非文本）
- binary_high_control: 控制字符占比高（二进制）
- binary_data_rows: 数据行（数字/符号为主）
- short_fragment: 极短（<20b，无完整词）
- wordy_miss: 含完整词但 0 提取（= 真漏，需人工查）
- other
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from UnityPy import Environment

from hanhua.core.scanner import probe_head_kind
from hanhua.core.unity.extractor import _textasset_entries, find_asset_files
from hanhua.core.unity.writer import _dispose_environment

_MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tga", ".psd", ".dds",
          ".exr", ".mp3", ".wav", ".ogg", ".aac", ".m4a", ".flac", ".mp4",
          ".webm", ".ttf", ".otf", ".woff", ".woff2", ".fbx", ".obj",
          ".dll", ".exe", ".so", ".dylib", ".pak", ".resS", ".resource"}
_WORD = re.compile(r"[A-Za-z]{3,}")
_B64 = re.compile(r"[A-Za-z0-9+/=]{40,}")


def classify(raw: bytes) -> str:
    if len(raw) < 8:
        return "short_fragment"
    if raw.startswith(b"\xef\xbb\xbf") and probe_head_kind(raw[3:]) == "zip":
        return "embedded_zip"
    # UTF-16 探测
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf16"
    ctrl = sum(1 for b in raw if b < 0x20 and b not in (0x09, 0x0A, 0x0D))
    if ctrl / len(raw) > 0.05:
        return "binary_high_control"
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        return "non_utf8"
    if text in ("LineBreaking Leading Characters", "LineBreaking Following Characters"):
        return "unity_linebreak"
    lines = text.splitlines()
    if not lines:
        return "empty"
    # base64 数据块：长 base64 token 行
    b64_lines = sum(1 for ln in lines if _B64.search(ln) and not _WORD.search(ln))
    if b64_lines / len(lines) > 0.3:
        return "base64_data"
    alpha = sum(1 for ln in lines
                if sum(c.isalpha() for c in ln) / max(1, len(ln)) >= 0.5)
    if alpha / len(lines) < 0.5:
        return "binary_data_rows"
    # 剩余：含词但 _textasset_entries 没提取出来 = 真漏
    words = sum(1 for ln in lines if _WORD.search(ln))
    if words:
        return "wordy_miss"
    return "other"


def main() -> None:
    root = Path(r"D:\游戏")
    games = sorted(d for d in root.iterdir() if d.is_dir())
    counts = Counter()
    examples: dict[str, list[str]] = {}
    wordy_miss: list[str] = []
    total_miss = 0
    for gi, g in enumerate(games, 1):
        for p in find_asset_files(g):
            if p.suffix.lower() in _MEDIA:
                continue
            env = Environment()
            try:
                env.load([str(p)])
            except Exception:  # noqa: BLE001
                continue
            try:
                for obj in env.objects:
                    if obj.type.name != "TextAsset":
                        continue
                    try:
                        ta = obj.read()
                    except Exception:  # noqa: BLE001
                        counts["read_error"] += 1
                        continue
                    script = getattr(ta, "m_Script", None)
                    if isinstance(script, str):
                        raw = script.encode("utf-8-sig", errors="surrogateescape")
                    elif isinstance(script, bytes):
                        raw = script
                    else:
                        counts["none"] += 1
                        continue
                    if not raw:
                        counts["empty"] += 1
                        continue
                    entries = _textasset_entries("audit", obj.path_id, raw)
                    if entries:
                        continue
                    total_miss += 1
                    c = classify(raw)
                    counts[c] += 1
                    key = f"{g.name}:{p.name}#{obj.path_id} {len(raw)}b"
                    examples.setdefault(c, []).append(key)
                    if c == "wordy_miss":
                        wordy_miss.append(
                            f"{key} head={raw[:100]!r}")
            finally:
                _dispose_environment(env)
        print(f"[{gi}/{len(games)}] {g.name} 累计 miss={total_miss}", flush=True)
    print("\n===== miss 分类 =====", flush=True)
    for k, v in counts.most_common():
        print(f"{k}: {v}", flush=True)
        for ex in examples.get(k, [])[:3]:
            print(f"    {ex}", flush=True)
    if wordy_miss:
        print("\n===== 真漏 wordy_miss =====", flush=True)
        for w in wordy_miss[:30]:
            print(w, flush=True)
    (Path(__file__).resolve().parents[1] / "survey_out" / "_miss_class.json").write_text(
        __import__("json").dumps(
            {"counts": dict(counts), "total_miss": total_miss,
             "wordy_miss": wordy_miss[:100], "examples": {k: v[:5] for k, v in examples.items()}},
            ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
