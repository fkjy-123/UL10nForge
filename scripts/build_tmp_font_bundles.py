# -*- coding: utf-8 -*-
"""把用户导出的 TMP SDF 资产（Unity YAML .asset，粗/中/细三档）转换为
load_tmp_bundle 可读的 UnityFS bundle（以 git 参考 arialuni bundle 为
骨架——保留 m_Script/Material/Shader 引用与容器版本，只替换字形数据、
字符表与图集像素）。

输出 3 档 × 4 版本：
  fonts/TMP_Font_AssetBundles/sourcehan_sdf_{heavy|medium|thin}_{u2019|u2021|u2022|u6000}

用法：
  python scripts/build_tmp_font_bundles.py [--ref-dir .ref_fonts]
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
FONTS = REPO / "fonts"
OUT_DIR = FONTS / "TMP_Font_AssetBundles"
DEFAULT_REF_DIR = REPO / ".ref_fonts"

WEIGHTS = {
    "heavy": "SourceHanSansSC-Heavy SDF.asset",
    "medium": "SourceHanSansSC-Medium SDF.asset",
    "thin": "SourceHanSansSC-Thin SDF.asset",
}
# 版本骨架：参考 bundle 名 → 输出 bundle 名
VERSIONS = {
    "u2019": "arialuni_sdf_u2019",
    "u2021": "arialuni_sdf_u2021",
    "u2022": "arialuni_sdf_u2022",
    "u6000": "arialuni_sdf_u6000",
}

# 从用户 .asset 复制进骨架的顶层字段（骨架里必须存在；其余忽略）
_COPY_TOP_FIELDS = (
    "m_FaceInfo", "m_GlyphTable", "m_CharacterTable",
    "m_AtlasTextureIndex", "m_AtlasWidth", "m_AtlasHeight",
    "m_AtlasPadding", "m_AtlasRenderMode", "m_AtlasPopulationMode",
    "m_UsedGlyphRects", "m_FreeGlyphRects", "m_Version",
    "m_IsMultiAtlasTexturesEnabled", "m_ClearDynamicDataOnBuild",
)
# 骨架缺 m_ClassDefinitionType（u2019/TMP 2.1）时从 glyph 移除
_GLYPH_KEYS_WITH_CDT = {"m_AtlasIndex", "m_ClassDefinitionType",
                        "m_GlyphRect", "m_Index", "m_Metrics", "m_Scale"}


class _UnityLoader(yaml.SafeLoader):
    """Unity YAML：!u! tag 直接当作普通映射构造。"""


_UnityLoader.add_multi_constructor(
    "tag:unity3d.com,2011:",
    lambda loader, tag_suffix, node: loader.construct_mapping(node))


def parse_asset(path: Path) -> dict:
    """解析 .asset → 按对象类型分组的 dict {type_id: object_dict}。

    Unity 文件的 %TAG 指令只在文件头声明，PyYAML 对后续文档的
    `!u!NNN` tag handle 作用域处理会报 undefined——文本层直接剥掉
    tag（对象类型用内容字段区分，不需要 tag）。
    """
    import re
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^--- !u!\d+", "---", text, flags=re.M)
    docs = list(yaml.load_all(text, Loader=_UnityLoader))
    out: dict[str, dict] = {}
    for doc in docs:
        if isinstance(doc, dict):
            out.update(doc)
    return out


def extract_font_and_atlas(asset: dict) -> tuple[dict, bytes]:
    """提取 TMP_FontAsset 字段 dict 与图集原始像素（_typelessdata hex）。"""
    font = None
    for obj in asset.values():
        if (isinstance(obj, dict) and obj.get("m_GlyphTable") is not None
                and obj.get("m_CharacterTable") is not None):
            font = obj
            break
    if font is None:
        raise ValueError("未找到 TMP_FontAsset 对象")
    tex = None
    for obj in asset.values():
        if (isinstance(obj, dict)
                and obj.get("m_TextureFormat") is not None
                and obj.get("_typelessdata")):
            tex = obj
            break
    if tex is None:
        raise ValueError("未找到 Texture2D 图集对象")
    hexdata = tex["_typelessdata"]
    if not isinstance(hexdata, str):
        raise ValueError("图集 _typelessdata 不是 hex 字符串")
    pixels = bytes.fromhex(hexdata)
    expected = int(tex.get("m_CompleteImageSize") or len(pixels) // 2)
    if len(pixels) != expected:
        raise ValueError(
            f"图集像素长度不匹配: got {len(pixels)} expected {expected}")
    return font, pixels


def convert_glyphs(user_glyphs: list, skeleton_keys: set[str],
                   has_cdt: bool) -> list:
    """用户 glyph 列表 → 骨架字段结构（缺 m_ClassDefinitionType 时剔除）。"""
    out = []
    for g in user_glyphs:
        item = dict(g)
        if not has_cdt:
            item.pop("m_ClassDefinitionType", None)
        # 骨架键集合与用户键一致时原样保留；未知键剔除防序列化错位
        out.append({k: item[k] for k in skeleton_keys if k in item})
    return out


def convert_chars(user_chars: list) -> list:
    return [dict(c) for c in user_chars]


def fill_skeleton(ref_file: Path, out_file: Path, font: dict,
                  pixels: bytes, weight_name: str) -> None:
    """复制骨架 bundle → 填入用户数据 → 保存到 out_file。"""
    shutil.copyfile(ref_file, out_file)
    from UnityPy import Environment
    env = Environment()
    env.load([str(out_file)])
    glyph_keys = None
    changed = 0
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            tree = obj.read_typetree()
            if tree.get("m_GlyphTable") is None:
                continue
            has_cdt = any(
                "m_ClassDefinitionType" in g for g in tree["m_GlyphTable"])
            if glyph_keys is None:
                glyph_keys = set(
                    (tree["m_GlyphTable"] or [{}])[0].keys())
            for k in _COPY_TOP_FIELDS:
                if k in tree and k in font:
                    tree[k] = font[k]
            tree["m_GlyphTable"] = convert_glyphs(
                font["m_GlyphTable"], glyph_keys, has_cdt)
            tree["m_CharacterTable"] = convert_chars(
                font["m_CharacterTable"])
            tree["m_Name"] = f"SourceHanSansSC-{weight_name} SDF"
            obj.save_typetree(tree)
            changed += 1
        elif obj.type.name == "Texture2D":
            t = obj.read_typetree()
            t["image data"] = pixels
            t["m_Width"] = 4096
            t["m_Height"] = 4096
            t["m_CompleteImageSize"] = len(pixels)
            t["m_StreamData"] = {"offset": 0, "size": 0, "path": ""}
            obj.save_typetree(t)
            changed += 1
    if changed == 0:
        raise ValueError(f"骨架 {ref_file.name} 没有可填对象")
    env.save(pack="lz4", out_path=str(out_file.parent))
    env.__del__() if hasattr(env, "__del__") else None


def main() -> int:
    ref_dir = Path(sys.argv[sys.argv.index("--ref-dir") + 1]
                   if "--ref-dir" in sys.argv else DEFAULT_REF_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for weight, asset_name in WEIGHTS.items():
        asset = parse_asset(FONTS / asset_name)
        font, pixels = extract_font_and_atlas(asset)
        print(f"{asset_name}: chars={len(font['m_CharacterTable'])} "
              f"glyphs={len(font['m_GlyphTable'])} atlas={len(pixels) >> 20}MB")
        for version, ref_name in VERSIONS.items():
            ref = ref_dir / ref_name
            if not ref.is_file():
                print(f"  SKIP {version}: 骨架缺失 {ref.name}")
                continue
            out = OUT_DIR / f"sourcehan_sdf_{weight}_{version}"
            fill_skeleton(ref, out, font, pixels, weight.title())
            size = out.stat().st_size >> 20
            print(f"  {out.name}: {size}MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
