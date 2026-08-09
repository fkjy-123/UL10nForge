"""写回安全闸门测试（指南 §14 P0-1/P0-2/P0-3 + P0-4 不可变字段）。

覆盖：五态闸门评估、rejected/truncated 阻断默认发布与 allow_partial
放行、source/target manifest 持久化、不可变字段集合收集与重开校验。
"""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from hanhua.core.memory import ProjectStore
from hanhua.core.models import FontConfig, WriteRejection
from hanhua.core.project import Project
from hanhua.core.smoke import SmokeResult
from hanhua.core.unity.writer import (
    WriteResult,
    _collect_immutable_values,
    _verify_saved_bundle,
)
from tests.test_scanner import _make_tree
from tests.test_project import _install_fake_raw_asset_environment


def _fake_font(installed=False, payload_deployed=False, runtime_verified=False,
               provider_supported=True, unsupported_reason=""):
    return SimpleNamespace(
        installed=installed, payload_deployed=payload_deployed,
        runtime_verified=runtime_verified,
        provider_supported=provider_supported,
        unsupported_reason=unsupported_reason)


def _fake_v2(files=0, entries=0):
    return SimpleNamespace(files=files, entries=entries)


def _gates(project: Project, *, v2=None, font=None, rejected=(), truncated=0,
           smoke_result=None, smoke_enabled=True, text_files=1,
           text_verified=1, allow_partial=False, ready_text=1,
           font_enabled=False):
    return project._evaluate_writeback_gates(
        text_files=text_files, v2=v2 if v2 is not None else _fake_v2(files=1, entries=1),
        text_verified=text_verified,
        font=font if font is not None else _fake_font(),
        font_level="disabled", active_font_config=FontConfig(enabled=font_enabled),
        rejected=list(rejected), truncated=truncated,
        allow_partial=allow_partial, smoke_result=smoke_result,
        smoke_enabled=smoke_enabled, ready_text_translations=ready_text)


# ── P0-1：五态闸门评估 ──

