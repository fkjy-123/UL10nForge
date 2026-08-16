"""智能上下文计算（2026-08-16 用户指令）。

问题背景：drova 等大文本游戏固定 ctx（6144）配置不当——大批次放不下
降级逐条（慢），或 KV 冗余浪费显存。用户要求「根据原文字数 + 预估
译文字数计算安全合理的上下文数字」：

规则：
1. 原文字数 → token 估算（混合：ASCII 0.28/字符、CJK 1.1/字符、
   其他 0.5/字符——中文原文 token 密度高于英文）；
2. 预估译文 token = 原文 token × 1.5（中文译文可能比英文原文更长，
   保守系数）；
3. 单条需求 = 最长原文的预估译文 token + prompt/模板开销——
   **保证任何一条文本不会上下文不够**（切换批量条数不影响：按最长
   单条兜底，不依赖批量大小）；
4. 批量需求 = 批量条数 × 平均原文预估译文 token + 开销；
5. ctx = max(单条需求, 批量需求) × 安全余量——不冗余太多（只用
   实际文本统计，不用固定大值）；
6. 下限 2048（llama 最低可用）· 上限 16384（常规显存 KV 上限）。
"""
from __future__ import annotations

from collections.abc import Iterable

# 安全余量：模型输出波动/格式噪音（JSON 包装等）
_SAFETY = 1.35
# prompt/模板开销：system prompt + 条目模板 + 术语/知识注入余量
_PROMPT_OVERHEAD = 900
_MIN_CTX = 2048
_MAX_CTX = 16384
# 译文保守系数（中文译文 token 可能多于英文原文）
_TRANSLATION_FACTOR = 1.5


def estimate_tokens(text: str) -> int:
    """混合文本 token 估算：ASCII 约 0.28 token/字符（英文 3.5 字符/
    token），CJK 约 1.1 token/字符（中文字符信息密度高），其他脚本
    （西里尔/希腊/泰文等）0.5 token/字符。"""
    ascii_n = sum(1 for ch in text if ord(ch) < 0x80)
    cjk_n = sum(1 for ch in text
                if "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff")
    other = len(text) - ascii_n - cjk_n
    return max(1, int(ascii_n * 0.28 + cjk_n * 1.1 + other * 0.5))


def smart_context_size(
        texts: Iterable[str], *,
        batch_size: int = 8,
        max_tokens: int = 4096,
        safety: float = _SAFETY,
        prompt_overhead: int = _PROMPT_OVERHEAD,
        min_ctx: int = _MIN_CTX,
        max_ctx: int = _MAX_CTX) -> int:
    """按原文统计计算安全合理的上下文 token 数（保险版）。

    硬约束优先（不再用"译文 ×1.5"估算输出）：
    - 单条需求 = 最长原文 token + 输出上限 max_tokens + prompt 开销——
      任何单条（输入 + 输出上限）都不会超 ctx，切换批量条数不影响；
    - 批量需求 = 批量条数 × 平均原文 token + 输出上限 + 开销；
    - ctx = max(两者) × 安全余量，夹在 [2048, 16384]。
    超限兜底：llama 拒绝超 ctx 请求 → 批处理器降级逐条（慢但不坏）。
    """
    tokens = [estimate_tokens(t) for t in texts if t]
    if not tokens:
        return 8192
    max_tok = max(tokens)
    avg_tok = sum(tokens) / len(tokens)
    # 输出上限按文本规模缩放（短文本输出短——'Options'→'选项' 几个
    # token，不必预留 4096；长文本封顶 api.max_tokens）：不冗余太多
    out_ceiling = min(int(max_tokens),
                      max(256, int(max_tok * 2) + 100))
    single_need = max_tok + out_ceiling + prompt_overhead
    batch_need = int(avg_tok * max(1, int(batch_size)))         + out_ceiling + prompt_overhead
    ctx = int(max(single_need, batch_need) * safety)
    return max(min_ctx, min(max_ctx, ctx))
