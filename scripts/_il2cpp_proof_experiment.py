"""Phase 4 前提实验：Il2CppDumper 假程序集（GenerateDummyDll=True）上跑证明链。

验证假程序集 IL 重建质量与证明率——决定 IL2CPP 游戏是否值得接入
证明链（决定 Phase 4 投入）。只读实验：不修改游戏文件。

用法：runtime/python/python.exe scripts/_il2cpp_proof_experiment.py <游戏目录>
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _find_inputs(game_dir: Path) -> tuple[Path, Path]:
    exe = next(game_dir.glob("*.exe"), None)
    if exe is None:
        raise SystemExit("未找到游戏 exe")
    meta = next(game_dir.rglob("global-metadata.dat"), None)
    if meta is None:
        raise SystemExit("未找到 global-metadata.dat")
    return exe, meta


def _run_dumper(game_dir: Path, exe: Path, meta: Path, workdir: Path):
    tools_dir = Path(__file__).resolve().parents[1] / "tools" / "Il2CppDumper"
    # 按 PE 机器类型选 dumper 位数（headache 32 位实证：x64 版报
    # "The file is a 32-bit file"）
    with exe.open("rb") as stream:
        head = stream.read(64)
    machine = int.from_bytes(head[60:64], "little") if len(head) >= 64 else 0
    pe_off = int.from_bytes(head[0x3C:0x40], "little") if len(head) >= 0x40 else 0
    with exe.open("rb") as stream:
        stream.seek(pe_off)
        pe_head = stream.read(24)
    machine = int.from_bytes(pe_head[4:6], "little")
    dumper = tools_dir / ("Il2CppDumper.exe" if machine == 0x8664
                          else "Il2CppDumper-x86.exe")
    config = {
        "RequireAnyKey": False,
        "DumpMethod": True,
        "DumpField": False,
        "DumpProperty": False,
        "DumpAttribute": False,
        "DumpFieldOffset": False,
        "DumpMethodOffset": False,
        "DumpTypeDefIndex": True,
        "GenerateDummyDll": True,
        "GenerateStruct": True,
        "DummyDllAddToken": True,
        "ForceIl2CppVersion": False,
        "ForceVersion": 16,
        "ForceDump": False,
        "NoRedirectedPointer": False,
    }
    for loc in (workdir / "config.json", game_dir / "il2cpp_data.json"):
        loc.parent.mkdir(parents=True, exist_ok=True)
        loc.write_text(json.dumps(config, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    proc = subprocess.run(
        [str(dumper), str(exe), str(meta), str(workdir)],
        capture_output=True, timeout=600)
    if proc.returncode != 0:
        print(proc.stdout.decode("utf-8", errors="replace")[-2000:])
        print(proc.stderr.decode("utf-8", errors="replace")[-2000:])
        raise SystemExit(f"Il2CppDumper 失败 rc={proc.returncode}")


def main() -> int:
    game_dir = Path(sys.argv[1])
    exe, meta = _find_inputs(game_dir)
    workdir = Path(tempfile.mkdtemp(prefix="il2cpp_proof_"))
    print(f"game: {game_dir.name}")
    print(f"inputs: {exe.name} + {meta.relative_to(game_dir)}")
    print("running Il2CppDumper (GenerateDummyDll=True)...")
    _run_dumper(game_dir, exe, meta, workdir)
    dll_dir = next(workdir.rglob("DummyDll"), None)
    if dll_dir is None:
        raise SystemExit("未生成 DummyDll")
    dlls = sorted(dll_dir.glob("*.dll"))
    print(f"dummy assemblies: {len(dlls)}")

    import dnfile
    from hanhua.core.unity.mono_dll import (_cross_assembly_ui_sinks,
                                            _decode_il, _method_il,
                                            _verified_ui_user_string_tokens,
                                            _walk_us_heap_records)
    pes = []
    for d in dlls:
        try:
            pes.append(dnfile.dnPE(str(d)))
        except Exception as exc:  # noqa: BLE001
            print(f"  load fail {d.name}: {exc}")
    print("cross-assembly closure...")
    sinks = _cross_assembly_ui_sinks(pes)
    print(f"sinks: {len(sinks)}")
    total_methods = decoded = 0
    total_literals = verified = with_space = 0
    verified_samples: list[str] = []
    for d, pe in zip(dlls, pes):
        try:
            methods = pe.net.mdtables.MethodDef.rows
            us = pe.net.user_strings
            heap_literals = 0
            heap_space = 0
            if us is not None:
                data = us.get_data_at_offset(0, us.sizeof())
                records = _walk_us_heap_records(data)
                heap_literals = len(records)
                heap_space = sum(1 for _, _, raw in records if b" " in raw)
                v = _verified_ui_user_string_tokens(pe, cross_sinks=sinks)
                for tok, _, raw in records:
                    if tok in v:
                        verified_samples.append(
                            raw[:-1].decode("utf-16-le", errors="replace"))
            total_literals += heap_literals
            with_space += heap_space
            verified += len(v)
        except Exception:  # noqa: BLE001
            continue
        for row in methods:
            total_methods += 1
            rva = int(getattr(row, "Rva", 0) or 0)
            if not rva:
                continue
            code = _method_il(pe, rva)
            if code is not None and _decode_il(code) is not None:
                decoded += 1
    print(f"methods: {total_methods}（IL 可解码 {decoded}，"
          f"{decoded / max(1, total_methods):.0%}）")
    print(f"dummy #US 字面量: {total_literals} | 含空格 {with_space}"
          f" | 已证明 UI {verified}")
    if total_literals:
        print(f"证明率: {verified / total_literals:.1%}")
    print(f"证明样本（前 20）: {verified_samples[:20]}")
    shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
