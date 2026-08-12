"""静态字体替换：写回阶段把游戏字体资源换成 CJK 全字库。

两条路径（都作用于写回副本，不碰原游戏）：

1. legacy Font 替换（主路径，覆盖 uGUI Text / 3D TextMesh 主流样本）：
   把 Font 对象内嵌的 ``m_FontData`` TTF 字节整体换成白名单中文字体 TTF。
   Unity 对 dynamic Font 在运行时按 TTF 生成字形图集，替换后拉丁+中文全部可渲染。

2. TMP_FontAsset 替换（版本化 bundle 路径）：
   按游戏 Unity 版本选择 ``fonts/TMP_Font_AssetBundles_2025-12-08`` 中
   对应版本的 ARIALUNI SDF 字体 bundle（u55to2017/u2018=TMP 1.x，
   u2019/u2021/u2022=TMP 2.x，u6000=TMP 3.x），把游戏内 TMP_FontAsset 的
   字形表/字符表/面信息替换为 bundle 字体的，图集 Texture2D 数据同步替换。

安全语义：任何失败只跳过该对象并记录，绝不阻断文本写回；替换后重开验证
（m_FontData == 目标 TTF / m_GlyphTable 数量一致）；外部流图集以追加方式
写入游戏 .resS 文件（不破坏既有流偏移）。
"""
from __future__ import annotations

import os
import re
import struct
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from hanhua.core.models import FontConfig
from hanhua.core.unity.writer import _dispose_environment


_MAJOR_VERSION = re.compile(r"^(\d+)")


@dataclass
class FontReplaceResult:
    replaced: int = 0
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # C5：被整容器重建（os.replace）的文件相对路径——Addressables 管线
    # 下 bundle CRC 已变，catalog.bin 中的 CRC 必须二次同步，否则运行时
    # CRC Mismatch 拒载（write_back_v2 末尾的 catalog 更新早于字体替换）。
    replaced_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TmpBundlePayload:
    """一个版本化 TMP 字体 bundle 解析后的载荷。"""
    bundle_path: Path
    font_name: str
    glyph_count: int
    layout_version: str  # "tmp1" | "tmp2" | "tmp3"
    font_typetree: dict
    atlas_texture: dict          # 图集 Texture2D typetree
    atlas_stream: bytes          # 图集像素流数据（原始字节）
    atlas_width: int
    atlas_height: int
    atlas_format: int


# ── 版本映射 ────────────────────────────────────────────────

def _bundle_dir() -> Path:
    return (Path(__file__).resolve().parents[3] / "fonts"
            / "TMP_Font_AssetBundles_2025-12-08")


def select_tmp_bundle(unity_version: str | None) -> Path | None:
    """按 Unity 主版本选 TMP 字体 bundle；未知版本返回 None。"""
    if not unity_version:
        return None
    major = _MAJOR_VERSION.match(unity_version.strip())
    if not major:
        return None
    major_num = int(major.group(1))
    names = {
        "TMP1": "arialuni_sdf-u55to2017",
        "TMP2": "arialuni_sdf_u2019",
    }
    if major_num <= 2017:
        filename = names["TMP1"]
    elif major_num == 2018:
        filename = "arialuni_sdf_u2018"
    elif major_num <= 2020:
        filename = "arialuni_sdf_u2019"
    elif major_num == 2021:
        filename = "arialuni_sdf_u2021"
    elif major_num == 2022:
        filename = "arialuni_sdf_u2022"
    elif major_num >= 6000:
        filename = "arialuni_sdf_u6000"
    else:
        return None
    bundle = _bundle_dir() / filename
    return bundle if bundle.is_file() else None


def _typetree_layout_version(tree: dict) -> str | None:
    """判定 TMP_FontAsset 布局代：tmp1（m_fontInfo/m_glyphInfoList）/ tmp2/3。"""
    if "m_GlyphTable" in tree:
        return "tmp2"
    if "m_glyphInfoList" in tree:
        return "tmp1"
    return None


