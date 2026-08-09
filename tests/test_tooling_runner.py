from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import threading

import pytest

from hanhua.core.tooling.manifest import ToolSpec
from hanhua.core.tooling.cache import VerifiedArtifactCache
from hanhua.core.tooling.runner import (
    IsolatedToolRunner,
    ToolCancelled,
    ToolIntegrityError,
    ToolOutputError,
    ToolTimeout,
)


def _cmd_spec() -> ToolSpec:
    entry = Path(os.environ["COMSPEC"]).resolve()
    return ToolSpec(
        tool_id="fixture_cmd",
        version="1",
        adapter_version="1",
        entry=entry,
        size=entry.stat().st_size,
        sha256=hashlib.sha256(entry.read_bytes()).hexdigest().upper(),
        capabilities=("fixture",),
        required_files=(),
    )


def _write_command(staged_entry, staged_inputs, output_dir):
    command = (
        f'copy /B /Y {staged_inputs["source.bin"]} {output_dir / "result.bin"} > nul '
        "& echo fixture-ok"
    )
    return [str(staged_entry), "/D", "/C", command]


def test_runner_isolates_inputs_and_reuses_verified_cache(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"safe input")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    runner = IsolatedToolRunner(tmp_path / "app-data")
    calls = []

    def command(*args):
        calls.append(1)
        return _write_command(*args)

    first = runner.run(
        _cmd_spec(), {"source.bin": source}, {"mode": "fixture"},
        command=command,
        validate=lambda output: [output / "result.bin"],
    )
    second = runner.run(
        _cmd_spec(), {"source.bin": source}, {"mode": "fixture"},
        command=command,
        validate=lambda output: [output / "result.bin"],
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls == [1]
    assert (second.artifact_dir / "result.bin").read_bytes() == b"safe input"
    assert "fixture-ok" in (second.artifact_dir / "stdout.log").read_text(encoding="utf-8")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_runner_normalizes_timeout_and_preserves_input(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"unchanged")
    runner = IsolatedToolRunner(tmp_path / "app-data")

    with pytest.raises(ToolTimeout, match="超时"):
        runner.run(
            _cmd_spec(), {"source.bin": source}, {"case": "timeout"},
            command=lambda entry, _inputs, _output: [
                str(entry), "/D", "/C",
                f'{Path(os.environ["SystemRoot"]) / "System32" / "PING.EXE"} '
                "127.0.0.1 -n 6 > nul"
            ],
            validate=lambda _output: [],
            timeout_s=0.1,
        )

    assert source.read_bytes() == b"unchanged"


def test_runner_discards_corrupt_cache_and_reruns(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"cache")
    runner = IsolatedToolRunner(tmp_path / "app-data")
    calls = []

    def command(*args):
        calls.append(1)
        return _write_command(*args)

    first = runner.run(
        _cmd_spec(), {"source.bin": source}, {"case": "corrupt"},
        command=command, validate=lambda output: [output / "result.bin"])
    (first.artifact_dir / "result.bin").write_bytes(b"tampered")

    second = runner.run(
        _cmd_spec(), {"source.bin": source}, {"case": "corrupt"},
        command=command, validate=lambda output: [output / "result.bin"])

    assert calls == [1, 1]
    assert second.cache_hit is False
    assert (second.artifact_dir / "result.bin").read_bytes() == b"cache"


def test_runner_rejects_validated_artifact_outside_output_root(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"safe")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"not an artifact")
    runner = IsolatedToolRunner(tmp_path / "app-data")

    with pytest.raises(ToolOutputError, match="输出目录"):
        runner.run(
            _cmd_spec(), {"source.bin": source}, {"case": "escape"},
            command=_write_command,
            validate=lambda _output: [outside],
        )


def test_runner_refuses_tool_spec_with_wrong_integrity(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"safe")
    spec = _cmd_spec()
    wrong = ToolSpec(
        tool_id=spec.tool_id, version=spec.version,
        adapter_version=spec.adapter_version, entry=spec.entry,
        size=spec.size, sha256="0" * 64,
        capabilities=spec.capabilities, required_files=spec.required_files,
    )
    runner = IsolatedToolRunner(tmp_path / "app-data")
    called = []

    with pytest.raises(ToolIntegrityError, match="SHA-256"):
        runner.run(
            wrong, {"source.bin": source}, {"case": "wrong-tool"},
            command=lambda *args: called.append(args) or _write_command(*args),
            validate=lambda output: [output / "result.bin"],
        )

    assert called == []


def test_runner_rejects_unvalidated_output_file(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"safe")
    runner = IsolatedToolRunner(tmp_path / "app-data")

    def command(entry, inputs, output):
        command_line = _write_command(entry, inputs, output)
        command_line[-1] += f' & echo unknown > {output / "unknown.txt"}'
        return command_line

    with pytest.raises(ToolOutputError, match="未验证"):
        runner.run(
            _cmd_spec(), {"source.bin": source}, {"case": "unknown-output"},
            command=command,
            validate=lambda output: [output / "result.bin"],
        )


