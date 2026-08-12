"""识别 L7 测试：typetree 覆盖率持续度量 + 字段白名单登记制。

评估报告：Unity 6000 typetree 264/268 失败靠 raw scan 兜底，但无每
容器 typetree 可用率统计（失败率哑信号）；_TYPETREE_DISPLAY_FIELDS
约 40 字段无登记制（新增无依据可审计）。
"""
import struct
from pathlib import Path

from hanhua.core.unity import extractor
from hanhua.core.unity.extractor import _TYPETREE_DISPLAY_FIELD_ROWS


def _with_len(s: str) -> bytes:
    """Unity 序列化对齐字符串（长度前缀 + 4 字节对齐），同 test_v2。"""
    b = s.encode("utf-8")
    padding = b"\x00" * (-len(b) % 4)
    return struct.pack("<I", len(b)) + b + padding


class _FakeObject:
    def __init__(self, path: Path, tree=None, raw: bytes = b"",
                 tname: str = "MonoBehaviour", path_id: int = 7):
        self.path_id = path_id
        self.assets_file = type("AssetFile", (), {"name": path.name})()
        self.type = type("ObjectType", (), {"name": tname})()
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


def _tree_with_text(text: str) -> dict:
    return {"m_Name": "obj", "m_Text": text}


# ── typetree 覆盖率 ──────────────────────────────────────────

def test_typetree_coverage_full_on_success(tmp_path, monkeypatch):
    """全部对象 typetree 成功 → coverage=1.0 入容器 meta。"""
    pf = _extract(tmp_path, [
        _FakeObject(Path("level1"), _tree_with_text("Hello player")),
    ], monkeypatch)
    assert pf.meta["typetree_coverage"] == 1.0
    assert pf.meta["typetree_objects"] == 1
    assert pf.skipped_reasons.get("typetree_failed") is None


def test_typetree_failure_counts_and_raw_fallback(tmp_path, monkeypatch):
    """typetree 失败 → typetree_failed 计数留档 + coverage=0.0 +
    raw scan 兜底（Unity 6000 264/268 失败的量化形态）。"""
    raw = _with_len("Hello player") + b"\x00" * 16
    pf = _extract(tmp_path, [
        _FakeObject(Path("level1"), tree=None, raw=raw),
    ], monkeypatch)
    assert pf.skipped_reasons["typetree_failed"] == 1
    assert pf.meta["typetree_coverage"] == 0.0
    assert pf.meta["typetree_objects"] == 1
    assert any(e.original == "Hello player" for e in pf.entries)


def test_typetree_partial_coverage(tmp_path, monkeypatch):
    """2 对象 1 成功 1 失败 → coverage=0.5（逐容器可用率可查）。"""
    pf = _extract(tmp_path, [
        _FakeObject(Path("level1"), _tree_with_text("A"), path_id=7),
        _FakeObject(Path("level1"), tree=None, raw=b"x", path_id=8),
    ], monkeypatch)
    assert pf.meta["typetree_coverage"] == 0.5
    assert pf.meta["typetree_objects"] == 2
    assert pf.skipped_reasons["typetree_failed"] == 1


# ── 字段白名单登记制 ─────────────────────────────────────────

def test_display_field_registry_derives_set():
    """frozenset 从登记表派生（接口不变），登记行无重复名。"""
    assert extractor._TYPETREE_DISPLAY_FIELDS == frozenset(
        f.name for f in _TYPETREE_DISPLAY_FIELD_ROWS)
    names = [f.name for f in _TYPETREE_DISPLAY_FIELD_ROWS]
    assert len(names) == len(set(names))
    fields = extractor._TYPETREE_DISPLAY_FIELDS
    assert "text" in fields and "dialoguetext" in fields
    assert "name" not in fields  # m_Name 标识名有意排除


def test_display_field_rows_carry_source_group():
    """每字段带出处分组（ui/dialogue/locale/misc）——新增必须登记。"""
    groups = {f.group for f in _TYPETREE_DISPLAY_FIELD_ROWS}
    assert groups <= {"ui", "dialogue", "locale", "misc"}
    assert groups == {"ui", "dialogue", "locale", "misc"}
    assert len(_TYPETREE_DISPLAY_FIELD_ROWS) >= 40  # 原清单规模保持