def _atlas_stream_meta(tree: dict) -> tuple[str, int, int]:
    """返回图集流 (path, offset, size)；无流数据时 path 为空。"""
    stream = tree.get("m_StreamData") or {}
    path = str(stream.get("path") or "")
    offset = int(stream.get("offset") or 0)
    size = int(stream.get("size") or 0)
    return path, offset, size


def _extract_atlas_bytes(env, atlas_tex, bundle: Path, atlas_tree: dict | None = None) -> bytes:
    """提取图集原始像素字节（仅流数据覆盖的区间，不含同流其他纹理）。

    优先从 bundle 的 ``CAB-xxx.resS`` 子文件按 m_StreamData 区间读取（保真无损）；
    无 resS 子文件/无流时回退 ``image_data``。
    """
    cab = str(atlas_tex.assets_file.name)  # CAB-xxxxxxxx
    bundle_file = None
    for item in env.files.values():
        if type(item).__name__ == "BundleFile":
            bundle_file = item
            break
    path, offset, size = _atlas_stream_meta(atlas_tree or {})
    if bundle_file is not None and path:
        res_name = Path(path).name
        res = bundle_file.files.get(res_name)
        if res is not None:
            reader = res.read() if callable(res.read) else res
            data = reader if isinstance(reader, bytes) else bytes(reader)
            if data and offset + size <= len(data):
                return data[offset:offset + size]
    reader = atlas_tex.read()
    return reader.image_data or b""


def load_tmp_bundle(bundle: Path) -> TmpBundlePayload:
    """解析版本化 TMP 字体 bundle，返回载荷。"""
    from UnityPy import Environment
    env = Environment()
    font_obj = atlas_obj = None
    try:
        env.load([str(bundle)])
        seen: set[tuple[str, int]] = set()
        for obj in env.objects:
            key = (obj.type.name, obj.path_id)
            if key in seen:
                continue
            seen.add(key)
            if obj.type.name == "MonoBehaviour" and font_obj is None:
                tree = obj.read_typetree()
                if _typetree_layout_version(tree) is not None:
                    font_obj = (obj, tree)
            elif obj.type.name == "Texture2D" and atlas_obj is None:
                atlas_obj = (obj, obj.read_typetree())
        if font_obj is None or atlas_obj is None:
            raise ValueError(
                f"TMP 字体 bundle 缺少字体或图集对象: {bundle.name}")
        _, font_tree = font_obj
        atlas_tex, atlas_tree = atlas_obj
        layout = _typetree_layout_version(font_tree)
        glyphs = len(font_tree.get("m_GlyphTable")
                     or font_tree.get("m_glyphInfoList") or [])
        atlas_bytes = _extract_atlas_bytes(env, atlas_tex, bundle, atlas_tree)
        if not atlas_bytes:
            raise ValueError(f"TMP 字体 bundle 图集数据缺失: {bundle.name}")
        return TmpBundlePayload(
            bundle_path=bundle,
            font_name=str(font_tree.get("m_Name", "ARIALUNI SDF")),
            glyph_count=glyphs,
            layout_version=layout,
            font_typetree=font_tree,
            atlas_texture=atlas_tree,
            atlas_stream=atlas_bytes,
            atlas_width=int(atlas_tree.get("m_Width") or 0),
            atlas_height=int(atlas_tree.get("m_Height") or 0),
            atlas_format=int(atlas_tree.get("m_TextureFormat") or 0),
        )
    finally:
        _dispose_environment(env)


# ── legacy Font 替换 ────────────────────────────────────────

def _font_ttf_candidate(config: FontConfig) -> Path | None:
    """白名单中文字体 TTF（写回方负责校验存在性）。"""
    from hanhua.core.font_support import FONT_OPTIONS
    if not config.filename:
        return None
    if config.filename not in FONT_OPTIONS:
        return None
    fonts_dir = _bundle_dir().parent
    candidate = fonts_dir / config.filename
    return candidate if candidate.is_file() else None


