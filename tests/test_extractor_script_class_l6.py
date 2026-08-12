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
