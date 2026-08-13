"""从只读文件布局生成确定性的 Unity 游戏指纹。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct
from typing import Literal

from hanhua.core.paths import _is_reparse_point
from hanhua.core.scanner import _has_unity_bundle_magic
from hanhua.core.unity.il2cpp import SUPPORTED_LITERAL_RECORD_SIZES
from hanhua.core.tooling.player_layout import (
    PlayerLayout,
    PlayerLayoutError,
    discover_player_candidates,
)


class FingerprintError(ValueError):
    pass


@dataclass(frozen=True)
class GameFingerprint:
    game_dir: Path
    player_root: Path | None
    layout_kind: str
    application_assemblies: tuple[Path, ...]
    unity_version: str
    runtime: Literal["mono", "il2cpp", "unknown"]
    executable: Path | None
    data_dir: Path | None
    metadata: Path | None
    game_assembly: Path | None
    metadata_version: int | None
    evidence: tuple[str, ...]
    capabilities: tuple[str, ...] = ()
    #: 存在的字体渲染栈（tmp/ugui/ngui/bitmap_font/runtime_font_fallback/
    #: unverified_font_stack）——Phase 2 消费者清单的来源（审计 §7.2）
    font_stacks: tuple[str, ...] = ()


#: evidence 键 → 字体渲染栈名（字体闭环 Phase 1）
_FONT_STACK_BY_EVIDENCE = (
    ("tmp", "tmp"),
    ("ugui", "ugui"),
    ("ngui", "ngui"),
    ("bitmap_font", "bitmap_font"),
)


def _derive_font_stacks(evidence: tuple[str, ...],
                        capabilities: tuple[str, ...]) -> tuple[str, ...]:
    """从指纹证据/能力派生字体渲染栈。

    tmp/ugui/ngui/bitmap_font 来自 DLL 与 .fnt 指纹；runtime_font_fallback
    来自 mono 运行时能力。一个栈都没识别到 → unverified_font_stack——
    Phase 2 必须知道「栈未知」而不是假装没有字体（审计 §9 样本 7：
    未识别对象不得静默消失）。"""
    stacks = [name for key, name in _FONT_STACK_BY_EVIDENCE if key in evidence]
    if "runtime_font_fallback" in capabilities:
        stacks.append("runtime_font_fallback")
    if not stacks:
        stacks.append("unverified_font_stack")
    return tuple(stacks)


_UNITY_VERSION = re.compile(
    rb"(?<!\d)((?:20\d{2}|6000)\.\d+\.\d+[abcfpx]\d+)(?!\d)")


def _pair_unknown_standard_player(
        game_dir: Path) -> tuple[Path | None, Path | None]:
    """Preserve legacy unknown-runtime evidence for one safe EXE/Data pair."""
    children = [path for path in game_dir.iterdir()
                if not _is_reparse_point(path)]
    executables: dict[str, Path] = {}
    for path in children:
        if (not path.is_file() or path.suffix.casefold() != ".exe"
                or path.name.casefold().startswith("unitycrashhandler")):
            continue
        key = path.stem.casefold()
        if key in executables:
            raise FingerprintError("游戏目录包含大小写冲突的 EXE")
        executables[key] = path
    pairs = []
    for data_dir in children:
        if not data_dir.is_dir() or not data_dir.name.casefold().endswith("_data"):
            continue
        executable = executables.get(data_dir.name[:-5].casefold())
        if executable is not None:
            pairs.append((executable, data_dir))
    if len(pairs) > 1:
        raise FingerprintError("游戏目录包含多个 EXE/Data 精确配对")
    return pairs[0] if pairs else (None, None)


def _find_unity_version(data_dir: Path | None) -> str:
    if data_dir is None:
        return "unknown"
    for name in ("globalgamemanagers", "data.unity3d", "mainData"):
        path = data_dir / name
        if _is_reparse_point(path) or not path.is_file():
            continue
        with path.open("rb") as stream:
            match = _UNITY_VERSION.search(stream.read(2 * 1024 * 1024))
        if match:
            return match.group(1).decode("ascii")
        env = None
        try:
            import UnityPy
            env = UnityPy.load(str(path))
            version = str(getattr(env.file, "unity_version", "") or "")
        except Exception:  # noqa: BLE001 版本探测失败不能阻断整个 fingerprint
            version = ""
        finally:
            if env is not None:
                from hanhua.core.unity.writer import _dispose_environment
                _dispose_environment(env)
        if _UNITY_VERSION.fullmatch(version.encode("ascii", errors="ignore")):
            return version
    return "unknown"


def _metadata_version(path: Path | None) -> int | None:
    if path is None:
        return None
    try:
        head = path.read_bytes()[:8]
        magic, version = struct.unpack("<II", head)
    except (OSError, struct.error):
        return None
    return version if magic == 0xFAB11BAF else None


def _regular_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    pending = [root]
    while pending:
        current = pending.pop()
        for path in current.iterdir():
            if _is_reparse_point(path):
                continue
            if path.is_dir():
                pending.append(path)
            elif path.is_file():
                files.append(path)
    return tuple(files)


def _candidate_evidence(root: Path, candidates: tuple[PlayerLayout, ...]
                        ) -> tuple[str, ...]:
    return tuple(
        "player_candidate:"
        f"{candidate.player_root.relative_to(root).as_posix() or '.'}:"
        f"{candidate.executable.relative_to(root).as_posix()}"
        for candidate in candidates
    )


def _resolve_player_selector(
        root: Path, value: str | Path, *, name: str) -> Path:
    selector = Path(value).expanduser()
    lexical = (selector if selector.is_absolute() else root / selector).absolute()
    try:
        relative = lexical.relative_to(root)
    except ValueError as exc:
        raise FingerprintError(f"{name} 必须位于游戏源目录内") from exc
    if ".." in relative.parts:
        raise FingerprintError(f"{name} 必须位于游戏源目录内")
    current = root
    for part in relative.parts:
        current /= part
        if _is_reparse_point(current):
            raise FingerprintError(f"{name} 不得经过 reparse point")
    try:
        resolved = lexical.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise FingerprintError(f"{name} 必须位于游戏源目录内") from exc
    return resolved


def fingerprint_game(
        game_dir: str | Path, *, player_root: str | Path | None = None,
        player_executable: str | Path | None = None,
) -> GameFingerprint:
    lexical_root = Path(game_dir).expanduser().absolute()
    if _is_reparse_point(lexical_root):
        raise FingerprintError(f"游戏目录是 reparse point（重解析点）：{lexical_root}")
    expected_parent = lexical_root.parent.resolve()
    root = lexical_root.resolve()
    if root.parent != expected_parent:
        raise FingerprintError(f"游戏目录解析后逃逸父目录：{lexical_root}")
    if not root.is_dir():
        raise FingerprintError(f"游戏目录不存在：{root}")
    try:
        candidates = discover_player_candidates(root)
    except PlayerLayoutError as exc:
        raise FingerprintError(f"Unity player 布局不安全：{exc}") from exc
    selected: PlayerLayout | None = None
    if player_root is not None or player_executable is not None:
        matches = list(candidates)
        if player_root is not None:
            root_selector = _resolve_player_selector(
                root, player_root, name="player_root")
            matches = [candidate for candidate in matches
                       if candidate.player_root == root_selector]
        if player_executable is not None:
            executable_selector = _resolve_player_selector(
                root, player_executable, name="player_executable")
            matches = [candidate for candidate in matches
                       if candidate.executable == executable_selector]
        if len(matches) != 1:
            if (player_root is not None and player_executable is None
                    and len(matches) > 1):
                raise FingerprintError(
                    "player_root 匹配多个候选；必须提供 player_executable")
            selector_name = (
                "player_executable" if player_executable is not None
                else "player_root")
            raise FingerprintError(f"{selector_name} 必须精确匹配一个安全候选")
        selected = matches[0]
    elif len(candidates) == 1:
        selected = candidates[0]
    elif len(candidates) > 1:
        return GameFingerprint(
            game_dir=root,
            player_root=None,
            layout_kind="ambiguous",
            application_assemblies=(),
            unity_version="unknown",
            runtime="unknown",
            executable=None,
            data_dir=None,
            metadata=None,
            game_assembly=None,
            metadata_version=None,
            evidence=("ambiguous_player_layout", *_candidate_evidence(
                root, candidates)),
            capabilities=(),
            font_stacks=("unverified_font_stack",),
        )

    if selected is not None:
        executable, data_dir = selected.executable, selected.data_dir
    else:
        executable, data_dir = _pair_unknown_standard_player(root)
    application_assemblies = (
        selected.application_assemblies if selected is not None else ())
    game_assembly = selected.game_assembly if selected is not None else None
    metadata = selected.metadata if selected is not None else None
    metadata_version = _metadata_version(metadata)
    has_mono = bool(application_assemblies)
    has_il2cpp = bool(game_assembly and game_assembly.is_file() and metadata)
    runtime: Literal["mono", "il2cpp", "unknown"]
    runtime = ("unknown" if has_mono and has_il2cpp else
               "il2cpp" if has_il2cpp else "mono" if has_mono else "unknown")

    evidence: list[str] = []
    if executable and data_dir:
        evidence.append("player_pair")
    if has_mono:
        evidence.append("managed_assembly")
    if has_il2cpp:
        evidence.extend(("game_assembly", "global_metadata"))
        if metadata_version not in SUPPORTED_LITERAL_RECORD_SIZES:
            evidence.append("unsupported_il2cpp_metadata_version")
    if has_mono and has_il2cpp:
        evidence.append("ambiguous_runtime_backend")
    if data_dir is not None:
        data_files = _regular_files(data_dir)
        dll_names = {
            path.name.casefold() for path in data_files
            if path.suffix.casefold() == ".dll"
        }
        if any("textmeshpro" in name for name in dll_names):
            evidence.append("tmp")
        if "unityengine.ui.dll" in dll_names:
            evidence.append("ugui")
        if any("ngui" in name for name in dll_names):
            evidence.append("ngui")
        if any(path.suffix.casefold() == ".fnt" for path in data_files):
            evidence.append("bitmap_font")
        addressables = data_dir / "StreamingAssets" / "aa"
        if any(path.parent == addressables and path.name.casefold().startswith("catalog.")
               for path in data_files):
            evidence.append("addressables")
        has_bundle = False
        has_serialized = False
        for path in data_files:
            name = path.name.casefold()
            if path.suffix.casefold() == ".bundle":
                has_bundle = True
            elif _has_unity_bundle_magic(path):
                has_bundle = True
            if name in {"globalgamemanagers", "maindata", "data.unity3d"} \
                    or path.suffix.casefold() == ".assets" \
                    or re.fullmatch(r"level\d+", name):
                has_serialized = True
            if has_bundle and has_serialized:
                break
        if has_bundle:
            evidence.append("asset_bundle")
        if has_serialized:
            evidence.append("serialized_file")

    capabilities = ["native_text_extract"]
    writeback_allowed = selected is not None and runtime != "unknown"
    if writeback_allowed and executable is not None and data_dir is not None:
        capabilities.append("native_text_writeback")
    if "asset_bundle" in evidence or "serialized_file" in evidence:
        capabilities.append("native_asset_extract")
        if writeback_allowed:
            capabilities.append("native_asset_writeback")
    if runtime == "mono":
        capabilities.extend((
            "native_mono_literal_extract",
            "native_mono_literal_writeback",
            "runtime_font_fallback",
        ))
    elif runtime == "il2cpp" and metadata_version in SUPPORTED_LITERAL_RECORD_SIZES:
        capabilities.extend((
            "native_il2cpp_literal_extract",
            "native_il2cpp_literal_writeback",
        ))
    if "bitmap_font" in evidence:
        capabilities.extend((
            "bitmap_artifact_generation",
            "bitmap_injection_unverified",
        ))
    return GameFingerprint(
        game_dir=root,
        player_root=selected.player_root if selected is not None else None,
        layout_kind=selected.layout_kind if selected is not None else "unknown",
        application_assemblies=application_assemblies,
        unity_version=_find_unity_version(data_dir),
        runtime=runtime,
        executable=executable,
        data_dir=data_dir,
        metadata=metadata,
        game_assembly=game_assembly,
        metadata_version=metadata_version,
        evidence=tuple(evidence),
        capabilities=tuple(capabilities),
        font_stacks=_derive_font_stacks(tuple(evidence),
                                        tuple(capabilities)),
    )