def test_runner_discards_malformed_cache_manifest_and_reruns(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"manifest")
    runner = IsolatedToolRunner(tmp_path / "app-data")
    calls = []

    def command(*args):
        calls.append(1)
        return _write_command(*args)

    first = runner.run(
        _cmd_spec(), {"source.bin": source}, {"case": "bad-manifest"},
        command=command, validate=lambda output: [output / "result.bin"])
    manifest = first.artifact_dir / ".artifact_manifest.json"
    manifest.write_text(
        '{"schema_version":1,"files":{"result.bin":[]}}', encoding="utf-8")

    second = runner.run(
        _cmd_spec(), {"source.bin": source}, {"case": "bad-manifest"},
        command=command, validate=lambda output: [output / "result.bin"])

    assert calls == [1, 1]
    assert second.cache_hit is False


def test_runner_cancellation_terminates_running_process_tree(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"cancel")
    runner = IsolatedToolRunner(tmp_path / "app-data")
    cancel = threading.Event()
    timer = threading.Timer(0.15, cancel.set)
    timer.start()
    try:
        with pytest.raises(ToolCancelled, match="取消"):
            runner.run(
                _cmd_spec(), {"source.bin": source}, {"case": "cancel"},
                command=lambda entry, _inputs, _output: [
                    str(entry), "/D", "/C",
                    f'{Path(os.environ["SystemRoot"]) / "System32" / "PING.EXE"} '
                    "127.0.0.1 -n 6 > nul"
                ],
                validate=lambda _output: [],
                cancel_event=cancel,
                timeout_s=10,
            )
    finally:
        timer.cancel()

    assert source.read_bytes() == b"cancel"


def test_runner_rechecks_staged_tool_after_prepare(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"safe")
    runner = IsolatedToolRunner(tmp_path / "app-data")

    def tamper(_job, _inputs, staged_entry):
        staged_entry.write_bytes(b"tampered")

    with pytest.raises(ToolIntegrityError, match="执行前"):
        runner.run(
            _cmd_spec(), {"source.bin": source}, {"case": "prepare-tamper"},
            prepare=tamper, command=_write_command,
            validate=lambda output: [output / "result.bin"],
        )


def test_runner_requires_argv_entry_to_match_staged_tool(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"safe")
    runner = IsolatedToolRunner(tmp_path / "app-data")

    with pytest.raises(ToolIntegrityError, match="命令入口"):
        runner.run(
            _cmd_spec(), {"source.bin": source}, {"case": "argv-swap"},
            command=lambda _entry, inputs, output: _write_command(
                Path(os.environ["COMSPEC"]), inputs, output),
            validate=lambda output: [output / "result.bin"],
        )


def _make_junction(link: Path, target: Path) -> None:
    result = subprocess.run(
        [os.environ["COMSPEC"], "/D", "/C", "mklink", "/J", str(link), str(target)],
        capture_output=True, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        pytest.skip("当前 Windows 环境不允许创建测试 junction")


def test_runner_rejects_replaced_output_root_junction(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"safe")
    outside = tmp_path / "outside"
    outside.mkdir()
    runner = IsolatedToolRunner(tmp_path / "app-data")

    def replace_output(job, _inputs, _entry):
        output = job / "output"
        output.rmdir()
        _make_junction(output, outside)

    with pytest.raises(ToolOutputError, match="根目录被替换"):
        runner.run(
            _cmd_spec(), {"source.bin": source}, {"case": "output-junction"},
            prepare=replace_output, command=_write_command,
            validate=lambda output: [output / "result.bin"],
        )


def test_runner_discards_cache_target_junction_without_touching_target(tmp_path):
    source = tmp_path / "original.bin"
    source.write_bytes(b"safe")
    runner = IsolatedToolRunner(tmp_path / "app-data")
    calls = []

    def command(*args):
        calls.append(1)
        return _write_command(*args)

    first = runner.run(
        _cmd_spec(), {"source.bin": source}, {"case": "cache-junction"},
        command=command, validate=lambda output: [output / "result.bin"])
    outside = tmp_path / "outside-cache"
    shutil.copytree(first.artifact_dir, outside)
    shutil.rmtree(first.artifact_dir)
    _make_junction(first.artifact_dir, outside)

    second = runner.run(
        _cmd_spec(), {"source.bin": source}, {"case": "cache-junction"},
        command=command, validate=lambda output: [output / "result.bin"])

    assert calls == [1, 1]
    assert second.cache_hit is False
    assert (outside / "result.bin").read_bytes() == b"safe"


def test_cache_rejects_path_traversal_key_before_touching_filesystem(tmp_path):
    cache_root = tmp_path / "cache"
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    cache = VerifiedArtifactCache(cache_root)

    with pytest.raises(ValueError, match="缓存键"):
        cache.lookup("../outside")

    assert marker.read_text(encoding="utf-8") == "keep"
