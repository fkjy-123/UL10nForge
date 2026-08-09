from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hanhua.core.tooling.manifest import ToolManifestError, ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_manifest(root: Path, entry: str, payload: bytes,
                    required_files: list[dict] | None = None) -> Path:
    manifest = root / "resources" / "tools_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "tools": [{
            "id": "fixture_tool",
            "version": "1.0",
            "adapter_version": "1",
            "entry": entry,
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest().upper(),
            "capabilities": ["fixture"],
            "required_files": required_files or [],
        }],
    }), encoding="utf-8")
    return manifest


def test_production_registry_contains_only_verified_automatic_tools():
    registry = ToolRegistry.load(PROJECT_ROOT)

    assert tuple(registry.specs) == ("il2cpp_dumper", "bmfont")
    assert registry.specs["il2cpp_dumper"].sha256 == (
        "071E36D396AE93CB2CFEC032513B46A6BFD67E9B93157830711AB6D79DB55045"
    )
    assert registry.specs["bmfont"].sha256 == (
        "4AEA5F359B4737253C521E29F87FC62D472FBEB9F9BA3A872353AB356A20E548"
    )
    assert registry.specs["il2cpp_dumper"].adapter_version == "3"
    assert registry.specs["bmfont"].adapter_version == "2"
    assert registry.specs["il2cpp_dumper"].capabilities == ("il2cpp_cross_check",)
    assert registry.specs["bmfont"].capabilities == ("bitmap_font_generation",)
    assert registry.specs["bmfont"].required_files[0].sha256 == (
        "628C898D666E3F9FD787315C6E3A6FDF11AAE429E401219E70EF32585FC81C4B"
    )
    assert {tool_id: status.state for tool_id, status in registry.statuses().items()} == {
        "il2cpp_dumper": "verified",
        "bmfont": "verified",
    }


def test_registry_detects_single_byte_integrity_change(tmp_path):
    payload = b"trusted executable"
    entry = tmp_path / "tools" / "fixture.exe"
    entry.parent.mkdir(parents=True)
    entry.write_bytes(payload)
    _write_manifest(tmp_path, "tools/fixture.exe", payload)
    registry = ToolRegistry.load(tmp_path)
    assert registry.verify("fixture_tool").state == "verified"

    entry.write_bytes(payload[:-1] + b"X")

    status = registry.verify("fixture_tool")
    assert status.state == "integrity_error"
    assert "SHA-256" in status.reason


def test_registry_detects_required_executable_integrity_change(tmp_path):
    launcher = b"trusted launcher"
    companion = b"trusted companion executable"
    entry = tmp_path / "tools" / "launcher.com"
    required = tmp_path / "tools" / "companion.exe"
    entry.parent.mkdir(parents=True)
    entry.write_bytes(launcher)
    required.write_bytes(companion)
    _write_manifest(tmp_path, "tools/launcher.com", launcher, [{
        "path": "tools/companion.exe",
        "size": len(companion),
        "sha256": hashlib.sha256(companion).hexdigest().upper(),
    }])
    registry = ToolRegistry.load(tmp_path)
    assert registry.verify("fixture_tool").state == "verified"

    required.write_bytes(companion[:-1] + b"X")

    status = registry.verify("fixture_tool")
    assert status.state == "integrity_error"
    assert "companion.exe" in status.reason


def test_registry_rejects_manifest_entry_outside_application_root(tmp_path):
    payload = b"outside"
    outside = tmp_path.parent / f"{tmp_path.name}-outside.exe"
    outside.write_bytes(payload)
    _write_manifest(tmp_path, f"../{outside.name}", payload)

    with pytest.raises(ToolManifestError, match="应用目录"):
        ToolRegistry.load(tmp_path)


@pytest.mark.parametrize("payload", [[], {"schema_version": True, "tools": []}])
def test_registry_normalizes_invalid_top_level_json(tmp_path, payload):
    manifest = tmp_path / "resources" / "tools_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ToolManifestError, match="schema"):
        ToolRegistry.load(tmp_path)


@pytest.mark.parametrize("field,value", [
    ("version", None),
    ("version", ["1.0"]),
    ("capabilities", None),
    ("capabilities", []),
])
def test_registry_requires_version_and_capabilities(tmp_path, field, value):
    payload = b"fixture"
    entry = tmp_path / "tools" / "fixture.exe"
    entry.parent.mkdir(parents=True)
    entry.write_bytes(payload)
    manifest = {
        "schema_version": 1,
        "tools": [{
            "id": "fixture_tool",
            "version": "1.0",
            "adapter_version": "1",
            "entry": "tools/fixture.exe",
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "capabilities": ["fixture"],
            "required_files": [],
        }],
    }
    if value is None:
        manifest["tools"][0].pop(field)
    else:
        manifest["tools"][0][field] = value
    path = tmp_path / "resources" / "tools_manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ToolManifestError, match=field):
        ToolRegistry.load(tmp_path)