def _ttf_has_magic(data: bytes) -> bool:
    return (data[:4] in {b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"}
            or data[:2] == b"\x00\x01")


def _ttf_metrics(data: bytes) -> tuple[float, float, float] | None:
    """解析 TTF head/hhea 表 → (ascent, descent, lineGap)，单位 em（除以 unitsPerEm）。

    用这些值同步 legacy Font 的 m_Ascent/m_Descent/m_LineSpacing：
    Unity 按原字体的度量渲染替换后的 TTF，指标不匹配会把字形错位缩放
    （deadbeat 原 m_Ascent=12 vs 联想小新黑体实际 0.86em）→ 字体模糊。
    """
    if len(data) < 12 or not _ttf_has_magic(data):
        return None
    try:
        num_tables = struct.unpack(">H", data[4:6])[0]
        tables: dict[str, tuple[int, int]] = {}
        for i in range(num_tables):
            off = 12 + i * 16
            if off + 16 > len(data):
                return None
            tag = data[off:off + 4].decode("latin1")
            _checksum, toffset, tlength = struct.unpack(
                ">III", data[off + 4:off + 16])
            tables[tag] = (toffset, tlength)
        head_off, head_len = tables.get("head", (0, 0))
        hhea_off, hhea_len = tables.get("hhea", (0, 0))
        if not (head_off and hhea_off and head_off + 20 <= len(data)
                and hhea_off + 10 <= len(data)):
            return None
        upm = struct.unpack(">H", data[head_off + 18:head_off + 20])[0]
        if not upm:
            return None
        ascent = struct.unpack(">h", data[hhea_off + 4:hhea_off + 6])[0] / upm
        descent = struct.unpack(">h", data[hhea_off + 6:hhea_off + 8])[0] / upm
        line_gap = struct.unpack(">h", data[hhea_off + 8:hhea_off + 10])[0] / upm
        return ascent, descent, line_gap
    except (IndexError, struct.error):
        return None


# 像素字体渲染模式（HintedRaster）：对矢量 TTF 会产生锯齿/块状模糊。
# 替换为平滑渲染（Smooth）提高清晰度。
_FONT_RENDERING_MODE_HINTED_RASTER = 2
_FONT_RENDERING_MODE_SMOOTH = 0


def _patch_font_object(env, font_obj, ttf_bytes: bytes) -> bool:
    """把单个 Font 对象的内嵌 TTF 换成目标 TTF。返回是否替换。

    同时按目标 TTF 的真实度量修正 m_Ascent/m_Descent/m_LineSpacing，
    并把像素字体渲染模式（HintedRaster）改为 Smooth——原字体指标
    与替换 TTF 不匹配是「汉化后字体模糊」的直接根因。
    """
    tree = font_obj.read_typetree()
    font_data = tree.get("m_FontData")
    if not isinstance(font_data, list) or len(font_data) < 256:
        # 无内嵌字体数据（静态位图字体/外部引用）→ 不替换
        return False
    current = bytes(font_data)
    if not _ttf_has_magic(current):
        return False
    # 注意：不在此处跳过 current == ttf_bytes —— UnityPy typetree 解析器
    # 对同类型对象可能返回共享缓存，前一个对象已改则后续读到的就是目标字节；
    # 跳过会漏计数（替换本身无害）。save_typetree 幂等。
    metrics = _ttf_metrics(ttf_bytes)
    if metrics is not None:
        ascent, descent, line_gap = metrics
        font_size = tree.get("m_FontSize") or 16
        tree["m_Ascent"] = round(ascent * font_size, 2)
        tree["m_Descent"] = round(descent * font_size, 2)
        tree["m_LineSpacing"] = round(
            (ascent - descent + line_gap) * font_size, 2)
        if tree.get("m_FontRenderingMode") == _FONT_RENDERING_MODE_HINTED_RASTER:
            tree["m_FontRenderingMode"] = _FONT_RENDERING_MODE_SMOOTH
    tree["m_FontData"] = list(ttf_bytes)
    font_obj.save_typetree(tree)
    return True


def _replace_and_swap(path: Path, env, verify_fn=None) -> None:
    """容器序列化 → 验证临时文件 → 释放句柄 → 原子替换目标文件。

    与 writer._patch_asset 同一顺序：验证发生在替换前（对临时文件），
    目标文件只在初次 env.load 时被打开，且替换前已 dispose，避免 Windows
    句柄锁定导致 PermissionError。
    """
    import gc
    import time as _time
    containers = {
        id(item): item for item in env.files.values()
        if type(item).__name__ in ("BundleFile", "SerializedFile")
    }
    if len(containers) != 1:
        raise ValueError(
            f"预期恰好一个顶层 Unity 容器，实际为 {len(containers)}: {path.name}")
    container = next(iter(containers.values()))
    with tempfile.TemporaryDirectory(
        prefix=f".{path.name}.", dir=path.parent,
    ) as tmp:
        saved = Path(tmp) / path.name
        if type(container).__name__ == "BundleFile":
            saved.write_bytes(container.save(packer="original"))
        else:
            saved.write_bytes(container.save())
        if verify_fn is not None:
            verify_fn(saved)
        _dispose_environment(env)
        gc.collect()
        # 兜底：Defender 扫描锁定窗口短重试
        for attempt in range(5):
            try:
                os.replace(saved, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                _time.sleep(0.8)


def _verify_legacy_saved(saved: Path, ttf_bytes: bytes, replaced: int) -> None:
    """重开临时容器验证全部 Font 的 m_FontData 均已被替换。"""
    from UnityPy import Environment
    verify = Environment()
    try:
        verify.load([str(saved)])
        seen: set[tuple[str, int]] = set()
        matched = 0
        for obj in verify.objects:
            if obj.type.name != "Font":
                continue
            key = (obj.type.name, obj.path_id)
            if key in seen:
                continue
            seen.add(key)
            tree = obj.read_typetree()
            fd = tree.get("m_FontData")
            if isinstance(fd, list) and bytes(fd) == ttf_bytes:
                matched += 1
        if matched < replaced:
            raise ValueError(
                f"Font 替换重开验证不一致: {saved.name} "
                f"replaced={replaced} matched={matched}")
    finally:
        _dispose_environment(verify)


def replace_legacy_fonts_in_container(
    path: Path,
    ttf_bytes: bytes,
    progress: int = 0,
) -> tuple[int, list[str]]:
    """替换单个 Unity 容器（.assets/level/bundle）内全部 Font 对象的内嵌 TTF。

    返回 (替换数, 跳过原因列表)。
    """
    from UnityPy import Environment
    env = Environment()
    replaced = 0
    skipped: list[str] = []
    try:
        env.load([str(path)])
        seen: set[tuple[str, int]] = set()
        for obj in env.objects:
            if obj.type.name != "Font":
                continue
            key = (obj.type.name, obj.path_id)
            if key in seen:
                continue
            seen.add(key)
            try:
                if _patch_font_object(env, obj, ttf_bytes):
                    replaced += 1
            except Exception as exc:  # noqa: BLE001
                skipped.append(f"{path.name}#Font#{obj.path_id}: {exc}")
        if not replaced:
            return 0, skipped
        _replace_and_swap(
            path, env,
            verify_fn=lambda saved: _verify_legacy_saved(saved, ttf_bytes, replaced),
        )
    finally:
        _dispose_environment(env)
    return replaced, skipped


# ── TMP_FontAsset 替换 ──────────────────────────────────────

# 常用汉字样本（GB2312 一级字）：字符表全覆盖样本且总量充足 → 视为已覆盖
# CJK，不替换（避免把游戏自带中文字体如 chi_NotoSansCH 换成 ARIALUNI SDF：
# 既没必要，又会把 bundle 撑到数百 MB）。
_CJK_SAMPLE_CODES = tuple(ord(c) for c in (
    "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严龙飞"
))
_CJK_MIN_TOTAL = 2000  # 字符表 CJK 码点数门槛（覆盖样本外生僻字的余量）


def _tmp_chars(tree: dict) -> list[int]:
    """从 TMP 字符表提取 unicode 码点（tmp1/tmp2 兼容）。"""
    chars: list[int] = []
    for field in ("m_CharacterTable", "m_characterTable"):
        table = tree.get(field)
        if isinstance(table, list):
            for item in table:
                if isinstance(item, dict):
                    u = item.get("m_Unicode")
                    if isinstance(u, int):
                        chars.append(u)
                    elif isinstance(u, str):
                        try:
                            chars.append(int(u, 16))
                        except ValueError:
                            pass
    return chars


def _tmp_covers_cjk(tree: dict) -> bool:
    """TMP 字体字符表是否已覆盖常用汉字（是则跳过替换）。"""
    chars = _tmp_chars(tree)
    cjk = {c for c in chars if 0x4E00 <= c <= 0x9FFF}
    if len(cjk) < _CJK_MIN_TOTAL:
        return False
    return all(c in cjk for c in _CJK_SAMPLE_CODES)


_TMP2_COPY_FIELDS = (
    "m_FaceInfo", "m_GlyphTable", "m_CharacterTable",
    "m_AtlasTextureIndex", "m_IsMultiAtlasTexturesEnabled",
    "m_UsedGlyphRects", "m_FreeGlyphRects",
)
_TMP1_COPY_FIELDS = (
    "m_fontInfo", "m_glyphInfoList", "m_kerningInfo",
    "m_kerningPair", "m_characterSpacing", "m_characterPadding",
)


def _copy_font_fields(game_tree: dict, payload: TmpBundlePayload) -> bool:
    """把 bundle 字体的字形数据复制进游戏字体 typetree。返回是否有变化。"""
    if payload.layout_version == "tmp2":
        fields = _TMP2_COPY_FIELDS
    else:
        fields = _TMP1_COPY_FIELDS
    changed = False
    for field_name in fields:
        if field_name not in payload.font_typetree:
            continue
        value = payload.font_typetree[field_name]
        if game_tree.get(field_name) != value:
            game_tree[field_name] = value
            changed = True
    return changed


def _resolve_atlas_obj(env, tree: dict) -> object | None:
    """解析 TMP 字体引用的图集 Texture2D。

    Unity 引用 `m_FileID=0` 表示同一 SerializedFile 内的对象 —— 旧代码把
    "0" 当作资产文件名比对导致永远找不到图集（project-arrhythmia 真实失败）。
    """
    refs = tree.get("m_AtlasTextures") or tree.get("atlas")
    ref = None
    if isinstance(refs, list) and refs:
        ref = refs[0] if isinstance(refs[0], dict) else None
    elif isinstance(refs, dict):
        ref = refs
    if not isinstance(ref, dict):
        return None
    file_id = ref.get("m_FileID")
    path_id = ref.get("m_PathID")
    if isinstance(file_id, str):
        same_file = file_id.strip() in {"", "0", "0:0"}
    else:
        same_file = not file_id or int(file_id) == 0
    if not same_file:
        return None  # 跨文件引用（同 bundle 其他 SerializedFile）：不支持
    try:
        path_id = int(path_id)
    except (TypeError, ValueError):
        return None
    for other in env.objects:
        if other.type.name == "Texture2D" and int(other.path_id) == path_id:
            return other
    return None


def _patch_atlas_texture(env, atlas_obj, payload: TmpBundlePayload) -> dict | None:
    """把游戏图集 Texture2D 替换为 bundle 图集（含真实像素）。

    旧实现两个缺陷（导致替换后 TMP 汉字仍是口口口口/花屏）：
    1. 图集引用 m_FileID=0 被当作文件名比对 → 永远找不到图集（已修）；
    2. 图集走共享 resS 流文件：多个 TMP 字体共用一个 resS，按 offset 覆盖/
       追加会把彼此刚写入的 64MB 数据互相踩掉（实测 resS 内 9 段数据互相
       重叠）。现在改为**内嵌数据**（m_StreamData.size=0 + typetree 的
       "image data" 字节）：Unity 加载时流为空则读内嵌字节 —— 每个图集
       独立携带像素，无需共享流、无需改任何引用。
    """
    tree = atlas_obj.read_typetree()
    # 图集整体换为 bundle 图集的内容；保留游戏图集的名称与采样/包裹设置
    # （wrap/filter 影响渲染，保留游戏原有设置最稳）。
    new_tree = dict(payload.atlas_texture)
    for keep in ("m_Name", "m_TextureSettings"):
        if keep in tree:
            new_tree[keep] = tree[keep]
    new_tree["image data"] = payload.atlas_stream
    new_tree["m_StreamData"] = {"offset": 0, "size": 0, "path": ""}
    new_tree["m_CompleteImageSize"] = len(payload.atlas_stream)
    return new_tree


def replace_tmp_fonts_in_container(
    path: Path,
    payload: TmpBundlePayload,
) -> tuple[int, list[str]]:
    """替换单个容器内全部 TMP_FontAsset 对象。返回 (替换数, 跳过列表)。"""
    from UnityPy import Environment
    env = Environment()
    replaced = 0
    skipped: list[str] = []
    patched: list = []
    try:
        env.load([str(path)])
        seen: set[tuple[str, int]] = set()
        for obj in env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            key = (obj.type.name, obj.path_id)
            if key in seen:
                continue
            seen.add(key)
            try:
                tree = obj.read_typetree()
            except Exception:  # noqa: BLE001
                continue
            if _typetree_layout_version(tree) is None:
                continue
            layout = _typetree_layout_version(tree)
            if layout != payload.layout_version:
                skipped.append(
                    f"{path.name}#TMP#{obj.path_id}: layout {layout} "
                    f"!= bundle {payload.layout_version}")
                continue
            glyphs = len(tree.get("m_GlyphTable")
                         or tree.get("m_glyphInfoList") or [])
            if glyphs <= 0:
                # 动态/空字体：字形由运行时生成，替换静态字形表有行为冲突风险
                skipped.append(
                    f"{path.name}#TMP#{obj.path_id}: dynamic font (0 glyphs)")
                continue
            if _tmp_covers_cjk(tree):
                # 字符表已覆盖常用汉字（如游戏自带 chi_NotoSansCH）：
                # 保留原字体，避免无谓替换与 bundle 膨胀
                skipped.append(
                    f"{path.name}#TMP#{obj.path_id}: already covers CJK")
                continue
            changed = _copy_font_fields(tree, payload)
            # 图集：游戏字体引用的 Texture2D 需要同步替换（m_FileID=0 为同文件引用）
            atlas_obj = _resolve_atlas_obj(env, tree)
            if atlas_obj is None:
                skipped.append(f"{path.name}#TMP#{obj.path_id}: atlas not found")
                continue
            atlas_tree = _patch_atlas_texture(env, atlas_obj, payload)
            if atlas_tree is None:
                skipped.append(
                    f"{path.name}#TMP#{obj.path_id}: atlas replace failed")
                continue
            atlas_obj.save_typetree(atlas_tree)
            if changed:
                obj.save_typetree(tree)
            patched.append((obj, atlas_obj))
            replaced += 1
        if not patched:
            return 0, skipped
        _replace_and_swap(
            path, env,
            verify_fn=lambda saved: _verify_tmp_saved(
                saved, payload, replaced))
    finally:
        _dispose_environment(env)
    return replaced, skipped


def _verify_tmp_saved(saved: Path, payload: TmpBundlePayload, replaced: int) -> None:
    """重开临时容器验证 TMP 字形表 + 图集像素均已替换。

    只验字形数量会漏掉「元数据更新但流没写入」的假通过——旧实现正是如此
    （同尺寸分支只改 typetree 不写像素）。图集流数据必须逐字节等于
    payload.atlas_stream。
    """
    from UnityPy import Environment
    verify = Environment()
    try:
        verify.load([str(saved)])
        seen: set[tuple[str, int]] = set()
        matched = 0
        atlas_verified = 0
        for obj in verify.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            key = (obj.type.name, obj.path_id)
            if key in seen:
                continue
            seen.add(key)
            try:
                tree = obj.read_typetree()
            except Exception:  # noqa: BLE001
                continue
            if _typetree_layout_version(tree) != payload.layout_version:
                continue
            glyphs = len(tree.get("m_GlyphTable")
                         or tree.get("m_glyphInfoList") or [])
            if glyphs == payload.glyph_count:
                matched += 1
            atlas_obj = _resolve_atlas_obj(verify, tree)
            if atlas_obj is None:
                continue
            atlas_tree = atlas_obj.read_typetree()
            if (atlas_tree.get("m_Width") == payload.atlas_width
                    and atlas_tree.get("m_Height") == payload.atlas_height
                    and atlas_tree.get("m_TextureFormat") == payload.atlas_format):
                data = atlas_tree.get("image data")
                if isinstance(data, (bytes, bytearray, list)) \
                        and bytes(data) == payload.atlas_stream:
                    atlas_verified += 1
        if matched < replaced:
            raise ValueError(
                f"TMP 替换重开验证不一致: {saved.name} "
                f"replaced={replaced} matched={matched}")
        if atlas_verified < replaced:
            raise ValueError(
                f"TMP 图集像素验证不一致: {saved.name} "
                f"replaced={replaced} atlas_verified={atlas_verified}")
    finally:
        _dispose_environment(verify)


def _object_key(obj) -> tuple[str, int]:
    return str(obj.assets_file.name), int(obj.path_id)


# ── 整目录入口 ──────────────────────────────────────────────

_ASSET_SUFFIXES = {".assets", ".bundle", ".unity3d", ".u3d", ".dat"}
_NO_EXT_NAMES = {"level", "maindata", "globalgamemanagers"}
# 真实 Unity 容器最小也有数 KB；更小的是占位/假文件（如测试 fixture 的
# 10 字节 globalgamemanagers），加载无意义且 UnityPy 会以未知格式持有句柄。
_MIN_CONTAINER_BYTES = 256


def _asset_candidates(out_dir: Path) -> list[Path]:
    """收集写回副本中值得做字体替换的 Unity 容器。"""
    candidates: list[Path] = []
    for root in (out_dir.rglob("*")):
        if not root.is_file():
            continue
        if root.stat().st_size < _MIN_CONTAINER_BYTES:
            continue
        name = root.name.casefold()
        is_level = name.startswith("level") and name[5:].isdigit()
        if (root.suffix.casefold() in _ASSET_SUFFIXES
                or name in _NO_EXT_NAMES or is_level):
            candidates.append(root)
    # 排除引擎/工具目录
    excluded = {"monobleedingedge", "il2cpp_data", "bee_data", "resources/unity"
                "_builtin_extra", "streamingassets/aa/catalogs"}
    return [c for c in candidates
            if not any(part.casefold() in excluded for part in c.parts)]


def install_static_fonts(
    out_dir: Path,
    config: FontConfig,
    *,
    unity_version: str | None = None,
) -> FontReplaceResult:
    """在写回副本上执行静态字体替换（legacy Font + TMP_FontAsset）。

    任何单项失败只跳过并记录；绝不抛出（字体是增强项，不阻断写回）。
    """
    result = FontReplaceResult()
    ttf = _font_ttf_candidate(config)
    if ttf is not None:
        ttf_bytes = ttf.read_bytes()
        for asset in _asset_candidates(out_dir):
            try:
                replaced, skipped = replace_legacy_fonts_in_container(
                    asset, ttf_bytes)
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"{asset.name}: {exc}")
                continue
            result.replaced += replaced
            result.skipped.extend(skipped)
            if replaced:
                result.replaced_paths.append(
                    asset.relative_to(out_dir).as_posix())
    # TMP 路径
    bundle = select_tmp_bundle(unity_version)
    if bundle is not None and config.enabled:
        try:
            payload = load_tmp_bundle(bundle)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"TMP bundle {bundle.name} 解析失败: {exc}")
            payload = None
        if payload is not None:
            for asset in _asset_candidates(out_dir):
                try:
                    replaced, skipped = replace_tmp_fonts_in_container(
                        asset, payload)
                except Exception as exc:  # noqa: BLE001
                    result.warnings.append(f"{asset.name}: {exc}")
                    continue
                result.replaced += replaced
                result.skipped.extend(skipped)
                if replaced:
                    result.replaced_paths.append(
                        str(asset.relative_to(out_dir)))
    return result
