# -*- coding: utf-8 -*-
"""发行包分卷（2026-08-15）：复用 package.py 白名单清单，用 7-Zip
按 2GB/卷切分——GitHub Release 单文件上限 2GB，7.5GB 包分 4 卷
（.7z.001~.004），用户解压 .001 即得应用目录（与完整 zip 等价）。

用法：
    python scripts/_split_release.py            # 分卷到 dist/
    python scripts/_split_release.py --verify   # 只验证分卷完整性
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# GitHub 单文件上限 2GB 且校验为「必须小于 2147483648」（等于会被拒）
# → 2GiB - 1MiB（2146435072 字节/卷）
VOLUME_BYTES = 2 * 1024 * 1024 * 1024 - 1024 * 1024
SEVEN_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")
OUT_BASE = ROOT / "dist" / "UL10nForge-0.30.0-beta.7z"


def _collect() -> list[Path]:
    """复用 package.py 的发布白名单（与已验证的 zip 同一清单）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from package import _walk_include  # noqa: PLC0415
    return _walk_include()


def main() -> int:
    files = _collect()
    if not files:
        print("[FAIL] 白名单清单为空")
        return 1
    total = sum(f.stat().st_size for f in files)
    print(f"清单：{len(files)} 文件 {total / 1e9:.2f} GB")
    listfile = ROOT / "dist" / "_release_list.txt"
    listfile.write_text(
        "\n".join(f.relative_to(ROOT).as_posix() for f in files),
        encoding="utf-8")
    volumes = 1 + total // VOLUME_BYTES
    print(f"分卷：{volumes} 卷 × {VOLUME_BYTES / 1e9:.0f} GB")
    cmd = [
        str(SEVEN_ZIP), "a", "-t7z",
        f"-v{VOLUME_BYTES}b",     # 按字节切卷（2GB 整）
        "-mx0",                    # store：GGUF 已压缩，零收益
        "-y",
        str(OUT_BASE),
        f"@{listfile}",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True,
                          encoding="utf-8", errors="replace")
    tail = (proc.stdout or "").strip().splitlines()
    print("\n".join(tail[-6:]))
    if proc.returncode != 0:
        print(f"[FAIL] 7z 退出码 {proc.returncode}")
        return proc.returncode
    parts = sorted((ROOT / "dist").glob("UL10nForge-0.30.0-beta.7z.*"))
    print("\n[ok] 分卷产物：")
    for p in parts:
        print(f"  {p.name}  {p.stat().st_size / 1e9:.2f} GB")
    # 完整性验证（整体测试覆盖全部分卷）
    test = subprocess.run(
        [str(SEVEN_ZIP), "t", str(OUT_BASE) + ".001"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace")
    if test.returncode != 0 or "Everything is Ok" not in (test.stdout or ""):
        print(f"[FAIL] 分卷完整性验证失败：{(test.stdout or '')[-300:]}")
        return 1
    print("[ok] 分卷完整性验证通过（Everything is Ok）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
