"""识别基线探针（无头）：对单个游戏目录跑完整 v2 提取并打印识别统计。

用法：runtime/python/python.exe scripts/_recognition_probe.py <游戏目录> [更多目录...]

输出（每游戏）：
- 形态 × 条目/display/skipped 统计；
- 程序集 #US 堆全集（代码文本精确分母）与已证明 UI 串数；
- typetree 覆盖率；
- skipped 原因分解（哑信号可见化）。

这是 Phase 0 基线 + Phase 3 识别率报告的数据源骨架。
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hanhua.core.models import STATUS_SKIPPED  # noqa: E402
from hanhua.core.unity import extractor as asset_ex  # noqa: E402
from hanhua.core.unity import mono_dll  # noqa: E402


def _count_entries(entries) -> dict:
    c = Counter()
    for e in entries:
        c["total"] += 1
        if e.status == STATUS_SKIPPED:
            c["skipped"] += 1
            c[f"skipped:{e.meta.get('reason', '?')}"] += 1
        else:
            c["pending"] += 1
            c[f"pending:{e.meta.get('reason', '?')}"] += 1
        c[f"conf:{e.meta.get('confidence', '?')}"] += 1
    return dict(c)


def probe_game(game_dir: str) -> dict:
    root = Path(game_dir)
    out: dict = {"name": root.name, "root": str(root),
                 "assets": {}, "mono": {}, "warnings": []}

    # ── Unity 二进制资源 ──
    try:
        asset_files = asset_ex.find_asset_files(root)
    except Exception as exc:  # noqa: BLE001
        asset_files = []
        out["warnings"].append(f"find_asset_files: {exc}")
    ac = Counter()
    typetree_ok = typetree_failed = 0
    for f in asset_files:
        try:
            pf = asset_ex.extract_asset_file(f)
        except Exception as exc:  # noqa: BLE001
            ac["file_error"] += 1
            continue
        ac.update(_count_entries(pf.entries))
        for reason, count in (pf.skipped_reasons or {}).items():
            ac[f"skip_reason:{reason}"] += count
        cov = (pf.meta or {}).get("typetree_coverage")
        nobj = (pf.meta or {}).get("typetree_objects")
        if cov is not None:
            typetree_ok += round(cov * nobj)
            typetree_failed += nobj - round(cov * nobj)
    out["assets"] = dict(ac)
    out["assets"]["files"] = len(asset_files)
    out["assets"]["typetree_ok"] = typetree_ok
    out["assets"]["typetree_failed"] = typetree_failed

    # ── Mono 程序集 ──
    try:
        dll_files = mono_dll.find_dll_files(root)
    except Exception as exc:  # noqa: BLE001
        dll_files = []
        out["warnings"].append(f"find_dll_files: {exc}")
    mc = Counter()
    mc["heap_total"] = 0
    mc["heap_verified_ui"] = 0
    mc["heap_has_space"] = 0
    for f in dll_files:
        try:
            pf = mono_dll.extract_dll_user_strings(f)
        except Exception as exc:  # noqa: BLE001
            mc["file_error"] += 1
            continue
        mc.update(_count_entries(pf.entries))
        for reason, count in (pf.skipped_reasons or {}).items():
            mc[f"skip_reason:{reason}"] += count
        # 分母：该程序集 #US 堆全集（编译器枚举出的精确清单）
        try:
            import dnfile
            pe = dnfile.dnPE(str(f))
            us = pe.net.user_strings
            if us is not None:
                data = us.get_data_at_offset(0, us.sizeof())
                records = mono_dll._walk_us_heap_records(data)
                mc["heap_total"] += len(records)
                verified = mono_dll._verified_ui_user_string_tokens(pe)
                mc["heap_verified_ui"] += len(verified)
                mc["heap_has_space"] += sum(
                    1 for _, _, raw in records
                    if b" " in raw or b"\t" in raw or b"\n" in raw)
        except Exception:  # noqa: BLE001
            pass
    out["mono"] = dict(mc)
    out["mono"]["files"] = len(dll_files)
    return out


def _print(out: dict) -> None:
    print(f"\n===== {out['name']} =====")
    for warn in out["warnings"]:
        print(f"  [WARN] {warn}")
    a = out["assets"]
    if a.get("files"):
        print(f"  assets: {a['files']} 文件 | 条目 {a.get('total', 0)}"
              f"（pending {a.get('pending', 0)} / skipped {a.get('skipped', 0)}）")
        if a.get("typetree_ok") or a.get("typetree_failed"):
            total = a["typetree_ok"] + a["typetree_failed"]
            print(f"    typetree 覆盖: {a['typetree_ok']}/{total}"
                  f"（{a['typetree_ok'] / max(1, total):.0%}）")
        for key in sorted(a):
            if key.startswith("skip_reason:") and a[key] >= 5:
                print(f"    {key} = {a[key]}")
    m = out["mono"]
    if m.get("files"):
        print(f"  mono: {m['files']} 程序集 | 条目 {m.get('total', 0)}"
              f"（pending {m.get('pending', 0)} / skipped {m.get('skipped', 0)}）")
        print(f"    #US 堆全集: {m['heap_total']}"
              f" | 已证明 UI: {m['heap_verified_ui']}"
              f" | 含空格: {m['heap_has_space']}")
        if m.get("heap_total"):
            print(f"    证明率(UI/堆): {m['heap_verified_ui'] / m['heap_total']:.1%}"
                  f" | 含空格率: {m['heap_has_space'] / m['heap_total']:.1%}")
        for key in sorted(m):
            if key.startswith("skip_reason:") and m[key] >= 5:
                print(f"    {key} = {m[key]}")
        print("    skipped 条目原因分解:")
        for key in sorted(m):
            if key.startswith("skipped:") and m[key] >= 3:
                print(f"    {key} = {m[key]}")
    # ── IL2CPP 检测 ──
    root = Path(out.get("root", ""))
    if root.is_dir():
        meta = next(root.rglob("global-metadata.dat"), None)
        has_assembly = (root / "GameAssembly.dll").exists()
        if meta is not None:
            print(f"  il2cpp: metadata {meta.relative_to(root)}"
                  f"（GameAssembly: {'有' if has_assembly else '无'}）")
    print()


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        try:
            out = probe_game(arg)
        except Exception as exc:  # noqa: BLE001
            print(f"===== {arg} =====\n  [ERROR] {exc!r}")
            continue
        _print(out)
