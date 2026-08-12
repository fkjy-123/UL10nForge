"""fix-31 TMP 资产对象判定（headache 实证 2026-08-12）。

TextMeshPro 字体/精灵资产序列化对象（resources.assets#1078、
sharedassets0#384）——m_AssetVersion '1.1.0' + 字体名含独立 token
'sdf'（'BaiJamjuree-Medium SDF'）或精灵资产名 'sprite asset'
（'Default Sprite Asset'）。资产名是 <font>/<sprite name=...>
按名引用键（Winkle/Smiley/Bai Jamjuree Medium），翻译断引用——
写回后 Sprite 变体/表情/字体全部丢失。资产对象字符串是资产元数据
（名字+GUID+版本），非可译 UI 文本 → 对象整体跳过（tmp_asset_object）。

'1.1.0' 词边界防普通文本 "v1.1.0" 误伤；单条件（只有 'sdf' 或只有
'1.1.0'）不触发。
"""
from hanhua.core.unity.extractor import _raw_string_entries

from tests.test_f29_word_table import _find
from tests.test_v2 import _scriptable_object_raw, _with_len


def test_sprite_asset_object_skipped():
    """精灵资产对象（'Default Sprite Asset' + '1.1.0' + 精灵名）：
    资产名串本身被引擎串过滤拦截（既有行为），同对象非引擎串
    （精灵名 Smiley/Wink、版本 1.1.0）是 <sprite name=...> 引用
    链的一部分 → 对象级 tmp_asset_object 跳过。"""
    raw = (_scriptable_object_raw(
        "Default Sprite Asset", "1.1.0", "Smiley", "Wink", "Whaaat!")
        + _with_len("Sprite Atlas 2"))
    entries = _raw_string_entries("f1", 5, raw, {}, "resources.assets")
    assert len(entries) == 6
    # 资产名被引擎串拦、版本号被键风格拦（既有行为，都不该翻）
    assert _find(entries, "Default Sprite Asset").meta["reason"] \
        == "prefilter_engine_string"
    assert _find(entries, "1.1.0").meta["reason"] == "prefilter_key_identifier"
    # 精灵名/图集名：<sprite name=...> 引用链 → 对象级 tmp_asset_object
    for name in ("Smiley", "Wink", "Whaaat!", "Sprite Atlas 2"):
        e = _find(entries, name)
        assert e.status == "skipped", f"{name} 未跳过"
        assert e.meta["reason"] == "tmp_asset_object", name


def test_sdf_font_asset_object_skipped():
    """SDF 字体资产对象（'BaiJamjuree-Medium SDF' + '1.1.0' + GUID）：
    字体名串被引擎串过滤拦截（既有行为），同对象非引擎串（GUID、
    布局参数 Character/Line Spacing）→ 对象级 tmp_asset_object
    跳过——字体名是判定证据，检测用完整 scanned 池（含引擎串）。"""
    raw = _scriptable_object_raw(
        "BaiJamjuree-Medium SDF", "1.1.0",
        "d0a1b2c3d4e5f60718293a4b5c6d7e8f",
        "f1029384756a7b8c9d0e1f2031425364",
        "Word Spacing", "Character", "Line Spacing")
    entries = _raw_string_entries("f1", 5, raw, {}, "sharedassets0.assets")
    # 字体名+GUID 被引擎串拦、版本号被键风格拦（既有行为）
    assert len(entries) == 7
    assert _find(entries, "1.1.0").meta["reason"] == "prefilter_key_identifier"
    # 布局参数串：字体资产元数据（对象级 tmp_asset_object 判定）
    assert _find(entries, "Character").meta["reason"] == "tmp_asset_object"
    assert _find(entries, "Line Spacing").meta["reason"] == "tmp_asset_object"


def test_version_only_object_not_triggered():
    """只有 '1.1.0'（无 sdf/sprite asset）：普通版本号对象（UI 文本
    "v1.1.0"）不触发 TMP 判定。"""
    raw = _with_len("Version 1.1.0") + _with_len("v1.1.0 is here")
    entries = _raw_string_entries("f1", 5, raw, {}, "sharedassets0.assets")
    reasons = {e.meta["reason"] for e in entries}
    assert "tmp_asset_object" not in reasons
    assert _find(entries, "Version 1.1.0").status == "pending"


def test_sdf_word_in_normal_object_not_triggered():
    """单条件（只有 'sdf' 词但无 '1.1.0'）：普通文本对象不触发
    （'sdf' 也可能是其它词；必须与资产版本号同现）。"""
    raw = _with_len("SDF 是一种字体技术") + _with_len("主菜单")
    entries = _raw_string_entries("f1", 5, raw, {}, "sharedassets0.assets")
    reasons = {e.meta["reason"] for e in entries}
    assert "tmp_asset_object" not in reasons
