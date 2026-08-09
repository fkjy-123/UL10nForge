"""Conservative discovery of safe Unity player filesystem layouts."""
from __future__ import annotations

from dataclasses import dataclass
import json
import mmap
from pathlib import Path
import struct
from typing import Literal

from hanhua.core.paths import _is_reparse_point


_MAX_MANIFEST_BYTES = 8 * 1024 * 1024
_MAX_DISCOVERY_DIRECTORIES = 4096
_MAX_DIRECTORY_ENTRIES = 65536
_FRAMEWORK_ASSEMBLY_PREFIXES = (
    "unityengine.", "unityeditor.", "system.",
)
_FRAMEWORK_ASSEMBLY_NAMES = frozenset({
    "microsoft.csharp.dll", "mono.security.dll", "mscorlib.dll", "netstandard.dll",
})
_PACKAGE_ASSEMBLY_NAMES = frozenset({
    "newtonsoft.json.dll",
    "unity.inputsystem.dll",
    "unity.localization.dll",
    "unity.postprocessing.runtime.dll",
    "unity.textmeshpro.dll",
    "unity.timeline.dll",
    "unity.visualscripting.antlr3.runtime.dll",
    "unity.visualscripting.core.dll",
    "unity.visualscripting.flow.dll",
    "unity.visualscripting.state.dll",
    # Demigiant DOTween 第三方插件：库内部日志（DOShakePosition: ... 调试消息
    # 与 "DOTWEEN ► " 前缀）会进翻译池且模型必失败（The Last Debug 真实样本）
    "dotween.dll",
    "dotween.modules.dll",
    "dotweenpro.dll",
    "dotweenpro.modules.dll",
    # websocket-sharp 网络库：内部 HTTP 协议字符串（HTTP/1.1 100 Continue 等）
    # 非游戏文本（Slendergus 真实样本）
    "websocket-sharp.dll",
})
_PACKAGE_ASSEMBLY_PREFIXES = (
    "unity.renderpipelines.",
)


@dataclass(frozen=True)
class PlayerLayout:
    source_root: Path
    player_root: Path
    layout_kind: Literal["standard", "flat", "nested_standard"]
    executable: Path
    data_dir: Path
    managed_dir: Path | None
    application_assemblies: tuple[Path, ...]
    game_assembly: Path | None
    metadata: Path | None


class PlayerLayoutError(ValueError):
    """Stable, path-free signal for corrupt or unsafe layout structure."""


class _DiscoveryLimit(ValueError):
    """Internal fail-closed signal for bounded discovery limits."""


