"""识别 L6 测试：PPtr m_Script 脚本类身份（确定性证据优先于串池信号）。

评估报告：rawstr 分类靠串池信号猜类（is_input_system_object 等），meta
不记录 m_Script 引用的脚本类名；morfosigame/deadbeat 输入配置对象靠猜。
建议：解析 PPtr m_Script → MonoScript 类名，确定性证据优先。
"""
import struct
from pathlib import Path

from hanhua.core.unity.extractor import (
    _INPUT_SYSTEM_SCRIPT_CLASSES, _TIMELINE_SCRIPT_CLASSES, _script_class_of)


def _with_len(s: str) -> bytes:
    """Unity 序列化对齐字符串（长度前缀 + 4 字节对齐），同 test_v2。"""
    b = s.encode("utf-8")
    padding = b"\x00" * (-len(b) % 4)
    return struct.pack("<I", len(b)) + b + padding


class _MonoScriptObj:
    """objects 池中的 MonoScript：read_typetree 返回 m_Name。"""

    def __init__(self, name: str):
        self.type = type("ObjectType", (), {"name": "MonoScript"})()
        self._name = name

    def read_typetree(self):
        return {"m_Name": self._name}


class _FakeObject:
    def __init__(self, path: Path, tree=None, raw: bytes = b"",
                 path_id: int = 7, objects: dict | None = None):
        self.path_id = path_id
        self.assets_file = type("AssetFile", (), {
            "name": path.name, "objects": objects or {}})()
        self.type = type("ObjectType", (), {"name": "MonoBehaviour"})()
        self._tree = tree
        self.raw = raw

    def read_typetree(self):
        if self._tree is None:
            raise ValueError("typetree 不可用")
        return self._tree

    def get_raw_data(self):
        return self.raw


class _FakeEnvironment:
    def __init__(self, objects):
        self.objects = objects
        self.files = {}

    def load(self, paths):
        pass


def _extract(tmp_path, objects, monkeypatch):
    import UnityPy
    from hanhua.core.unity.extractor import extract_asset_file
    p = Path(tmp_path) / "level1"
    p.write_bytes(b"\x00" * 8)
    monkeypatch.setattr(UnityPy, "Environment",
                        lambda: _FakeEnvironment(objects))
    return extract_asset_file(p, "level1")


def _input_obj(script_name: str | None, raw: bytes, path_id: int = 7):
    """带 m_Script PPtr 的 MonoBehaviour（objects 池含 MonoScript 或为空）。"""
    tree = {"m_Script": {"m_FileID": 0, "m_PathID": 9}, "m_Name": "obj"}
    objects = {}
    if script_name is not None:
        objects[9] = _MonoScriptObj(script_name)
    return _FakeObject(Path("level1"), tree=tree, raw=raw,
                       path_id=path_id, objects=objects)


# ── _script_class_of 纯函数 ─────────────────────────────────

def test_script_class_of_resolves_pptr_to_monoscript():
    """m_Script PPtr（FileID=0）→ objects 池 MonoScript → 类名。"""
    obj = _input_obj("InputActionAsset", b"")
    assert _script_class_of(obj._tree, obj) == "InputActionAsset"


def test_script_class_of_empty_on_external_fileid():
    """跨文件 PPtr（m_FileID≠0）无法在同文件 objects 池解析 → ""。"""
    obj = _input_obj("InputActionAsset", b"")
    tree = {"m_Script": {"m_FileID": 1, "m_PathID": 9}}
    assert _script_class_of(tree, obj) == ""


def test_script_class_of_empty_on_missing_pptr_or_unresolved():
    """无 m_Script / m_PathID 不在池 → ""（解析失败不改变既有判定）。"""
    obj = _input_obj("InputActionAsset", b"")
    assert _script_class_of({}, obj) == ""
    assert _script_class_of(
        {"m_Script": {"m_FileID": 0, "m_PathID": 42}}, obj) == ""


