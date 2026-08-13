# -*- coding: utf-8 -*-
"""BMFont 位图字体 provider：审计 + 生成注入（Phase 5，计划 §Phase 5 顺序 2）。

审计：对原游戏 .fnt 严格解析（bmfont.validate_fnt 契约链）→ 需求码点
缺失清单；缺失即需要注入（否则保持 CANDIDATE_ONLY，不假装覆盖）。

注入：用已验语料（bmfont.run_bmfont：质量门过滤 + 工具产物严格验证）生成
新 .fnt + atlas PNG，写到 staging 与原游戏相同相对路径（NGUI/BMFont 标准
布局：文本描述器 + 外部 atlas，资源加载按文件名寻址——替换文件即注入）。

非 BMP 码点：BMFont 文本描述器 char id 支持 32-bit（0x10FFFF），语料按
scalar 生成，验证层 validate_fnt 同样按 id 判定——不拆 surrogate。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hanhua.core.font.glyph_set import RequiredGlyphSet
from hanhua.core.font.providers.registry import BitmapProvider
from hanhua.core.tooling.bmfont import (BmFontArtifact,
                                        BmFontValidationError,
                                        run_bmfont, validate_fnt)
from hanhua.core.tooling.manifest import ToolSpec
from hanhua.core.tooling.runner import IsolatedToolRunner


@dataclass(frozen=True)
class BitmapAudit:
    """单个 .fnt 的注入审计结果（缺字清单——有缺字才触发注入）。"""

    fnt: Path
    valid: bool                  # .fnt 描述器契约链是否完整
    missing: frozenset[int]      # 需求集缺失码点（空 = 无需注入）
    detail: str = ""


def required_corpus(required: RequiredGlyphSet) -> str:
    """需求集 → 语料字符串（按 scalar 排序；非 BMP 单 scalar 不拆分）。"""
    return "".join(chr(s) for s in sorted(required.scalars))


def audit_bitmap_font(fnt: Path, required: RequiredGlyphSet) -> BitmapAudit:
    """审计原游戏 .fnt：契约链有效 + 需求码点覆盖。"""
    try:
        artifact = validate_fnt(fnt, required_corpus(required))
    except BmFontValidationError as exc:
        # 描述器无效/缺字：missing 无法从坏契约中分离 → 保守全缺
        detail = str(exc)
        if "缺少字符" in detail:
            codes = detail.split("缺少字符：", 1)[1].strip()
            missing = frozenset(
                int(part.strip().split(" ")[0].replace("U+", ""), 16)
                for part in codes.split(",") if part.strip())
            return BitmapAudit(fnt, True, missing, detail)
        return BitmapAudit(fnt, False, frozenset(required.scalars), detail)
    return BitmapAudit(fnt, True, frozenset(), "契约链完整，需求码点已覆盖")


def inject_bitmap_font(
        provider: BitmapProvider,
        staging_fnt: Path,
        required: RequiredGlyphSet,
        runner: IsolatedToolRunner,
        spec: ToolSpec,
        font_file: Path,
        *,
        width: int = 2048,
        height: int = 2048,
) -> BmFontArtifact:
    """生成中文字库 .fnt + atlas 注入 staging 对应相对路径。

    staging_fnt 必须与 provider.fnt 相对 game_dir 的相对路径一致——
    原样替换后游戏按文件名寻址加载。产物经 run_bmfont 严格验证
    （validate_fnt：尺寸/CRC/需求码点覆盖），失败抛 BmFontValidationError
    由调用方记 warning，消费者保持未覆盖。
    """
    result, artifact = run_bmfont(
        runner, spec, font_file, _entries_for(required),
        width=width, height=height)
    if not result.succeeded:
        raise BmFontValidationError(
            f"BMFont 工具失败：{result.status}"
            + (f"：{result.stderr}" if result.stderr else ""))
    staging_fnt.parent.mkdir(parents=True, exist_ok=True)
    for page in artifact.pages:
        target = staging_fnt.parent / page.name
        target.write_bytes(page.read_bytes())
    staging_fnt.write_text(artifact.descriptor.read_text(encoding="utf-8-sig"),
                           encoding="utf-8")
    return validate_fnt(staging_fnt, required_corpus(required),
                        expected_width=width, expected_height=height)


def _entries_for(required: RequiredGlyphSet):
    """需求集 → TextEntry 语料视图（build_corpus 的 TextEntry 契约）。

    直接构造最小 TextEntry：status=translated、translation=需求文本、
    quality_passed=True、role=display、confidence=high——build_corpus
    只对通过质量门的 display 条目取译文。
    """
    from hanhua.core.models import TextEntry
    text = required_corpus(required)
    return [TextEntry(
        "required-glyphs", "glyphset", text, translation=text,
        status="translated",
        meta={"quality_passed": True, "role": "display",
              "confidence": "high"})]
