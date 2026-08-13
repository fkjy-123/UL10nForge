# -*- coding: utf-8 -*-
"""FontVerifier：逐 Unicode Code Point 全链验证器（#12 minato 核心交付）。

字体问题文档.txt 原则落地：**不猜测字体是否支持字符**——对需求集
每个码点沿 Font → Character → Glyph → Atlas → Fallback 链实际验证，
任意断点按验收计划第十八阶段 Case A-H 分类（可区分根因，不再统一
报「字体失败」）：

  Case A  字体本身没有 Glyph（TTF/OTF cmap 缺码点）      → MISSING_GLYPH
  Case B  Font Asset 字符表缺（cmap 有而 TMP 字符表无）  → CHARACTER_MISSING
  Case C  TMP 未引用正确 Font Asset（消费端配置）        → CONSUMER_MISCONFIG
  Case D  Fallback 未配置（主字体缺且无兜底链）          → FALLBACK_UNCONFIGURED
  Case E  Fallback 配置了但字符不存在                    → FALLBACK_MISSING_GLYPH
  Case F  Dynamic Font Asset 运行时生成（静态不可断言）  → DYNAMIC_UNVERIFIED
  Case G  字形→图集引用链断 / 图集无法容纳字形          → ATLAS_MISSING
  Case H  字体文件本身无效（导入失败信号：magic 不符/解析失败）→ FONT_INVALID
  DATA_CORRUPTION  上游数据已损坏（□ U+25A1 等方框码点已写入）——
                归因数据层，不是字体缺字（diagnostics 同源语义）

验证器是纯函数：只接受结构化输入（TTF 字节 / TMP 资产信息 / Fallback
链 / 消费端配置），不做 Unity 资产解析——资产解析在 extractor/inventory
层（FontObjectEvidence 等），本模块专注确定性验证与根因分类。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import Enum

from hanhua.core.font.glyph_set import RequiredGlyphSet
from hanhua.core.font.diagnostics import TOFU_CODEPOINTS
from hanhua.core.font.ttf_charset import ttf_charset

#: sfnt 合法 magic（ttf/otf/ttc）。ttcf 是多字体集合容器，单文件验证
#: 按无效处理（Case H）——需要先拆包，不在本验证器职责内。
_SFNT_MAGICS = {b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"}


def _has_sfnt_directory(data: bytes) -> bool:
    """文件是否带合法 sfnt 表目录。

    区分两种「ttf_charset 返回空集」的情形（ttf_charset 对畸形输入
    保守返回空集，不抛异常）：
      - 无合法表目录 → 文件损坏（Case H，FONT_INVALID）
      - 有合法表目录 → 字体本身有效、只是没收录目标码点
        （Case A 事实，可走 fallback / 静态替换）
    """
    if len(data) < 12 or data[:4] not in _SFNT_MAGICS:
        return False
    num_tables = struct.unpack_from(">H", data, 4)[0]
    if not 1 <= num_tables <= 64:
        return False
    return 12 + num_tables * 16 <= len(data)


class ChainCase(str, Enum):
    """全链验证断点分类（验收计划第十八阶段 Case A-H + 数据损坏）。"""

    OK = "OK"
    FONT_INVALID = "FONT_INVALID"              # Case H
    MISSING_GLYPH = "MISSING_GLYPH"            # Case A
    CHARACTER_MISSING = "CHARACTER_MISSING"    # Case B（字符表缺）
    GLYPH_MISSING = "GLYPH_MISSING"            # Case B 深化（字形表缺）
    CONSUMER_MISCONFIG = "CONSUMER_MISCONFIG"  # Case C
    FALLBACK_UNCONFIGURED = "FALLBACK_UNCONFIGURED"      # Case D
    FALLBACK_MISSING_GLYPH = "FALLBACK_MISSING_GLYPH"    # Case E
    DYNAMIC_UNVERIFIED = "DYNAMIC_UNVERIFIED"  # Case F（运行时 attest）
    ATLAS_MISSING = "ATLAS_MISSING"            # Case G
    DATA_CORRUPTION = "DATA_CORRUPTION"        # 上游数据损坏


#: 模块级别名（包导出与测试断言用）
OK = ChainCase.OK
FONT_INVALID = ChainCase.FONT_INVALID
MISSING_GLYPH = ChainCase.MISSING_GLYPH
CHARACTER_MISSING = ChainCase.CHARACTER_MISSING
GLYPH_MISSING = ChainCase.GLYPH_MISSING
CONSUMER_MISCONFIG = ChainCase.CONSUMER_MISCONFIG
FALLBACK_UNCONFIGURED = ChainCase.FALLBACK_UNCONFIGURED
FALLBACK_MISSING_GLYPH = ChainCase.FALLBACK_MISSING_GLYPH
DYNAMIC_UNVERIFIED = ChainCase.DYNAMIC_UNVERIFIED
ATLAS_MISSING = ChainCase.ATLAS_MISSING
DATA_CORRUPTION = ChainCase.DATA_CORRUPTION

#: 缺字类终态（会显示 tofu 或需要人工处置的断点）
DEFECT_CASES = frozenset({
    FONT_INVALID, MISSING_GLYPH, CHARACTER_MISSING, GLYPH_MISSING,
    CONSUMER_MISCONFIG, FALLBACK_UNCONFIGURED, FALLBACK_MISSING_GLYPH,
    DYNAMIC_UNVERIFIED, ATLAS_MISSING,
})


@dataclass(frozen=True)
class FontSource:
    """一个字体源（TTF/OTF 字节 + 名称）。bytes 为空 = 无效/缺失。"""

    name: str
    data: bytes = b""

    def codepoints(self) -> frozenset[int] | None:
        """cmap 码点集；字体无效（无数据/解析失败/无 sfnt 表目录）→ None。

        ttf_charset 对畸形输入保守返回空集——空集本身不代表「字体有效
        但不含目标码点」：损坏/截断/混淆的字体文件（通常远大于任何
        阈值）必须判 Case H，不能被当作「有效但空」而走 Case A 分支。
        sfnt 表目录探测是唯一可靠区分（不猜测文件大小）。
        """
        if not self.data:
            return None
        try:
            cps = ttf_charset(self.data)
        except Exception:  # noqa: BLE001 解析失败 = 文件无效（Case H）
            return None
        if not cps and not _has_sfnt_directory(self.data):
            return None
        return cps


@dataclass(frozen=True)
class TmpAssetInfo:
    """TMP_FontAsset 资产信息（由 inventory/extractor 层解析提供）。"""

    name: str
    character_table: frozenset[int] = frozenset()   # m_CharacterTable 码点
    glyph_table: frozenset[int] = frozenset()       # m_GlyphTable 对应码点
    atlas_valid: bool = True                        # 图集引用/尺寸可解析
    dynamic: bool = False                           # 动态字体（运行时生成）


@dataclass(frozen=True)
class CodepointVerdict:
    """单码点全链验证结果：断点位置 + Case 分类 + 来源回溯。"""

    scalar: int
    case: ChainCase
    chain: tuple[str, ...] = ()     # 验证链上的证据（Font/TMP/Atlas/Fallback）
    sources: tuple[str, ...] = ()   # 需求来源 locator（file_id:key_path）

    @property
    def char(self) -> str:
        return chr(self.scalar)


@dataclass
class VerificationReport:
    """全链验证报告：逐码点 verdicts + 分类统计 + 循环检测。"""

    required: RequiredGlyphSet
    verdicts: list[CodepointVerdict]
    fallback_cycle: tuple[str, ...] = ()
    consumer_kind: str = ""

    def by_case(self) -> dict[str, list[CodepointVerdict]]:
        out: dict[str, list[CodepointVerdict]] = {}
        for v in self.verdicts:
            out.setdefault(v.case, []).append(v)
        return out

    @property
    def ok_count(self) -> int:
        return sum(1 for v in self.verdicts if v.case == OK)

    @property
    def defect_count(self) -> int:
        return sum(1 for v in self.verdicts if v.case in DEFECT_CASES)

    @property
    def font_glyph_gaps(self) -> int:
        """Case A 聚合：主字体缺字形的码点数（不论 fallback 是否兜底）。

        事实留档：case 报可行动的 fallback 层断点，但「字体本身缺字形」
        的事实记录在 chain[0]（"Font[x]缺字形"），聚合供验收报告使用。
        """
        return sum(1 for v in self.verdicts
                   if v.chain and "缺字形" in v.chain[0])

    def summary_text(self) -> str:
        """人类可读摘要（验收报告 / 诊断输出用）。"""
        by = self.by_case()
        gaps = self.font_glyph_gaps
        lines = [f"需求码点 {len(self.required.scalars)} · "
                 f"覆盖 {self.ok_count} · 断点 {self.defect_count}"
                 + (f" · 主字体缺字形 {gaps}（Case A）" if gaps else "")]
        for case in sorted(by, key=lambda c: -len(by[c])):
            vs = by[case]
            if case == OK:
                continue
            sample = " ".join(v.char for v in vs[:12])
            lines.append(
                f"[{case}] ×{len(vs)} · 样本「{sample}」"
                + (f" · 例：{vs[0].sources[0]}" if vs[0].sources else ""))
        if self.fallback_cycle:
            lines.append("Fallback 循环引用: "
                         + " → ".join(self.fallback_cycle))
        return "\n".join(lines)


def detect_fallback_cycle(fallbacks: list[FontSource]) -> tuple[str, ...]:
    """Fallback 链循环检测（验收计划 16.3：A→B→C→A）。

    按名称判重：同一名称出现两次即循环（Unity 按 asset 名引用）。
    返回循环路径（空 = 无循环）。
    """
    seen: dict[str, int] = {}
    for i, fb in enumerate(fallbacks):
        if fb.name in seen:
            return tuple(fb.name for fb in fallbacks[seen[fb.name]:i + 1])
        seen[fb.name] = i
    return ()


def verify_chain(required: RequiredGlyphSet, *,
                 font: FontSource,
                 tmp: TmpAssetInfo | None = None,
                 fallbacks: tuple[FontSource, ...] = (),
                 consumer_ok: bool = True,
                 consumer_kind: str = "") -> VerificationReport:
    """逐码点全链验证（#12 核心入口）。

    required:      需求集（真实译文码点 + 来源回溯）
    font:          主字体源（Case A/H 判定）
    tmp:           TMP_FontAsset 资产信息（None = 无 TMP 层，仅验证 Font）
    fallbacks:     Fallback 字体链（Case D/E）
    consumer_ok:   TMP 消费者是否正确引用本资产（Case C）
    consumer_kind: 消费者类型标签（报告用，如 "TMP_Text"）
    """
    font_cps = font.codepoints()
    verdicts: list[CodepointVerdict] = []
    for scalar in sorted(required.scalars):
        sources = tuple(required.sources_of(scalar))
        if scalar in TOFU_CODEPOINTS:
            # 上游数据已损坏：方框码点被写入——归因数据层，不是字体
            verdicts.append(CodepointVerdict(
                scalar, DATA_CORRUPTION, ("data",), sources))
            continue
        if font_cps is None:
            # Case H：字体文件本身无效（无数据/解析失败/magic 不符）
            verdicts.append(CodepointVerdict(
                scalar, FONT_INVALID, (f"Font[{font.name}]",), sources))
            continue
        chain = [f"Font[{font.name}]"]
        if scalar not in font_cps:
            # Case A 事实：主字体缺字形（chain[0] 留档聚合）——
            # case 报可行动的 fallback 层断点（Case D 未配置 / Case E
            # 配置了但缺 / 兜底命中则 OK）
            chain[0] = f"Font[{font.name}]缺字形"
            ok = False
            for fb in fallbacks:
                fb_cps = fb.codepoints()
                if fb_cps is None:
                    chain.append(f"Fallback[{fb.name}]无效")
                    continue
                chain.append(f"Fallback[{fb.name}]")
                if scalar in fb_cps:
                    ok = True
                    break
            if not fallbacks:
                verdicts.append(CodepointVerdict(
                    scalar, FALLBACK_UNCONFIGURED, tuple(chain), sources))
            elif ok:
                verdicts.append(CodepointVerdict(
                    scalar, OK, tuple(chain), sources))
            else:
                verdicts.append(CodepointVerdict(
                    scalar, FALLBACK_MISSING_GLYPH, tuple(chain), sources))
            continue
        if not consumer_ok:
            # Case C：TMP 消费者未引用本字体资产
            verdicts.append(CodepointVerdict(
                scalar, CONSUMER_MISCONFIG, tuple(chain) + ("consumer",),
                sources))
            continue
        if tmp is None:
            # 无 TMP 层（纯 Font 渲染）——Font 层已验证通过
            verdicts.append(CodepointVerdict(scalar, OK, tuple(chain), sources))
            continue
        if tmp.dynamic:
            # Case F：动态字体运行时按 TTF 生成字形——静态不可断言
            # 覆盖，诚实标注需运行时 attestation（不伪装 PASS）
            verdicts.append(CodepointVerdict(
                scalar, DYNAMIC_UNVERIFIED,
                tuple(chain) + (f"TMP[{tmp.name}]dynamic",), sources))
            continue
        chain.append(f"TMP[{tmp.name}]")
        if scalar not in tmp.character_table:
            # Case B：cmap 有而 Font Asset 字符表无——静态资产未收录
            verdicts.append(CodepointVerdict(
                scalar, CHARACTER_MISSING, tuple(chain) + ("character",),
                sources))
            continue
        if scalar not in tmp.glyph_table:
            # Case B 深化：字符表有而字形表无
            verdicts.append(CodepointVerdict(
                scalar, GLYPH_MISSING, tuple(chain) + ("glyph",), sources))
            continue
        if not tmp.atlas_valid:
            # Case G：字形→图集引用链断/图集无法容纳
            verdicts.append(CodepointVerdict(
                scalar, ATLAS_MISSING, tuple(chain) + ("atlas",), sources))
            continue
        verdicts.append(CodepointVerdict(
            scalar, OK, tuple(chain) + ("atlas",), sources))
    return VerificationReport(
        required, verdicts,
        fallback_cycle=detect_fallback_cycle(list(fallbacks)),
        consumer_kind=consumer_kind)
