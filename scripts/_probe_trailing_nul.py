"""临时探针:验证 IL2CPP 截短译文后记录长度不更新 → 运行时字符串尾部 NUL。"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hanhua.core.unity.il2cpp import parse_string_literals
from hanhua.core.unity.writer import _fit_bytes

GAMES = Path("D:/游戏")
for meta_path in GAMES.rglob("global-metadata.dat"):
    try:
        raw = meta_path.read_bytes()
    except OSError:
        continue
    literals = parse_string_literals(raw)
    if not literals:
        continue
    print(f"=== {meta_path.parent.parent.parent.name} {meta_path.parent.parent.name}: {len(literals)} literals ===")
    shown = 0
    for data_index, length, data_pos in literals:
        s = raw[data_pos:data_pos + length].decode("utf-8", "replace")
        if len(s) >= 4 and shown < 3:
            payload, truncated = _fit_bytes("你好世界", length, "utf-8")
            print(f"  orig={s[:26]!r} len={length} -> payload={payload!r} 截断={truncated}")
            shown += 1
