# -*- coding: utf-8 -*-
"""位图字体 provider（Phase 5，计划 §Phase 5）。

把当前已能发现但无法闭环的 NGUI/BMFont 第三方位图字体变成显式 provider：
发现（registry）→ 审计（缺字清单）→ 生成注入（.fnt + atlas PNG）→
重开验证（validate_fnt）→ 覆盖反哺（ngui_bitmap 消费者 → COVERED）。

没有 provider 的位图栈保持 CANDIDATE_ONLY（BITMAP_FONT_INJECTION_REQUIRED）
并在报告中给出明确资产、原因与手工处置建议。
"""
from hanhua.core.font.providers.bmfont import (
    BitmapAudit, audit_bitmap_font, inject_bitmap_font,
)
from hanhua.core.font.providers.registry import (
    BitmapProvider, BitmapInjectionResult, resolve_bitmap_providers,
)

__all__ = [
    "BitmapAudit", "BitmapInjectionResult", "BitmapProvider",
    "audit_bitmap_font", "inject_bitmap_font", "resolve_bitmap_providers",
]
