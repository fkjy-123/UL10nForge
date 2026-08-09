"""全量游戏字体审计（只读）：找出所有会「口口口口」的字体。

对 D:\\游戏 每个 Unity 游戏：遍历全部 Unity 容器（.assets/level*/bundle…），
统计：
- legacy Font 对象：m_FontData 内嵌 TTF 的 CJK 覆盖（解析 cmap）
- TMP_FontAsset：布局代（tmp1/tmp2/tmp3）、字形数、字符表 CJK 覆盖
- 图集流数据形态（内嵌 archive: / 外部 .resS）

输出: D:\\游戏\\_font_audit.json
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ttf_cjk_check import _CJK_SAMPLE, _SAMPLE_CODES, parse_cmap_codepoints

from UnityPy import Environment
from hanhua.core.unity.writer import _dispose_environment

_ASSET_SUFFIXES = {".assets", ".bundle", ".unity3d", ".u3d", ".dat", ".ab"}
_NO_EXT_NAMES = {"level", "maindata", "globalgamemanagers"}
_MIN_CONTAINER_BYTES = 4096


def _asset_candidates(game_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for root in game_dir.rglob("*"):
        if not root.is_file() or root.stat().st_size < _MIN_CONTAINER_BYTES:
            continue
        name = root.name.casefold()
        is_level = name.startswith("level") and name[5:].isdigit()
        if (root.suffix.casefold() in _ASSET_SUFFIXES
                or name in _NO_EXT_NAMES or is_level):
            candidates.append(root)
    excluded = {"monobleedingedge", "il2cpp_data", "bee_data", "resources/unity",
                "_builtin_extra", "streamingassets/aa/catalogs"}
    return [c for c in candidates
            if not any(part.casefold() in excluded for part in c.parts)]


def _font_data_info(tree: dict) -> dict | None:
    fd = tree.get("m_FontData")
    if not isinstance(fd, list) or len(fd) < 256:
        return None
    data = bytes(fd)
    if data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf") \
            and data[:2] != b"\x00\x01":
        return None
    cps = parse_cmap_codepoints(data)
    covered = sum(1 for c in _SAMPLE_CODES if c in cps)
    return {
        "data_size": len(data),
        "magic": data[:4].hex(),
        "cjk_covered": covered,
        "cjk_total": len(_SAMPLE_CODES),
        "coverage_pct": round(covered / len(_SAMPLE_CODES) * 100, 1),
    }


def _tmp_chars(tree: dict) -> list[int]:
    """从 TMP 字符表提取 unicode 码点（tmp1/tmp2/tmp3 兼容）。"""
    chars: list[int] = []
    for field in ("m_CharacterTable", "m_characterTable"):
        table = tree.get(field)
        if isinstance(table, list):
            for item in table:
                if isinstance(item, dict):
                    u = item.get("m_Unicode")
                    if isinstance(u, int):
                        chars.append(u)
                    elif isinstance(item.get("m_Unicode"), str):
                        try:
                            chars.append(int(str(item["m_Unicode"]), 16))
                        except ValueError:
                            pass
    return chars


def audit_container(path: Path, per_font_cb) -> None:
    env = Environment()
    try:
        env.load([str(path)])
        seen: set[tuple[str, int]] = set()
        for obj in env.objects:
            key = (obj.type.name, obj.path_id)
            if key in seen:
                continue
            seen.add(key)
            tname = obj.type.name
            if tname == "Font":
                try:
                    tree = obj.read_typetree()
                except Exception:
                    continue
                info = _font_data_info(tree)
                if info:
                    per_font_cb("legacy", obj, info)
            elif tname == "MonoBehaviour":
                try:
                    tree = obj.read_typetree()
                except Exception:
                    continue
                layout = None
                glyphs = 0
                if "m_GlyphTable" in tree:
                    layout = "tmp2"
                    glyphs = len(tree["m_GlyphTable"] or [])
                elif "m_glyphInfoList" in tree:
                    layout = "tmp1"
                    glyphs = len(tree["m_glyphInfoList"] or [])
                elif "m_Material" in tree and "m_CreationSettings" in tree:
                    layout = "tmp3"
                if layout is None:
                    continue
                chars = _tmp_chars(tree)
                cjk_chars = sum(1 for c in chars if 0x4E00 <= c <= 0x9FFF)
                per_font_cb("tmp", obj, {
                    "layout": layout,
                    "glyphs": glyphs,
                    "chars": len(chars),
                    "cjk_chars": cjk_chars,
                    "name": tree.get("m_Name", ""),
                })
    except Exception as exc:
        per_font_cb("container_error", None, {"error": str(exc)[:200]})
    finally:
        _dispose_environment(env)


def audit_game(game_dir: Path, time_budget_s: float = 300.0) -> dict:
    started = time.monotonic()
    result: dict = {
        "game": game_dir.name,
        "containers": 0,
        "legacy_fonts": [],
        "tmp_fonts": [],
        "container_errors": [],
        "elapsed_s": 0.0,
        "timeout": False,
    }
    for path in _asset_candidates(game_dir):
        if time.monotonic() - started > time_budget_s:
            result["timeout"] = True
            break
        result["containers"] += 1

        def cb(kind, obj, info):
            if kind == "container_error":
                result["container_errors"].append(f"{path.name}: {info['error']}")
                return
            rel = str(path.relative_to(game_dir)).replace("\\", "/")
            entry = {**info, "path": rel}
            if kind == "legacy":
                result["legacy_fonts"].append(entry)
            else:
                result["tmp_fonts"].append(entry)

        audit_container(path, cb)
    result["elapsed_s"] = round(time.monotonic() - started, 1)
    return result


def main() -> None:
    base = Path(r"D:\游戏")
    survey = json.loads((base / "_survey.json").read_text(encoding="utf-8"))
    games = [r["name"] for r in survey if r["unity"]]
    out = []
    t0 = time.monotonic()
    for i, name in enumerate(games, 1):
        game_dir = base / name
        if not game_dir.is_dir():
            continue
        print(f"[{i}/{len(games)}] {name} ...", flush=True)
        try:
            out.append(audit_game(game_dir))
        except Exception as exc:  # noqa: BLE001
            out.append({"game": name, "fatal": str(exc)[:300]})
        (base / "_font_audit.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  done ({out[-1].get('elapsed_s')}s, "
              f"legacy={len(out[-1].get('legacy_fonts', []))}, "
              f"tmp={len(out[-1].get('tmp_fonts', []))})", flush=True)
    print(f"TOTAL {round(time.monotonic() - t0, 1)}s -> {base / '_font_audit.json'}")


if __name__ == "__main__":
    main()