def test_script_class_of_empty_on_non_monoscript_or_error():
    """目标不是 MonoScript / typetree 读取失败 → ""（不抛错）。"""
    obj = _input_obj("InputActionAsset", b"")
    other = type("Obj", (), {"type": type("T", (), {"name": "MonoBehaviour"})()})()
    obj.assets_file.objects[9] = other
    assert _script_class_of(obj._tree, obj) == ""
    bad = type("Obj", (), {"type": type("T", (), {"name": "MonoScript"})()})()

    def _boom():
        raise ValueError("typetree 不可用")
    bad.read_typetree = _boom
    obj.assets_file.objects[9] = bad
    assert _script_class_of(obj._tree, obj) == ""


def test_script_class_sets_cover_registry_entries():
    """两名单非空且为 frozenset（确定性类名证据源）。"""
    assert "InputActionAsset" in _INPUT_SYSTEM_SCRIPT_CLASSES
    assert "PlayableDirector" in _TIMELINE_SCRIPT_CLASSES
    assert isinstance(_INPUT_SYSTEM_SCRIPT_CLASSES, frozenset)


# ── 集成：类名证据跳过 + meta 记录 ──────────────────────────

def test_input_system_class_skips_action_names(tmp_path, monkeypatch):
    """InputActionAsset 类名对象：无任何串池信号时 action 名仍跳过
    （类名证据独立成立——morfosigame 'Normal' map 名不在名单的形态）。
    注意避开 _INPUT_BINDING_NAMES（move/fire 等命中硬结构规则
    input_binding 先行跳过，不走对象级判定）。"""
    raw = _with_len("Jump") + _with_len("Interact")
    pf = _extract(tmp_path, [_input_obj("InputActionAsset", raw)],
                  monkeypatch)
    skip = [e for e in pf.entries if e.original == "Jump"][0]
    assert skip.status == "skipped"
    assert skip.meta["reason"] == "input_system_object"
    assert skip.meta["obj_is_key_list"] is True
    assert skip.meta["script_class"] == "InputActionAsset"


def test_timeline_class_skips_track_names(tmp_path, monkeypatch):
    """PlayableDirector 类名对象：剪辑名（无轨道编号形态）被跳过。"""
    raw = _with_len("Intro") + _with_len("Loop")
    pf = _extract(tmp_path, [_input_obj("PlayableDirector", raw)],
                  monkeypatch)
    skip = [e for e in pf.entries if e.original == "Intro"][0]
    assert skip.status == "skipped"
    assert skip.meta["reason"] == "timeline_object"


def test_string_pool_signal_still_works_without_class(tmp_path, monkeypatch):
    """无类名（PPtr 无法解析）→ 串池信号兜底保持：InputSystem 程序集
    串仍判输入对象（引擎串本身进 prefilter 样本，普通词被对象级跳过）。"""
    raw = _with_len("UnityEngine.InputSystem") + _with_len("Jump")
    pf = _extract(tmp_path, [_input_obj(None, raw)], monkeypatch)
    skip = [e for e in pf.entries if e.original == "Jump"][0]
    assert skip.status == "skipped"
    assert skip.meta["reason"] == "input_system_object"
    assert "script_class" not in skip.meta


def test_unrelated_class_leaves_classification_to_pool(tmp_path, monkeypatch):
    """无关类名（PlayerController）不在名单 → 串池无信号时短词串不因
    类名被判 input_system_object（既有分类链原样走）；类名仍记录进
    meta（可审计）。"""
    raw = _with_len("Jump") + _with_len("Interact")
    pf = _extract(tmp_path, [_input_obj("PlayerController", raw)],
                  monkeypatch)
    move = [e for e in pf.entries if e.original == "Jump"][0]
    assert move.meta.get("reason") != "input_system_object"
    assert move.meta.get("script_class") == "PlayerController"


