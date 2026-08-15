"""语料驱动 sink 挖掘：从全部游戏的 IL 数据流挖「以字符串字面量调用
的 (类型, 方法)」高频清单 → 证明链 sink 种子（替代手工加 seed）。

方法：对每个 Mono 游戏的程序集跑轻量栈模拟——call/callvirt 时栈顶
N 元素含字符串字面量来源（src token），记录该 MemberRef 身份。
聚合 (type, method) × 游戏数 × 调用数，排名输出。

用法：runtime/python/python.exe scripts/_sink_mining.py <语料目录> [--top N]
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dnfile

from hanhua.core.unity.mono_dll import (_decode_il, _member_identity_map,
                                        _method_il, find_dll_files)


def _mine_game(game_dir: Path, sink_counts: dict,
               sink_games: dict) -> None:
    try:
        dlls = find_dll_files(game_dir)
    except Exception:  # noqa: BLE001
        return
    game_hits: set = set()
    for dll in dlls:
        try:
            pe = dnfile.dnPE(str(dll))
        except Exception:  # noqa: BLE001
            continue
        members = _member_identity_map(pe)
        try:
            method_rows = pe.net.mdtables.MethodDef.rows
        except AttributeError:
            continue
        for row in method_rows:
            rva = int(getattr(row, "Rva", 0) or 0)
            if not rva:
                continue
            code = _method_il(pe, rva)
            if code is None:
                continue
            instructions = _decode_il(code)
            if instructions is None:
                continue
            stack: list[object] = []
            for opcode, operand in instructions:
                if opcode == 0x72:  # ldstr
                    stack.append(("src", operand & 0x00FFFFFF))
                elif opcode in (0x28, 0x6F):  # call / callvirt
                    identity = members.get(operand)
                    if identity is not None:
                        # 调用时栈上是否有字符串字面量来源（含拼接片段）
                        has_src = any(
                            isinstance(el, tuple) and el[0] == "src"
                            for el in stack[-4:])
                        if has_src:
                            sink_counts[identity] += 1
                            game_hits.add(identity)
                    stack.clear()
                elif opcode in (0x25,):  # dup
                    if stack:
                        stack.append(stack[-1])
                elif opcode in (0x0A, 0x0B, 0x0C, 0x0D, 0x10, 0x13,
                                0x26, 0x30):
                    if stack:
                        stack.pop()
                elif opcode in (0x0E, 0x0F, 0x11, 0x12, 0x02, 0x03,
                                0x04, 0x05, 0x06, 0x07, 0x08, 0x09,
                                *range(0x14, 0x20), 0x20, 0x21, 0x22,
                                0x23, 0x7B, 0x7C, 0x7E, 0x74, 0x75,
                                0x8C, 0x79, 0x8E, 0xA2):
                    # ldarg/ldloc/ldc/ldfld/castclass 等 → 普通值
                    stack.append("other")
                else:
                    # 未建模指令保守清空（与证明器同语义）
                    stack.clear()
    for identity in game_hits:
        sink_games[identity] = sink_games.get(identity, set()) | {game_dir.name}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top_n = 40
    if "--top" in sys.argv:
        top_n = int(sys.argv[sys.argv.index("--top") + 1])
    root = Path(args[0])
    games = sorted(p for p in root.iterdir() if p.is_dir()
                   and not p.name.startswith(("_", ".")))
    sink_counts: dict = defaultdict(int)
    sink_games: dict = {}
    for i, game in enumerate(games):
        _mine_game(game, sink_counts, sink_games)
        print(f"\r{i + 1}/{len(games)} {game.name[:40]:<40}", end="",
              flush=True)
    print()
    ranked = sorted(
        sink_counts.items(),
        key=lambda kv: (-len(sink_games.get(kv[0], set())), -kv[1]))
    print(f"\n字符串字面量消费 API 排名（top {top_n}）：")
    for identity, count in ranked[:top_n]:
        games_hit = len(sink_games.get(identity, set()))
        print(f"  {identity[0]}.{identity[1]}  "
              f"调用 {count:>5}  游戏 {games_hit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
