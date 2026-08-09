"""固定工具清单、路径边界与供应链完整性验证。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


class ToolManifestError(ValueError):
    """工具清单不可信或结构无效。"""


@dataclass(frozen=True)
class ToolFileSpec:
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    version: str
    adapter_version: str
    entry: Path
    size: int
    sha256: str
    capabilities: tuple[str, ...]
    required_files: tuple[ToolFileSpec, ...]


@dataclass(frozen=True)
class ToolStatus:
    tool_id: str
    state: str
    path: Path
    reason: str = ""


def _contained_path(root: Path, raw_path: object, field: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ToolManifestError(f"{field} 必须是非空相对路径")
    relative = Path(raw_path)
    if relative.is_absolute():
        raise ToolManifestError(f"{field} 必须位于应用目录内")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ToolManifestError(f"{field} 必须位于应用目录内") from exc
    return resolved


def _valid_size(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _normalized_sha256(value: object, field: str) -> str:
    if (not isinstance(value, str) or len(value) != 64
            or any(ch not in "0123456789abcdefABCDEF" for ch in value)):
        raise ToolManifestError(f"{field} SHA-256 无效")
    return value.upper()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


class ToolRegistry:
    def __init__(self, app_root: Path, specs: dict[str, ToolSpec]):
        self.app_root = app_root
        self.specs = specs

    @classmethod
    def load(cls, app_root: str | Path, manifest_path: str | Path | None = None) -> "ToolRegistry":
        root = Path(app_root).resolve()
        path = (Path(manifest_path).resolve() if manifest_path is not None
                else root / "resources" / "tools_manifest.json")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ToolManifestError(f"无法读取工具清单：{path}") from exc
        if (not isinstance(raw, dict)
                or type(raw.get("schema_version")) is not int
                or raw.get("schema_version") != 1
                or not isinstance(raw.get("tools"), list)):
            raise ToolManifestError("不支持的工具清单 schema")
        specs: dict[str, ToolSpec] = {}
        for item in raw["tools"]:
            if not isinstance(item, dict):
                raise ToolManifestError("工具记录必须是对象")
            tool_id = item.get("id")
            if not isinstance(tool_id, str) or not tool_id or tool_id in specs:
                raise ToolManifestError("工具 id 缺失或重复")
            size = item.get("size")
            sha256 = item.get("sha256")
            version = item.get("version")
            adapter_version = item.get("adapter_version")
            capabilities = item.get("capabilities")
            required = item.get("required_files", [])
            if not _valid_size(size):
                raise ToolManifestError(f"{tool_id} size 无效")
            normalized_sha = _normalized_sha256(sha256, tool_id)
            if not isinstance(version, str) or not version:
                raise ToolManifestError(f"{tool_id} version 无效")
            if not isinstance(adapter_version, str) or not adapter_version:
                raise ToolManifestError(f"{tool_id} adapter_version 无效")
            if (not isinstance(capabilities, list)
                    or not capabilities
                    or not all(isinstance(value, str) and value for value in capabilities)):
                raise ToolManifestError(f"{tool_id} capabilities 无效")
            if not isinstance(required, list):
                raise ToolManifestError(f"{tool_id} required_files 无效")
            required_specs: list[ToolFileSpec] = []
            for index, required_item in enumerate(required):
                field = f"{tool_id}.required_files[{index}]"
                if not isinstance(required_item, dict):
                    raise ToolManifestError(f"{field} 必须是对象")
                required_size = required_item.get("size")
                if not _valid_size(required_size):
                    raise ToolManifestError(f"{field} size 无效")
                required_specs.append(ToolFileSpec(
                    path=_contained_path(root, required_item.get("path"), field),
                    size=required_size,
                    sha256=_normalized_sha256(required_item.get("sha256"), field),
                ))
            specs[tool_id] = ToolSpec(
                tool_id=tool_id,
                version=version,
                adapter_version=adapter_version,
                entry=_contained_path(root, item.get("entry"), f"{tool_id}.entry"),
                size=size,
                sha256=normalized_sha,
                capabilities=tuple(capabilities),
                required_files=tuple(required_specs),
            )
        return cls(root, specs)

    def verify(self, tool_id: str) -> ToolStatus:
        try:
            spec = self.specs[tool_id]
        except KeyError as exc:
            raise ToolManifestError(f"未知工具：{tool_id}") from exc
        if not spec.entry.is_file():
            return ToolStatus(tool_id, "missing", spec.entry, "主程序不存在")
        missing = [item.path for item in spec.required_files if not item.path.is_file()]
        if missing:
            return ToolStatus(tool_id, "missing", spec.entry,
                              f"缺少必需文件：{missing[0].name}")
        if spec.entry.stat().st_size != spec.size:
            return ToolStatus(tool_id, "integrity_error", spec.entry, "文件大小不符")
        digest = _file_sha256(spec.entry)
        if digest != spec.sha256:
            return ToolStatus(tool_id, "integrity_error", spec.entry, "SHA-256 不符")
        for item in spec.required_files:
            if item.path.stat().st_size != item.size:
                return ToolStatus(tool_id, "integrity_error", spec.entry,
                                  f"{item.path.name} 文件大小不符")
            if _file_sha256(item.path) != item.sha256:
                return ToolStatus(tool_id, "integrity_error", spec.entry,
                                  f"{item.path.name} SHA-256 不符")
        return ToolStatus(tool_id, "verified", spec.entry)

    def statuses(self) -> dict[str, ToolStatus]:
        return {tool_id: self.verify(tool_id) for tool_id in self.specs}
