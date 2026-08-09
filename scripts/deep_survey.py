"""深度调查：D:\\游戏 全量游戏的文本位置普查（只读，不写任何文件到游戏内）。

多方法交叉，输出每游戏 JSON 指纹 + 汇总报告：
A. 文件系统普查：扩展名分布、命名模式、无扩展名文件、异常头（加密/混淆）
B. Unity 容器解析：UnityPy 全量 load → 对象类型分布、TextAsset/MonoBehaviour
   文本量、AssetBundle 嵌套
C. 字节级盲扫：非容器文件 UTF-8/UTF-16-LE 可读串统计（找格式外文本）
D. 运行时检测：IL2CPP（global-metadata）/ mono（Managed/*.dll）状态

产出：survey_out/<game>.json + 汇总报告。供识别模块升级（阶段 3）确定缺口。
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from UnityPy import Environment
from hanhua.core.unity.writer import _dispose_environment

# 媒体扩展名：绝无文本，跳过 UnityPy 解析与盲扫
_MEDIA_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tga", ".psd", ".dds", ".exr",
    ".mp3", ".wav", ".ogg", ".aac", ".m4a", ".flac", ".wma", ".webm",
    ".mp4", ".avi", ".mov", ".wmv", ".fbx", ".obj", ".blend", ".max",
    ".dll", ".exe", ".so", ".dylib", ".pak", ".tres", ".ttf", ".otf",
    ".eot", ".woff", ".woff2", ".dat", ".bin", ".bytes",
}
# 已知文本/容器扩展名：必做 UnityPy 尝试
_CONTAINER_EXTS = {
    ".assets", ".unity3d", ".bundle", ".asset", ".resS", ".resource",
    ".ress", ".ab", ".u3d", ".upk",
}
# 命名模式：命中即高概率文本文件
_NAME_PATTERNS = [
    r"locali[sz]", r"language", r"lang_", r"\blang\b", r"strings",
    r"translat", r"\bi18n\b", r"\bi2\b", r"\btext\b", r"\bui\b",
    r"dialog", r"dialogue", r"subtitles", r"subtitle", r"\bpo\b", r"\.csv$",
]
_UNITY_MAGICS = (b"UnityFS", b"UnityWeb", b"UnityRaw", b"UnityArchive", b"PK\x03\x04")


def _name_hint(rel: str) -> bool:
    low = rel.lower()
    return any(re.search(p, low) for p in _NAME_PATTERNS)


def _readable_strings(blob: bytes, min_len: int = 4) -> int:
    """统计 UTF-8 可读串数量（粗略文本量估计）。"""
    n = 0
    for m in re.finditer(rb"[ -~]{4,}", blob):
        n += 1
    return n


def _head_magic(p: Path) -> str | None:
    try:
        with p.open("rb") as f:
            head = f.read(16)
    except OSError:
        return None
    if head.startswith(_UNITY_MAGICS):
        return "unity-ok"
    if head.startswith(b"#$unity3dchina!@"):
        return "unitycn-encrypted"
    if head[:1] in (b"{", b"[", b"<") or head.startswith(b"\xef\xbb\xbf"):
        return "text-ok"
    if b"\x00" in head:
        return "binary-unknown"
    return "suspicious"


def survey_game(game_name: str, src: Path) -> dict:
    t0 = time.time()
    out = {
        "game": game_name,
        "files": 0,
        "size_mb": 0.0,
        "ext_counter": {},
        "no_ext_files": [],
        "name_hits": [],
        "container_ok": 0,
        "container_fail": [],
        "suspicious_heads": [],
        "unitycn_heads": [],
        "object_types": Counter(),
        "textasset_total_chars": 0,
        "textasset_samples": [],
        "mb_string_objects": 0,
        "mb_sample_paths": [],
        "streaming_files": [],
        "il2cpp": None,
        "mono_dlls": [],
        "blobscan_hits": [],
        "scan_ms": 0,
    }
    try:
        env = Environment()
        seen_containers: set[Path] = set()
        for p in sorted(src.rglob("*")):
            if not p.is_file() or p.is_symlink():
                continue
            rel = p.relative_to(src)
            out["files"] += 1
            out["size_mb"] += p.stat().st_size / 1e6
            ext = p.suffix.lower()
            if ext:
                out["ext_counter"][ext] = out["ext_counter"].get(ext, 0) + 1
            else:
                out["no_ext_files"].append(rel.as_posix())
            if _name_hint(rel.as_posix()):
                out["name_hits"].append(rel.as_posix())
            if p.parent.name == "StreamingAssets":
                out["streaming_files"].append(rel.as_posix())
            if ext in _MEDIA_EXTS:
                continue
            # 加密/异常头检测（bundle/container 类 + 无扩展名文件）。
            # .resS/.resource 本身是无头原始数据（正常），排除
            if (ext in _CONTAINER_EXTS or not ext) and ext not in (
                    ".ress", ".resource"):
                magic = _head_magic(p)
                if magic == "unitycn-encrypted":
                    out["unitycn_heads"].append(rel.as_posix())
                elif magic == "suspicious" and p.stat().st_size > 4096:
                    out["suspicious_heads"].append(rel.as_posix())
            # Unity 容器解析
            if ext in _CONTAINER_EXTS or not ext or _name_hint(rel.as_posix()):
                if p in seen_containers:
                    continue
                seen_containers.add(p)
                try:
                    env.load([str(p)])
                    out["container_ok"] += 1
                except Exception:  # noqa: BLE001
                    out["container_fail"].append(rel.as_posix())
                    continue
                for obj in env.objects:
                    tname = obj.type.name
                    out["object_types"][tname] += 1
                    if tname == "TextAsset":
                        try:
                            ta = obj.read()
                            script = getattr(ta, "script", None)
                            if isinstance(script, (bytes, bytearray)):
                                txt = bytes(script).decode(
                                    "utf-8", errors="ignore")
                            else:
                                txt = getattr(ta, "m_Script", "") or ""
                            out["textasset_total_chars"] += len(txt)
                            if len(out["textasset_samples"]) < 3:
                                name = getattr(ta, "m_Name", "") or rel.as_posix()
                                out["textasset_samples"].append(
                                    f"{name}:{len(txt)}c:{txt[:80]!r}")
                        except Exception:  # noqa: BLE001
                            pass
                    elif tname == "MonoBehaviour":
                        out["mb_string_objects"] += 1
                        if len(out["mb_sample_paths"]) < 5:
                            out["mb_sample_paths"].append(rel.as_posix())
        # 字节盲扫：非媒体、非容器解析失败/未尝试的较大文件
        for p in sorted(src.rglob("*")):
            if not p.is_file() or p.is_symlink():
                continue
            ext = p.suffix.lower()
            if ext in _MEDIA_EXTS:
                continue
            size = p.stat().st_size
            if size > 20 * 1e6 or size < 1024:
                continue
            rel = p.relative_to(src)
            posix = rel.as_posix().lower()
            # 引擎噪声：mono 运行时配置 / Unity API 文档 / Burst 调试信息
            if "/mono/" in posix or posix.startswith("mono/"):
                continue
            if "_data/managed/" in posix and posix.endswith(".xml"):
                continue
            if "burstdebuginformation" in posix:
                continue
            try:
                blob = p.read_bytes()
            except OSError:
                continue
            n = _readable_strings(blob)
            if n >= 8:
                out["blobscan_hits"].append(f"{rel.as_posix()}:{n}str")
        # 运行时检测
        for cand in src.rglob("global-metadata.dat"):
            out["il2cpp"] = {"version_hint": "found", "size": cand.stat().st_size}
        for cand in src.rglob("*.dll"):
            if "Managed" in str(cand):
                out["mono_dlls"].append(cand.relative_to(src).as_posix())
    finally:
        _dispose_environment(env)
    out["scan_ms"] = int((time.time() - t0) * 1000)
    # Counter → dict（JSON 序列化）
    out["object_types"] = dict(out["object_types"].most_common(30))
    # 截断样本，防输出过大
    out["name_hits"] = out["name_hits"][:40]
    out["streaming_files"] = out["streaming_files"][:20]
    out["blobscan_hits"] = out["blobscan_hits"][:40]
    out["no_ext_files"] = out["no_ext_files"][:40]
    out["container_fail"] = out["container_fail"][:40]
    out["suspicious_heads"] = out["suspicious_heads"][:20]
    out["unitycn_heads"] = out["unitycn_heads"][:10]
    return out


def main() -> int:
    root = Path(r"D:\游戏")
    out_dir = Path(__file__).resolve().parents[1] / "survey_out"
    out_dir.mkdir(exist_ok=True)
    games = sorted(d for d in root.iterdir() if d.is_dir())
    print(f"共 {len(games)} 个游戏目录", flush=True)
    summary = []
    for i, g in enumerate(games, 1):
        print(f"[{i}/{len(games)}] {g.name} ...", flush=True)
        try:
            r = survey_game(g.name, g)
        except Exception as exc:  # noqa: BLE001
            r = {"game": g.name, "error": f"{type(exc).__name__}: {exc}"}
        (out_dir / f"{g.name}.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        summary.append(r)
        if "error" in r:
            print(f"  失败: {r['error']}", flush=True)
        else:
            print(
                f"  文件={r['files']} 容器OK={r['container_ok']} "
                f"容器失败={len(r['container_fail'])} 对象={sum(r['object_types'].values())} "
                f"TextAsset={r['object_types'].get('TextAsset', 0)} "
                f"MonoBehaviour={r['object_types'].get('MonoBehaviour', 0)} "
                f"可疑头={len(r['suspicious_heads'])} 字节盲扫={len(r['blobscan_hits'])} "
                f"IL2CPP={'Y' if r['il2cpp'] else 'N'} {r['scan_ms']}ms",
                flush=True)
    # 汇总报告
    report = {
        "games": len(games),
        "ok": sum(1 for r in summary if "error" not in r),
        "failed": [r["game"] for r in summary if "error" in r],
        "total_files": sum(r.get("files", 0) for r in summary),
        "total_size_gb": round(sum(r.get("size_mb", 0) for r in summary) / 1e3, 1),
        "container_ok": sum(r.get("container_ok", 0) for r in summary),
        "container_fail_total": sum(len(r.get("container_fail", [])) for r in summary),
        "all_object_types": dict(Counter(
            t for r in summary for t, c in r.get("object_types", {}).items()
            for _ in range(c)).most_common(40)),
        "textasset_total_chars": sum(r.get("textasset_total_chars", 0) for r in summary),
        "il2cpp_games": [r["game"] for r in summary if r.get("il2cpp")],
        "mono_games": [r["game"] for r in summary if r.get("mono_dlls")],
        "unitycn_games": [r["game"] for r in summary if r.get("unitycn_heads")],
        "suspicious_games": [r["game"] for r in summary
                             if r.get("suspicious_heads")],
        "no_streaming_games": [r["game"] for r in summary
                               if r.get("streaming_files")],
        "blobscan_only_games": [r["game"] for r in summary
                                if r.get("blobscan_hits")],
    }
    (out_dir / "_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n===== 汇总 =====", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=1), flush=True)
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
