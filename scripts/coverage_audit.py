"""识别覆盖率审计：全量游戏的文本位置提取成功率。

统计每个游戏的：
- TextAsset 对象：总数、m_Script 为 str 的（老 Unity，修复后兼容）、
  为 bytes/None 的；按 _textasset_entries 实测能提取条目的比例
- 外部文本文件：TEXT_EXTENSIONS 命中 + 内容路由可解析
- 容器：可解析数 / 总数
- DLL/metadata：mono / IL2CPP 状态

输出 _coverage.json（每游戏 + 汇总），用于阶段 3 覆盖率 ≥95% 证据。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from UnityPy import Environment
from hanhua.core.scanner import (TEXT_EXTENSIONS, _BINARY_SUFFIXES,
                                 probe_head_kind)
from hanhua.core.unity.extractor import _textasset_entries, find_asset_files
from hanhua.core.unity.writer import _dispose_environment

_MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tga", ".psd", ".dds",
          ".exr", ".mp3", ".wav", ".ogg", ".aac", ".m4a", ".flac", ".mp4",
          ".webm", ".ttf", ".otf", ".woff", ".woff2", ".fbx", ".obj",
          ".dll", ".exe", ".so", ".dylib", ".pak", ".resS", ".resource"}


def audit_game(name: str, src: Path) -> dict:
    out = {
        "game": name,
        "containers": 0,
        "container_ok": 0,
        "textasset_total": 0,
        "textasset_str": 0,       # m_Script 为 str（老 Unity）
        "textasset_bytes": 0,
        "textasset_none": 0,
        "textasset_extractable": 0,  # 实测 _textasset_entries 非空
        "textasset_sample_miss": [],
        "text_files": 0,
        "text_files_routed": 0,   # 内容路由成功（含 .subs 等变体）
        "mono_dlls": 0,
        "il2cpp": False,
    }
    # 外部文本文件：扩展名命中 + 内容探测
    for p in src.rglob("*"):
        if not p.is_file() or p.is_symlink():
            continue
        rel = str(p.relative_to(src)).lower()
        if "/mono/" in rel or "_data/managed/" in rel or "burstdebug" in rel:
            continue
        ext = p.suffix.lower()
        if ext in _MEDIA or ext in _BINARY_SUFFIXES:
            continue
        if p.stat().st_size > 50 * 1e6:
            continue
        if ext in TEXT_EXTENSIONS or not ext:
            out["text_files"] += 1
            kind = probe_head_kind(p.read_bytes()[:8192])
            if kind in ("text", "zip", "sqlite", "unity", "serialized",
                        "webfile", "lz4", "gzip", "zstd"):
                out["text_files_routed"] += 1
        else:
            kind = probe_head_kind(p.read_bytes()[:8192])
            if kind == "text":
                out["text_files"] += 1
                out["text_files_routed"] += 1
    # 容器 TextAsset 审计
    for p in find_asset_files(src):
        if p.suffix.lower() in _MEDIA:
            continue
        env = Environment()
        try:
            env.load([str(p)])
        except Exception:  # noqa: BLE001
            continue
        out["containers"] += 1
        out["container_ok"] += 1
        try:
            for obj in env.objects:
                if obj.type.name != "TextAsset":
                    continue
                out["textasset_total"] += 1
                try:
                    ta = obj.read()
                except Exception:  # noqa: BLE001
                    out["textasset_none"] += 1
                    continue
                script = getattr(ta, "m_Script", None)
                if isinstance(script, str):
                    out["textasset_str"] += 1
                    raw = script.encode("utf-8-sig", errors="surrogateescape")
                elif isinstance(script, bytes):
                    out["textasset_bytes"] += 1
                    raw = script
                else:
                    out["textasset_none"] += 1
                    continue
                try:
                    entries = _textasset_entries(
                        "audit", obj.path_id, raw or b"")
                except Exception:  # noqa: BLE001
                    entries = []
                if entries:
                    out["textasset_extractable"] += 1
                elif len(out["textasset_sample_miss"]) < 3:
                    out["textasset_sample_miss"].append(
                        f"{p.name}#{obj.path_id} {len(raw)}b")
        finally:
            _dispose_environment(env)
    out["mono_dlls"] = len(list(src.rglob("Managed/*.dll")))
    out["il2cpp"] = any(src.rglob("il2cpp_data/Metadata/global-metadata.dat"))
    return out


def main() -> int:
    root = Path(r"D:\游戏")
    out_dir = Path(__file__).resolve().parents[1] / "survey_out"
    out_dir.mkdir(exist_ok=True)
    games = sorted(d for d in root.iterdir() if d.is_dir())
    print(f"共 {len(games)} 个游戏", flush=True)
    rows = []
    for i, g in enumerate(games, 1):
        print(f"[{i}/{len(games)}] {g.name}", flush=True)
        try:
            r = audit_game(g.name, g)
        except Exception as exc:  # noqa: BLE001
            r = {"game": g.name, "error": f"{type(exc).__name__}: {exc}"}
        rows.append(r)
        if "error" not in r:
            print(
                f"  TA={r['textasset_total']} (str={r['textasset_str']} "
                f"bytes={r['textasset_bytes']}) "
                f"可提取={r['textasset_extractable']} "
                f"文本文件={r['text_files']}/{r['text_files_routed']} "
                f"容器={r['container_ok']}/{r['containers']}",
                flush=True)
    ok = [r for r in rows if "error" not in r]
    sum_ta = sum(r["textasset_total"] for r in ok)
    sum_ext = sum(r["textasset_extractable"] for r in ok)
    sum_tf = sum(r["text_files"] for r in ok)
    sum_tr = sum(r["text_files_routed"] for r in ok)
    sum_c = sum(r["container_ok"] for r in ok)
    sum_cc = sum(r["containers"] for r in ok)
    report = {
        "games": len(games),
        "ok": len(ok),
        "failed": [r["game"] for r in rows if "error" in r],
        "textasset_total": sum_ta,
        "textasset_extractable": sum_ext,
        "textasset_rate": round(sum_ext / max(1, sum_ta), 4),
        "textasset_str_total": sum(r["textasset_str"] for r in ok),
        "text_files": sum_tf,
        "text_files_routed": sum_tr,
        "text_file_rate": round(sum_tr / max(1, sum_tf), 4),
        "containers": sum_cc,
        "container_ok": sum_c,
        "container_rate": round(sum_c / max(1, sum_cc), 4),
        "mono_games": sum(1 for r in ok if r["mono_dlls"]),
        "il2cpp_games": sum(1 for r in ok if r["il2cpp"]),
        "sample_miss": [m for r in ok for m in r["textasset_sample_miss"]][:20],
    }
    (out_dir / "_coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n===== 覆盖率汇总 =====", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
