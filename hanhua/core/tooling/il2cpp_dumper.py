"""Il2CppDumper 私有配置、sidecar 验证与原生结果交叉报告。"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import unicodedata

from hanhua.core.tooling.manifest import ToolSpec
from hanhua.core.tooling.runner import IsolatedToolRunner, ToolRunResult


class Il2CppOutputError(ValueError):
    pass


@dataclass(frozen=True)
class Il2CppLiteral:
    value: str
    address: int


@dataclass(frozen=True)
class LiteralComparison:
    native_total: int
    sidecar_total: int
    intersection: int
    native_only: int
    sidecar_only: int
    agreement: float
    anchors_found: tuple[str, ...] = ()
    anchors_missing: tuple[str, ...] = ()


_ADDRESS = re.compile(r"^0x[0-9A-Fa-f]+$")
_ALLOWED_CONTROLS = {"\t", "\n", "\r"}
_LOG_DIR_MARKER = re.compile(r"；日志：(?P<dir>.+)$")


def _enrich_dumper_failure(exc: Exception) -> Exception:
    """外部 dumper 失败时，把工具日志中的 metadata 版本缺口提升进 reason。

    Il2CppDumper 遇不支持的 metadata 版本会打印 NotSupportedException 但
    以退出码 0 结束，导致失败被误报为 sidecar JSON 损坏。此处从 runner
    保留的日志里识别版本缺口，追加到异常消息，供上层降级判定（#183）。
    """
    message = exc.args[0] if exc.args else ""
    match = _LOG_DIR_MARKER.search(message)
    if match is None:
        return exc
    log_dir = Path(match.group("dir").strip())
    for name in ("stderr.log", "stdout.log"):
        log = log_dir / name
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if "not a supported version" not in line.casefold():
                continue
            line = line.strip()
            if exc.args:
                exc.args = (f"{message}（工具日志：{line}）", *exc.args[1:])
            else:
                exc.args = (f"工具日志：{line}",)
            return exc
    return exc


def _illegal_controls(value: str) -> bool:
    return any((ord(char) < 0x20 and char not in _ALLOWED_CONTROLS)
               or 0x7F <= ord(char) <= 0x9F for char in value)


def write_private_config(source: str | Path, destination: str | Path) -> Path:
    source_path = Path(source)
    destination_path = Path(destination)
    try:
        config = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Il2CppOutputError("Il2CppDumper 原配置不可读") from exc
    if not isinstance(config, dict):
        raise Il2CppOutputError("Il2CppDumper 原配置必须是 JSON 对象")
    config = {
        "RequireAnyKey": False,
        "DumpMethod": True,
        "DumpField": False,
        "DumpProperty": False,
        "DumpAttribute": False,
        "DumpFieldOffset": False,
        "DumpMethodOffset": False,
        "DumpTypeDefIndex": True,
        "GenerateDummyDll": False,
        "GenerateStruct": True,
        "DummyDllAddToken": False,
        "ForceIl2CppVersion": False,
        "ForceVersion": 16,
        "ForceDump": False,
        "NoRedirectedPointer": False,
    }
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination_path


def load_string_literals(path: str | Path) -> tuple[Il2CppLiteral, ...]:
    sidecar = Path(path)
    if not sidecar.is_file() or sidecar.stat().st_size > 256 * 1024 * 1024:
        raise Il2CppOutputError("stringliteral.json 缺失或过大")
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Il2CppOutputError("stringliteral.json 不是有效 UTF-8 JSON") from exc
    if not isinstance(raw, list) or len(raw) > 2_000_000:
        raise Il2CppOutputError("stringliteral.json 顶层必须是受限数组")
    literals = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise Il2CppOutputError(f"literal[{index}] 必须是对象")
        value = item.get("value")
        address = item.get("address")
        if (not isinstance(value, str) or len(value) > 1_000_000
                or not isinstance(address, str) or _ADDRESS.fullmatch(address) is None
                or len(address) > 18):
            raise Il2CppOutputError(f"literal[{index}] schema 无效")
        if not value or _illegal_controls(value):
            raise Il2CppOutputError(f"literal[{index}] 含空串或非法控制字符")
        literals.append(Il2CppLiteral(value=value, address=int(address, 16)))
    return tuple(literals)


def sanitize_string_literals(path: str | Path, report_path: str | Path) -> dict:
    """把工具原始 sidecar 规范化为严格可加载版本，并审计被拒记录。"""
    sidecar = Path(path)
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Il2CppOutputError("stringliteral.json 不是有效 UTF-8 JSON") from exc
    if not isinstance(raw, list) or len(raw) > 2_000_000:
        raise Il2CppOutputError("stringliteral.json 顶层必须是受限数组")
    accepted = []
    rejected = {"empty": 0, "illegal_control": 0}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise Il2CppOutputError(f"literal[{index}] 必须是对象")
        value = item.get("value")
        address = item.get("address")
        if (not isinstance(value, str) or len(value) > 1_000_000
                or not isinstance(address, str) or _ADDRESS.fullmatch(address) is None
                or len(address) > 18):
            raise Il2CppOutputError(f"literal[{index}] schema 无效")
        if not value:
            rejected["empty"] += 1
            continue
        if _illegal_controls(value):
            rejected["illegal_control"] += 1
            continue
        accepted.append({"value": value, "address": address})
    if not accepted:
        raise Il2CppOutputError("stringliteral.json 没有可交叉验证的有效记录")
    report = {
        "schema_version": 1,
        "source_records": len(raw),
        "accepted_records": len(accepted),
        "normalized_unique_records": len(
            _normalized(item["value"] for item in accepted)),
        "rejected": rejected,
    }
    sidecar.write_text(
        json.dumps(accepted, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    Path(report_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    load_string_literals(sidecar)
    return report


def _normalized(values) -> set[str]:
    return {normalized for value in values
            if (normalized := unicodedata.normalize("NFKC", value).strip())}


def compare_literals(native_values, sidecar: tuple[Il2CppLiteral, ...],
                     required_anchors=()) -> LiteralComparison:
    native_set = _normalized(native_values)
    sidecar_set = _normalized(item.value for item in sidecar)
    intersection = len(native_set & sidecar_set)
    denominator = max(len(native_set), len(sidecar_set), 1)
    anchors = tuple(unicodedata.normalize("NFKC", value).strip()
                    for value in required_anchors if str(value).strip())
    return LiteralComparison(
        native_total=len(native_set),
        sidecar_total=len(sidecar_set),
        intersection=intersection,
        native_only=len(native_set - sidecar_set),
        sidecar_only=len(sidecar_set - native_set),
        agreement=intersection / denominator,
        anchors_found=tuple(value for value in anchors if value in sidecar_set),
        anchors_missing=tuple(value for value in anchors if value not in sidecar_set),
    )


def run_il2cpp_dumper(
    runner: IsolatedToolRunner,
    spec: ToolSpec,
    executable: str | Path,
    metadata: str | Path,
    source_config: str | Path,
    *,
    timeout_s: float = 180,
) -> tuple[ToolRunResult, tuple[Il2CppLiteral, ...]]:
    source_config = Path(source_config)
    job_root: list[Path] = []

    def prepare(job, _inputs, entry):
        job_root[:] = [job]
        write_private_config(source_config, job / "config.json")
        write_private_config(source_config, entry.parent / "config.json")

    def command(entry, inputs, output):
        return [str(entry), str(inputs["game.exe"]),
                str(inputs["global-metadata.dat"]), str(output)]

    def validate(output):
        sidecar = output / "stringliteral.json"
        if not sidecar.is_file() and job_root:
            matches = [path for path in job_root[0].rglob("stringliteral.json")
                       if path != sidecar]
            if len(matches) == 1:
                matches[0].replace(sidecar)
        report_path = output / "validation-report.json"
        sanitize_string_literals(sidecar, report_path)
        for item in list(output.iterdir()):
            if item in {sidecar, report_path}:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        return [sidecar, report_path]

    try:
        result = runner.run(
            spec,
            {"game.exe": executable, "global-metadata.dat": metadata},
            {"mode": "literal_cross_check"},
            prepare=prepare, command=command, validate=validate, timeout_s=timeout_s,
        )
    except Exception as exc:  # noqa: BLE001 外部工具失败需提升日志原因
        raise _enrich_dumper_failure(exc) from exc
    return result, load_string_literals(result.artifact_dir / "stringliteral.json")