def _u16(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 2 > len(data):
        return None
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(data):
        return None
    return struct.unpack_from("<I", data, offset)[0]


def _is_pe_buffer(data, *, require_cli: bool) -> bool:
    if len(data) < 0x40 or data[:2] != b"MZ":
        return False
    pe_offset = _u32(data, 0x3C)
    if pe_offset is None or pe_offset + 24 > len(data):
        return False
    if data[pe_offset:pe_offset + 4] != b"PE\0\0":
        return False
    section_count = _u16(data, pe_offset + 6)
    optional_size = _u16(data, pe_offset + 20)
    if section_count is None or section_count == 0 or optional_size is None:
        return False
    optional = pe_offset + 24
    section_table = optional + optional_size
    if optional_size < 2 or section_table + section_count * 40 > len(data):
        return False
    magic = _u16(data, optional)
    if magic == 0x10B:
        directory_count_offset, directories_offset = 92, 96
    elif magic == 0x20B:
        directory_count_offset, directories_offset = 108, 112
    else:
        return False
    if optional_size < directory_count_offset + 4:
        return False

    sections: list[tuple[int, int, int, int]] = []
    for index in range(section_count):
        header = section_table + index * 40
        values = tuple(_u32(data, header + offset) for offset in (8, 12, 16, 20))
        if any(value is None for value in values):
            return False
        virtual_size, virtual_address, raw_size, raw_offset = values
        assert virtual_size is not None and virtual_address is not None
        assert raw_size is not None and raw_offset is not None
        if raw_size and (raw_offset > len(data) or raw_size > len(data) - raw_offset):
            return False
        sections.append((virtual_address, virtual_size, raw_offset, raw_size))

    def mapped_offset(rva: int, size: int) -> int | None:
        if rva <= 0 or size <= 0:
            return None
        for virtual_address, virtual_size, raw_offset, raw_size in sections:
            span = max(virtual_size, raw_size)
            if rva < virtual_address or rva - virtual_address >= span:
                continue
            delta = rva - virtual_address
            if delta > raw_size or size > raw_size - delta:
                return None
            offset = raw_offset + delta
            return offset if offset <= len(data) and size <= len(data) - offset else None
        return None

    if not require_cli:
        return True
    directory_count = _u32(data, optional + directory_count_offset)
    cli_directory = optional + directories_offset + 14 * 8
    if (directory_count is None or directory_count <= 14
            or cli_directory + 8 > section_table):
        return False
    cli_rva = _u32(data, cli_directory)
    cli_size = _u32(data, cli_directory + 4)
    if cli_rva is None or cli_size is None or cli_size < 0x48:
        return False
    cli_offset = mapped_offset(cli_rva, cli_size)
    if cli_offset is None:
        return False
    header_size = _u32(data, cli_offset)
    metadata_rva = _u32(data, cli_offset + 8)
    metadata_size = _u32(data, cli_offset + 12)
    if (header_size is None or header_size < 0x48 or header_size > cli_size
            or metadata_rva is None or metadata_size is None or metadata_size < 4):
        return False
    metadata_offset = mapped_offset(metadata_rva, metadata_size)
    return metadata_offset is not None and data[metadata_offset:metadata_offset + 4] == b"BSJB"


def is_pe_image(path: Path, *, require_cli: bool = False) -> bool:
    """Return whether *path* is a bounded PE image, optionally with valid CLI metadata."""
    try:
        with path.open("rb") as stream, mmap.mmap(
                stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            return _is_pe_buffer(data, require_cli=require_cli)
    except (OSError, ValueError):
        return False


def _trusted_path(source_root: Path, candidate: Path) -> Path | None:
    lexical_root = source_root.absolute()
    lexical_candidate = candidate.absolute()
    try:
        relative = lexical_candidate.relative_to(lexical_root)
    except ValueError:
        return None
    current = lexical_root
    if _is_reparse_point(current):
        return None
    for part in relative.parts:
        current /= part
        if _is_reparse_point(current):
            return None
    try:
        resolved_root = lexical_root.resolve()
        resolved = lexical_candidate.resolve()
        resolved.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    return resolved


def _children(source_root: Path, parent: Path) -> tuple[Path, ...]:
    safe_parent = _trusted_path(source_root, parent)
    if safe_parent is None or not safe_parent.is_dir():
        raise PlayerLayoutError("unsafe_directory")
    entries: list[Path] = []
    for index, entry in enumerate(safe_parent.iterdir()):
        if index >= _MAX_DIRECTORY_ENTRIES:
            raise _DiscoveryLimit("directory_entry_limit")
        entries.append(entry)
    names: set[str] = set()
    safe: list[Path] = []
    for entry in entries:
        canonical = entry.name.casefold()
        if canonical in names:
            raise PlayerLayoutError("duplicate_canonical_entry")
        names.add(canonical)
        resolved = _trusted_path(source_root, entry)
        if resolved is not None:
            safe.append(resolved)
    return tuple(safe)


def _direct_named(source_root: Path, parent: Path, name: str,
                  *, directory: bool = False) -> Path | None:
    matches = [entry for entry in _children(source_root, parent)
               if entry.name.casefold() == name.casefold()
               and (entry.is_dir() if directory else entry.is_file())]
    return matches[0] if len(matches) == 1 else None


def discover_application_assemblies(
        source_root: Path, data_dir: Path) -> tuple[Path, ...]:
    """Discover direct, valid application assemblies for one Unity data root."""
    source = source_root.absolute()
    safe_data = _trusted_path(source, data_dir)
    if safe_data is None or not safe_data.is_dir():
        return ()
    try:
        data_children = _children(source, safe_data)
        managed_matches = [entry for entry in data_children
                           if entry.name.casefold() == "managed" and entry.is_dir()]
        managed = managed_matches[0] if len(managed_matches) == 1 else None
        if managed is None:
            return ()
        manifest_matches = [entry for entry in data_children
                            if entry.name.casefold() == "scriptingassemblies.json"]
        if manifest_matches and not manifest_matches[0].is_file():
            return ()
        manifest = manifest_matches[0] if manifest_matches else None
        managed_files = {entry.name.casefold(): entry
                         for entry in _children(source, managed) if entry.is_file()}
    except (OSError, _DiscoveryLimit):
        return ()

    if manifest is not None:
        try:
            if manifest.stat().st_size > _MAX_MANIFEST_BYTES:
                return ()
            with manifest.open("rb") as stream:
                raw_manifest = stream.read(_MAX_MANIFEST_BYTES + 1)
            if len(raw_manifest) > _MAX_MANIFEST_BYTES:
                return ()
            payload = json.loads(raw_manifest.decode("utf-8-sig"))
        except (OSError, UnicodeError, RecursionError, ValueError):
            return ()
        if not isinstance(payload, dict):
            return ()
        names, types = payload.get("names"), payload.get("types")
        if (not isinstance(names, list) or not isinstance(types, list)
                or len(names) != len(types)):
            return ()
        selected: list[Path] = []
        canonical_names: set[str] = set()
        for name, assembly_type in zip(names, types):
            if (not isinstance(name, str) or not name
                    or Path(name).name != name
                    or Path(name).suffix.casefold() != ".dll"
                    or type(assembly_type) is not int):
                return ()
            canonical_name = name.casefold()
            if canonical_name in canonical_names:
                return ()
            canonical_names.add(canonical_name)
            if assembly_type != 16:
                continue
            if not _is_application_assembly_name(name):
                continue
            assembly = managed_files.get(name.casefold())
            if assembly is None or not is_pe_image(assembly, require_cli=True):
                return ()
            selected.append(assembly)
        return tuple(sorted(
            selected, key=lambda path: (path.name.casefold(), path.name)))

    fallback = [entry for entry in managed_files.values()
                if entry.suffix.casefold() == ".dll"
                and entry.name.casefold().startswith(
                    ("assembly-csharp", "assembly-unityscript"))
                and is_pe_image(entry, require_cli=True)]
    return tuple(sorted(fallback, key=lambda path: (path.name.casefold(), path.name)))


def _is_application_assembly_name(name: str) -> bool:
    canonical = name.casefold()
    if canonical.startswith(("assembly-csharp", "assembly-unityscript")):
        return True
    return (canonical not in _FRAMEWORK_ASSEMBLY_NAMES
            and canonical not in _PACKAGE_ASSEMBLY_NAMES
            and not canonical.startswith(
                _FRAMEWORK_ASSEMBLY_PREFIXES + _PACKAGE_ASSEMBLY_PREFIXES))


_EXCLUDED_EXE_ROLES = (
    "unitycrashhandler", "installer", "setup", "uninstall", "updater",
    "update", "launcher", "crashreporter", "crash-reporter",
)
_UNITY_MARKERS = ("globalgamemanagers", "mainData", "data.unity3d")


def _backend_evidence(source: Path, data_dir: Path, player_root: Path) -> tuple[
        Path | None, tuple[Path, ...], Path | None, Path | None]:
    assemblies = discover_application_assemblies(source, data_dir)
    try:
        managed = _direct_named(source, data_dir, "Managed", directory=True)
        game_assembly = _direct_named(source, player_root, "GameAssembly.dll")
        il2cpp_data = _direct_named(source, data_dir, "il2cpp_data", directory=True)
        metadata_dir = (_direct_named(source, il2cpp_data, "Metadata", directory=True)
                        if il2cpp_data is not None else None)
        metadata = (_direct_named(source, metadata_dir, "global-metadata.dat")
                    if metadata_dir is not None else None)
    except (OSError, _DiscoveryLimit):
        return None, (), None, None
    has_il2cpp = bool(
        game_assembly is not None and is_pe_image(game_assembly)
        and metadata is not None and _has_metadata_magic(metadata))
    if not has_il2cpp:
        game_assembly, metadata = None, None
    return managed, assemblies, game_assembly, metadata


def _has_metadata_magic(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            return stream.read(4) == struct.pack("<I", 0xFAB11BAF)
    except OSError:
        return False


def _layout(source: Path, player_root: Path, data_dir: Path, executable: Path,
            kind: Literal["standard", "flat", "nested_standard"]
            ) -> PlayerLayout | None:
    managed, assemblies, game_assembly, metadata = _backend_evidence(
        source, data_dir, player_root)
    if not assemblies and (game_assembly is None or metadata is None):
        return None
    return PlayerLayout(
        source, player_root, kind, executable, data_dir, managed, assemblies,
        game_assembly, metadata)


def _standard_at(source: Path, root: Path) -> tuple[PlayerLayout, ...]:
    try:
        children = _children(source, root)
    except (OSError, _DiscoveryLimit):
        return ()
    executables = {entry.stem.casefold(): entry for entry in children
                   if entry.is_file() and entry.suffix.casefold() == ".exe"
                   and is_pe_image(entry)}
    layouts: list[PlayerLayout] = []
    for data_dir in children:
        if not data_dir.is_dir() or not data_dir.name.casefold().endswith("_data"):
            continue
        executable = executables.get(data_dir.name[:-5].casefold())
        if executable is None:
            continue
        kind: Literal["standard", "nested_standard"] = (
            "standard" if root == source else "nested_standard")
        candidate = _layout(source, root, data_dir, executable, kind)
        if candidate is not None:
            layouts.append(candidate)
    return tuple(sorted(layouts, key=lambda item: (
        item.executable.name.casefold(), item.executable.name,
        item.data_dir.name.casefold(), item.data_dir.name,
    )))


def _flat_at(source: Path) -> PlayerLayout | None:
    try:
        children = _children(source, source)
    except (OSError, _DiscoveryLimit):
        return None
    executables = [entry for entry in children
                   if entry.is_file() and entry.suffix.casefold() == ".exe"
                   and not any(role in entry.name.casefold()
                               for role in _EXCLUDED_EXE_ROLES)
                   and is_pe_image(entry)]
    markers = {entry.name.casefold() for entry in children if entry.is_file()}
    if len(executables) != 1 or not any(name.casefold() in markers
                                        for name in _UNITY_MARKERS):
        return None
    return _layout(source, source, source, executables[0], "flat")


def discover_player_candidates(
        source_root: str | Path) -> tuple[PlayerLayout, ...]:
    """Return deterministic, strongly evidenced Unity player candidates."""
    lexical = Path(source_root).expanduser().absolute()
    if _is_reparse_point(lexical) or not lexical.is_dir():
        return ()
    try:
        source = lexical.resolve()
    except OSError:
        return ()
    candidates: list[PlayerLayout] = []
    flat = _flat_at(source)
    if flat is not None:
        candidates.append(flat)
    pending = [source]
    visited_directories = 0
    while pending:
        current = pending.pop()
        visited_directories += 1
        if visited_directories > _MAX_DISCOVERY_DIRECTORIES:
            return ()
        standard = _standard_at(source, current)
        if standard:
            candidates.extend(standard)
        try:
            directories = [entry for entry in _children(source, current)
                           if entry.is_dir()
                           and not entry.name.casefold().endswith("_data")
                           and entry.name.casefold() not in {
                               "managed", "il2cpp_data", "streamingassets",
                           }]
        except (OSError, _DiscoveryLimit):
            return ()
        pending.extend(reversed(sorted(
            directories, key=lambda path: (path.name.casefold(), path.name))))
    unique: dict[tuple[str, str], PlayerLayout] = {}
    for candidate in candidates:
        relative = candidate.player_root.relative_to(source)
        executable_relative = candidate.executable.relative_to(source)
        key = (
            str(relative).replace("\\", "/").casefold(),
            str(executable_relative).replace("\\", "/").casefold(),
        )
        if key in unique:
            raise PlayerLayoutError("duplicate_player_candidate")
        unique[key] = candidate
    return tuple(sorted(unique.values(), key=lambda item: (
        str(item.player_root.relative_to(source)).replace("\\", "/").casefold(),
        str(item.player_root.relative_to(source)).replace("\\", "/"),
        str(item.executable.relative_to(source)).replace("\\", "/").casefold(),
        str(item.executable.relative_to(source)).replace("\\", "/"),
    )))
