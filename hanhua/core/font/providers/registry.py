# -*- coding: utf-8 -*-
"""位图字体 provider 发现（Phase 5，计划 §Phase 5 顺序 1/4）。

从指纹证据 + 原游戏文件树定位可注入的 BMFont 资产：
- 指纹 `bitmap_font` evidence（存在 .fnt）→ 扫描全部 .fnt 描述器；
- NGUI 指纹（DLL 含 ngui）→ kind=ngui_bmfont（NGUI UIFont 使用 BMFont
  文本描述器 + 外部 atlas 的标准布局，注入路径与 BMFont 一致）；
- 无 provider 时返回空——消费者保持 CANDIDATE_ONLY 且报告给出明确资产/
  原因/手工处置建议（计划完成标准：不支持的自定义栈不再静默停留）。

注入后重开验证复用 bmfont.validate_fnt（严格：common/page/char 声明、
chars count、atlas PNG 尺寸/CRC/像素长度、需求码点覆盖）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hanhua.core.tooling.fingerprint import GameFingerprint


@dataclass(frozen=True)
class BitmapProvider:
    """一个可注入的位图字体资产（原游戏内 .fnt 描述器）。"""

    provider_id: str            # "bmfont" / "ngui_bmfont"
    kind: str                   # "bmfont" / "ngui"
    fnt: Path                   # 原游戏 .fnt 绝对路径
    reason: str = ""


@dataclass
class BitmapInjectionResult:
    """位图注入闭环结果（pipeline.apply_bitmap 返回值）。"""

    providers: list[BitmapProvider] = field(default_factory=list)
    injected: int = 0           # 成功生成并替换的 .fnt 数量
    audited: int = 0            # 审计过的 .fnt 数量
    pending: int = 0            # 缺字且未能注入的 provider 数
    warnings: list[str] = field(default_factory=list)

    def blocks_publish(self) -> bool:
        """仍存在未注入 provider → 保持 CANDIDATE_ONLY（发布门决策）。
        审计已覆盖（无需注入）不算 pending——与「已注入」同样证明覆盖。"""
        return self.pending > 0


def resolve_bitmap_providers(
        game_dir: Path, fingerprint: GameFingerprint,
        *, exclude_roots: tuple[Path, ...] = ()) -> tuple[BitmapProvider, ...]:
    """发现原游戏内全部可注入的 BMFont 资产。

    exclude_roots: 跳过目录（如历史汉化输出）——防止把上次注入的
    .fnt 当作原游戏资产反复注入。
    """
    if "bitmap_font" not in fingerprint.evidence:
        return ()
    kind = "ngui" if "ngui" in fingerprint.evidence else "bmfont"
    provider_id = "ngui_bmfont" if kind == "ngui" else "bmfont"
    excluded = tuple(root.resolve() for root in exclude_roots)
    root = game_dir.resolve()
    providers: list[BitmapProvider] = []
    seen: set[Path] = set()
    for fnt in sorted(root.rglob("*.fnt")):
        resolved = fnt.resolve()
        if resolved in seen:
            continue
        if any(resolved == exc or exc in resolved.parents
               for exc in excluded):
            continue
        seen.add(resolved)
        relative = resolved.relative_to(root)
        reason = (f"NGUI UIFont 位图字体资产 {relative}"
                  if kind == "ngui"
                  else f"BMFont 位图字体资产 {relative}")
        providers.append(BitmapProvider(provider_id, kind, resolved, reason))
    return tuple(providers)
