"""启动冒烟与日志扫描测试（P0-5）。

不启动真实进程：通过注入的 launcher 模拟存活/崩溃/退出码，日志增量
扫描用真实临时文件验证。
"""
import time
from pathlib import Path

from hanhua.core.smoke import (
    SmokeResult,
    _scan_log_errors,
    find_player_executable,
    run_staging_smoke,
)


class FakeProc:
    """Popen 兼容替身：alive_until 之前 poll 返回 None，之后返回 exit_code。"""

    def __init__(self, exit_code=None, alive_until=None):
        self.exit_code = exit_code
        self.alive_until = alive_until
        self.terminated = False
        self.killed = False

    def poll(self):
        if self.alive_until is not None and time.perf_counter() < self.alive_until:
            return None
        if self.terminated or self.killed:
            return self.exit_code if self.exit_code is not None else -1
        return self.exit_code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.poll()


def _make_staging(tmp_path: Path, exe_name: str = "Game.exe") -> Path:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / exe_name).write_bytes(b"MZ fake")
    return staging


def test_find_player_executable_prefers_recorded_rel_path(tmp_path):
    staging = _make_staging(tmp_path)
    (staging / "Data").mkdir()
    (staging / "Data" / "Data.exe").write_bytes(b"MZ")
    assert find_player_executable(staging, Path("Game.exe")) == staging / "Game.exe"
    assert find_player_executable(
        staging, Path("missing.exe")) == staging / "Game.exe"


def test_find_player_executable_rejects_absolute_recorded_path(tmp_path):
    """防回归：传源目录绝对路径时必须在 staging 内解析（否则 pathlib
    拼接直接返回原路径，冒烟会启动原游戏而非汉化副本）。"""
    staging = _make_staging(tmp_path)
    original = tmp_path / "original" / "Game.exe"
    original.parent.mkdir()
    original.write_bytes(b"MZ")
    assert find_player_executable(staging, original) == staging / "Game.exe"
    # 绝对路径的文件名在 staging 中不存在 → 回退全局查找，但结果
    # 必须仍在 staging 内，绝不落到源目录原文件上
    assert find_player_executable(staging, tmp_path / "Nope.exe") == staging / "Game.exe"


def test_find_player_executable_matches_data_dir_sibling(tmp_path):
    staging = _make_staging(tmp_path, "A.exe")
    (staging / "B.exe").write_bytes(b"MZ")
    (staging / "A_Data").mkdir()
    (staging / "B_Data").mkdir()
    assert find_player_executable(staging) == staging / "A.exe"


def test_find_player_executable_none(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "note.txt").write_text("hi", encoding="utf-8")
    assert find_player_executable(staging) is None
    assert find_player_executable(staging, Path("missing.exe")) is None


def _launcher_for(proc):
    def launch(exe, cwd, stderr_path):
        return proc
    return launch


def test_run_smoke_passed_when_alive_to_timeout(tmp_path):
    staging = _make_staging(tmp_path)
    proc = FakeProc(alive_until=time.perf_counter() + 30)
    result = run_staging_smoke(
        staging, Path("Game.exe"), timeout=0.5,
        launcher=_launcher_for(proc))
    assert result.status == "passed"
    assert result.passed and not result.blocked and not result.unverifiable
    assert proc.terminated   # 存活到超时后必须被清理


def test_run_smoke_blocked_on_crash(tmp_path):
    staging = _make_staging(tmp_path)
    result = run_staging_smoke(
        staging, Path("Game.exe"), timeout=2.0,
        launcher=_launcher_for(FakeProc(exit_code=3221225477)))
    assert result.status == "blocked"
    assert result.exit_code == 3221225477
    assert "崩溃" in result.detail


def test_run_smoke_warn_on_quick_zero_exit(tmp_path):
    staging = _make_staging(tmp_path)
    result = run_staging_smoke(
        staging, Path("Game.exe"), timeout=2.0,
        launcher=_launcher_for(FakeProc(exit_code=0)))
    assert result.status == "warn"
    assert result.exit_code == 0


def test_run_smoke_unverifiable_without_executable(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    result = run_staging_smoke(staging, Path("Game.exe"), timeout=0.5)
    assert result.status == "unverifiable"


def test_run_smoke_unverifiable_on_launch_error(tmp_path):
    staging = _make_staging(tmp_path)

    def failing_launch(exe, cwd, stderr_path):
        raise OSError("CreateProcess failed")

    result = run_staging_smoke(
        staging, Path("Game.exe"), timeout=0.5, launcher=failing_launch)
    assert result.status == "unverifiable"
    assert "无法启动" in result.detail


def test_run_smoke_warn_on_log_errors(tmp_path):
    staging = _make_staging(tmp_path)
    log = tmp_path / "Player.log"
    log.write_text("Loading scene\nall fine\n", encoding="utf-8")
    proc = FakeProc(alive_until=time.perf_counter() + 30)

    def launch_with_log_error(exe, cwd, stderr_path):
        # 快照在 launcher 之前：这里追加的内容是“启动后新增”段
        with log.open("a", encoding="utf-8") as fh:
            fh.write("CRC Mismatch detected\n")
        return proc

    result = run_staging_smoke(
        staging, Path("Game.exe"), timeout=0.5,
        launcher=launch_with_log_error, log_paths=(log,))
    assert result.status == "warn"
    assert any("CRC Mismatch" in line for line in result.log_errors)


def test_scan_log_errors_only_scans_new_section(tmp_path):
    log = tmp_path / "Player.log"
    log.write_text("old line with ERROR: before start\n", encoding="utf-8")
    size = log.stat().st_size
    wall = time.time()
    time.sleep(0.01)
    log.write_text(log.read_text(encoding="utf-8")
                   + "new ERROR: line\nclean line\n", encoding="utf-8")
    errors, new_bytes = _scan_log_errors(log, size, wall)
    assert len(errors) == 1 and "new ERROR: line" in errors[0]
    assert new_bytes > 0


def test_scan_log_errors_ignores_unchanged_log(tmp_path):
    log = tmp_path / "Player.log"
    log.write_text("no errors\n", encoding="utf-8")
    errors, new_bytes = _scan_log_errors(log, log.stat().st_size, time.time())
    assert errors == [] and new_bytes == 0


def test_smoke_result_defaults():
    result = SmokeResult("unverifiable", "no exe")
    assert result.unverifiable and not result.passed and not result.blocked