def test_code_driven_object_name_not_display(tmp_path, monkeypatch):
    """minato 实证「no translation found for 音频」（2026-08-15）：
    对象 [Minato(对象名), audio(子对象名), TMPro.TMP_Text(类型引用),
    SetText(代码驱动方法)]——SetText 说明文本由代码运行时设置，audio
    是 GameObject 名不是静态显示文本。此前 SetText 被引擎串过滤不
    贡献 code 信号（白名单词 + 单类型引用即放行 display），audio 被
    译成「音频」写回，游戏按名查找失败。修复：代码驱动方法名计入
    code 信号 → is_code_heavy → 白名单词按 code 对象跳过。"""
    raw = (_with_len("Minato") + _with_len("audio")
           + _with_len("TMPro.TMP_Text, Unity.TextMeshPro")
           + _with_len("SetText"))
    pf = _extract(tmp_path, [_input_obj(None, raw)], monkeypatch)
    audio = [e for e in pf.entries if e.original == "audio"][0]
    assert audio.status == "skipped"
    assert audio.meta["reason"] == "code_heavy_identifier"
    assert audio.meta["obj_is_code_heavy"] is True


def test_static_button_object_still_display(tmp_path, monkeypatch):
    """对照组（hotel-paradise 按钮对象形态）：无代码驱动方法、含控件
    状态证据（Normal/Highlighted/Pressed）+ 组件类型引用——白名单
    显示词照常放行，修复不误伤静态按钮文本。"""
    raw = (_with_len("Save") + _with_len("Normal")
           + _with_len("Highlighted") + _with_len("Pressed")
           + _with_len("Some.UI.Button, UnityEngine.UI"))
    pf = _extract(tmp_path, [_input_obj(None, raw)], monkeypatch)
    save = [e for e in pf.entries if e.original == "Save"][0]
    assert save.status == "pending"
    assert save.meta["role"] == "display"


def test_button_object_shared_name_word_skipped(tmp_path, monkeypatch):
    """2026-08-15 多游戏实证「写回后按键 UI 失灵/游戏卡住」：按钮对象
    m_Name 与 m_text 同值（"Exit" ×2）+ Button 类型引用——两处一起
    翻译写回会改对象名，代码按名查找断裂。修复：同值 ≥2 处的共享词
    全组跳过保留原文（宁漏勿坏）。用 Exit（非 Unity 生命周期词——
    Start 会被既有 lifecycle_method 规则先行跳过）。"""
    raw = (_with_len("Exit") + _with_len("Exit")
           + _with_len("UnityEngine.UI.Button, UnityEngine.UI"))
    pf = _extract(tmp_path, [_input_obj(None, raw)], monkeypatch)
    exits = [e for e in pf.entries if e.original == "Exit"]
    assert len(exits) == 2
    for e in exits:
        assert e.status == "skipped"
        assert e.meta["reason"] == "object_name_shared_word"


def test_code_heavy_button_shared_name_word_skipped(tmp_path, monkeypatch):
    """code_heavy 变体（多类型引用 + 控件状态）：UI 证据对象里的共享
    白名单词同样跳过（is_code_heavy 分支的共享词保护）。"""
    raw = (_with_len("Settings") + _with_len("Settings")
           + _with_len("Normal") + _with_len("Highlighted")
           + _with_len("Pressed")
           + _with_len("UnityEngine.UI.Button, UnityEngine.UI")
           + _with_len("TMPro.TMP_Text, Unity.TextMeshPro"))
    pf = _extract(tmp_path, [_input_obj(None, raw)], monkeypatch)
    settings = [e for e in pf.entries if e.original == "Settings"]
    assert len(settings) == 2
    for e in settings:
        assert e.status == "skipped"
        assert e.meta["reason"] == "object_name_shared_word"


def test_static_button_single_word_still_display(tmp_path, monkeypatch):
    """对照组（hotel-paradise 静态按钮）：白名单词单次出现照常放行。"""
    raw = (_with_len("Save") + _with_len("Normal")
           + _with_len("Highlighted") + _with_len("Pressed")
           + _with_len("Some.UI.Button, UnityEngine.UI"))
    pf = _extract(tmp_path, [_input_obj(None, raw)], monkeypatch)
    save = [e for e in pf.entries if e.original == "Save"][0]
    assert save.status == "pending"
    assert save.meta["role"] == "display"