def test_gates_all_pass_when_everything_clean(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    gates = _gates(
        proj, smoke_result=SmokeResult("passed", "存活 20s 无异常"))
    assert gates["overall"]["status"] == "PASS"
    assert gates["file"]["status"] == "PASS"
    assert gates["container"]["status"] == "PASS"
    assert gates["object"]["status"] == "PASS"
    assert gates["runtime"]["status"] == "N/A"          # 未启用字体
    assert gates["gameplay"]["status"] == "PASS"


def test_gates_object_blocked_without_allow_partial(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    gates = _gates(proj, rejected=[WriteRejection("a:b", "reason")])
    assert gates["object"]["status"] == "BLOCKED"
    assert gates["overall"]["status"] == "BLOCKED"


def test_gates_object_warn_with_allow_partial(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    gates = _gates(
        proj, rejected=[WriteRejection("a:b", "reason")], allow_partial=True)
    assert gates["object"]["status"] == "WARN"
    assert gates["overall"]["status"] == "WARN"


def test_gates_truncated_blocks_default_publish(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    gates = _gates(proj, truncated=3)
    assert gates["object"]["status"] == "BLOCKED"
    assert gates["overall"]["status"] == "BLOCKED"


def test_gates_gameplay_blocked_on_smoke_crash(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    gates = _gates(proj, smoke_result=SmokeResult("blocked", "崩溃退出"))
    assert gates["gameplay"]["status"] == "BLOCKED"
    assert gates["overall"]["status"] == "BLOCKED"


def test_gates_gameplay_na_on_unverifiable_smoke(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    gates = _gates(proj, smoke_result=SmokeResult("unverifiable", "无 exe"))
    assert gates["gameplay"]["status"] == "N/A"
    assert gates["overall"]["status"] == "PASS"


def test_gates_gameplay_na_when_smoke_disabled(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    gates = _gates(proj, smoke_result=None, smoke_enabled=False)
    assert gates["gameplay"]["status"] == "N/A"


def test_gates_runtime_warn_when_unverified_payload(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    gates = _gates(
        proj,
        font=_fake_font(installed=True, payload_deployed=True,
                        runtime_verified=False),
        font_enabled=True)
    assert gates["runtime"]["status"] == "WARN"


def test_gates_overall_prefers_blocked_over_warn(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    gates = _gates(
        proj, smoke_result=SmokeResult("blocked", "崩溃"),
        rejected=[WriteRejection("a:b", "reason")], allow_partial=True)
    assert gates["overall"]["status"] == "BLOCKED"


# ── P0-3：source/target manifest ──

def test_manifest_lists_all_files_with_hashes(tmp_path):
    proj = Project.open_game_dir(_make_tree(), tmp_path / "app")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    fingerprint = SimpleNamespace(unity_version="2022.3.34", runtime="mono")
    source_hashes = {
        "a.json": "src-hash-a",
        "b.txt": "src-hash-b",
    }
    output_hashes = {
        "a.json": "target-hash-a-changed",
        "b.txt": "src-hash-b",          # 未修改文件也列出
    }
    gates = _gates(proj)

    name = proj._write_publish_manifest(
        out_dir, source_hashes, output_hashes, fingerprint, gates, False)

    assert name == ".hanhua-manifest.json"
    manifest = json.loads((out_dir / name).read_text(encoding="utf-8"))
    assert manifest["schema"] == 1
    assert manifest["game"] == {"unity_version": "2022.3.34", "runtime": "mono"}
    assert manifest["changed_files"] == 1
    assert manifest["file_count"] == 2
    by_path = {item["path"]: item for item in manifest["files"]}
    assert by_path["a.json"]["changed"] is True
    assert by_path["a.json"]["target_sha256"] == "target-hash-a-changed"
    # 未修改文件：双 hash 一致且显式列出
    assert by_path["b.txt"]["changed"] is False
    assert by_path["b.txt"]["source_sha256"] == "src-hash-b"
    assert manifest["gates"]["overall"]["status"] == "PASS"


# ── P0-2：write_all 集成（默认阻断 / allow_partial 放行） ──

def _make_write_ready_project(tmp_path, monkeypatch):
    d = _make_tree()
    app_dir = tmp_path / "app"
    proj = Project.open_game_dir(d, app_dir)
    proj.scan()
    entry = next(row for row in proj.store.get_entries()
                 if row["status"] == "pending")
    proj.store.set_manual(entry["file_id"], entry["key_path"], "已翻译")
    return proj


def test_write_all_publishes_with_manifest_when_clean(tmp_path, monkeypatch):
    _install_fake_raw_asset_environment(monkeypatch)
    proj = _make_write_ready_project(tmp_path, monkeypatch)

    result = proj.write_all()

    assert result["verification"]["overall"] == "PASS"
    assert result["verification"]["gates"]["object"]["status"] == "PASS"
    assert result["verification"]["manifest"] == ".hanhua-manifest.json"
    manifest_path = proj.out_dir / ".hanhua-manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["changed_files"] >= 1
    unchanged = [item for item in manifest["files"] if not item["changed"]]
    assert unchanged, "未修改文件也必须列入 manifest"
    assert result["verification"]["smoke"] is not None


def test_write_all_blocks_default_publish_on_rejected(
        tmp_path, monkeypatch):
    _install_fake_raw_asset_environment(monkeypatch)
    proj = _make_write_ready_project(tmp_path, monkeypatch)
    fake_outcome = WriteResult(
        files=1, entries=1, attempted=2,
        rejected=[WriteRejection("fake:key", "test_reject")])

    def capture_v2(store, game_dir, staging):
        return fake_outcome

    monkeypatch.setattr("hanhua.core.project.write_back_v2", capture_v2)

    with pytest.raises(RuntimeError, match="阻断默认发布"):
        proj.write_all()
    assert not proj.out_dir.exists(), "被阻断时不得发布副本"


def test_write_all_blocks_on_truncated_entries(tmp_path, monkeypatch):
    _install_fake_raw_asset_environment(monkeypatch)
    proj = _make_write_ready_project(tmp_path, monkeypatch)
    fake_outcome = WriteResult(
        files=1, entries=2, attempted=2, truncated=2,
        truncated_items=["「长文本」→「长文本…」"])

    def capture_v2(store, game_dir, staging):
        return fake_outcome

    monkeypatch.setattr("hanhua.core.project.write_back_v2", capture_v2)

    with pytest.raises(RuntimeError, match="截断"):
        proj.write_all()


def test_write_all_publishes_with_warn_when_allow_partial(
        tmp_path, monkeypatch):
    _install_fake_raw_asset_environment(monkeypatch)
    proj = _make_write_ready_project(tmp_path, monkeypatch)
    fake_outcome = WriteResult(
        files=1, entries=1, attempted=2,
        rejected=[WriteRejection("fake:key", "test_reject")],
        truncated=1, truncated_items=["「a」→「a…」"])

    def capture_v2(store, game_dir, staging):
        return fake_outcome

    monkeypatch.setattr("hanhua.core.project.write_back_v2", capture_v2)

    result = proj.write_all(allow_partial=True)

    assert result["verification"]["overall"] == "WARN"
    assert result["verification"]["gates"]["object"]["status"] == "WARN"
    assert result["verification"]["allow_partial"] is True
    assert proj.out_dir.is_dir()
    assert len(result["verification"]["rejected_entries"]) == 1
    assert len(result["verification"]["truncated_entries"]) == 1
    blocked = result["verification"]["blocked_entries"]
    assert len(blocked) == 2, "rejected + truncated 必须全量进入报告"


# ── P0-5：write_all 冒烟集成 ──

def test_write_all_blocks_publish_on_smoke_crash(tmp_path, monkeypatch):
    _install_fake_raw_asset_environment(monkeypatch)
    proj = _make_write_ready_project(tmp_path, monkeypatch)

    def crashing_smoke(staging, executable_rel=None, timeout=20.0):
        return SmokeResult("blocked", "玩家进程崩溃退出（exit code 1）")

    with pytest.raises(RuntimeError, match="闸门 BLOCKED"):
        proj.write_all(smoke_runner=crashing_smoke)
    assert not proj.out_dir.exists()


def test_write_all_smoke_passed_recorded_in_gates(tmp_path, monkeypatch):
    _install_fake_raw_asset_environment(monkeypatch)
    proj = _make_write_ready_project(tmp_path, monkeypatch)

    def passing_smoke(staging, executable_rel=None, timeout=20.0):
        return SmokeResult("passed", "存活 20s 无异常", log_scan="Player.log")

    result = proj.write_all(smoke_runner=passing_smoke)

    assert result["verification"]["gates"]["gameplay"]["status"] == "PASS"
    assert result["verification"]["smoke"]["status"] == "passed"


def test_write_all_smoke_warn_does_not_block(tmp_path, monkeypatch):
    _install_fake_raw_asset_environment(monkeypatch)
    proj = _make_write_ready_project(tmp_path, monkeypatch)

    def warning_smoke(staging, executable_rel=None, timeout=20.0):
        return SmokeResult(
            "warn", "存活但日志有错误", log_errors=("CRC Mismatch",))

    result = proj.write_all(smoke_runner=warning_smoke)

    assert result["verification"]["overall"] == "WARN"
    assert proj.out_dir.is_dir()
    assert "CRC Mismatch" in result["verification"]["smoke"]["log_errors"]


def test_write_all_smoke_disabled_na(tmp_path, monkeypatch):
    _install_fake_raw_asset_environment(monkeypatch)
    proj = _make_write_ready_project(tmp_path, monkeypatch)

    result = proj.write_all(smoke=False)

    assert result["verification"]["gates"]["gameplay"]["status"] == "N/A"
    assert result["verification"]["smoke"] is None


# ── P0-4：不可变字段集合 ──

def test_collect_immutable_values_recursive():
    tree = {
        "m_Name": "Menu",
        "m_TableData": [
            {"m_Id": 1, "m_Localized": "Play"},
            {"m_Id": 2, "m_Localized": "Quit"},
        ],
        "m_Script": {"m_FileID": 100, "m_PathID": 0},
        "m_Address": "bundles/menu",
        "plain_field": "这是显示文本",
    }
    collected = _collect_immutable_values(tree)
    paths = [path for path, _ in collected]
    assert ["m_Name"] in paths
    assert ["m_TableData", 0, "m_Id"] in paths
    assert ["m_Script", "m_FileID"] in paths
    assert ["m_Address"] in paths
    # 显示文本字段不收集
    assert not any(path == ["plain_field"] for path in paths)


class _FakeTypetreeObject:
    def __init__(self, tree):
        self._tree = tree
        self.assets_file = type("AssetFile", (), {"name": "x.assets"})()
        self.path_id = 7
        self.type = type("ObjectType", (), {"name": "MonoBehaviour"})()

    def read_typetree(self):
        return self._tree

    def get_raw_data(self):
        return b"raw"


class _FakeVerifierEnvironment:
    """验证器 Environment 替身：重开后返回篡改后的 typetree。"""

    def __init__(self, objects):
        self.objects = objects
        self.files = {}

    def load(self, paths):
        pass


def test_verify_saved_bundle_detects_immutable_field_drift(monkeypatch):
    import UnityPy

    baseline_tree = {
        "m_Name": "Menu",
        "m_TableData": [{"m_Id": 1, "m_Localized": "Play"}],
    }
    drifted_tree = {
        "m_Name": "Menu改",           # 不可变字段被意外改动
        "m_TableData": [{"m_Id": 1, "m_Localized": "开始游戏"}],
    }
    env = _FakeVerifierEnvironment([_FakeTypetreeObject(drifted_tree)])

    # 写回前收集：m_Name=Menu、m_Id=1 必须保持不变（重开后已漂移）
    immutable = _collect_immutable_values(baseline_tree)
    monkeypatch.setattr(UnityPy, "Environment", lambda: env)

    with pytest.raises(ValueError, match="验证失败"):
        _verify_saved_bundle(
            Path("unused"),
            expected_raw_by_path_id={},
            expected_immutable_values={("x.assets", 7): immutable})


def test_verify_saved_bundle_passes_when_immutable_intact(monkeypatch):
    import UnityPy

    tree = {
        "m_Name": "Menu",
        "m_TableData": [{"m_Id": 1, "m_Localized": "开始游戏"}],
    }
    env = _FakeVerifierEnvironment([_FakeTypetreeObject(tree)])
    immutable = _collect_immutable_values(tree)
    monkeypatch.setattr(UnityPy, "Environment", lambda: env)

    # m_Localized 变化不影响不可变校验
    _verify_saved_bundle(
        Path("unused"),
        expected_raw_by_path_id={},
        expected_immutable_values={("x.assets", 7): immutable})
