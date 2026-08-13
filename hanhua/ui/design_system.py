"""Aurora Forge UL10nForge设计令牌（2026-08-13 UI 重设计）。

规格（docs/superpowers/specs/2026-08-13-aurora-forge-ui-redesign.md）：
- 石墨黑中性底色（canvas #090B12）承载高密度信息；薄荷青、天蓝、
  紫罗兰、琥珀、珊瑚红仅在有语义的位置出现。
- 色彩 Token：canvas / surface / surfaceRaised / textPrimary /
  textSecondary / mint / sky / violet / amber / coral / success。
- 大面积区域坚持中性色。彩色只用于阶段标识、数值、按钮、状态边和
  局部光晕；所有彩色状态同时配有文字或图标。
- 4px 基础网格，主要间距 8/12/16/24/32；按钮/输入 10px 圆角、
  卡片 14px、浮层 18px。
- 动效时长：页面进入 180ms、状态轨呼吸 1.6s、导航指示器 180-220ms。
- 可达性硬约束：控件最小可点击高度 44px（护栏测试断言，不可降）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DesignTokens:
    # ── Aurora Forge 背景层级（§4.1） ──
    canvas: str = "#090B12"            # 应用背景
    surface: str = "#10141F"           # 主面板
    surface_raised: str = "#171C2A"    # 浮层与强调卡
    surface_hover: str = "#1B2133"     # hover 抬升
    border: str = "#232B3D"            # 低对比分隔（默认卡片不描边）
    border_strong: str = "#3A4560"     # 输入框/可编辑区/选中边框
    # 旧字段别名（结构兼容，值已对齐新色板）
    background: str = "#090B12"        # == canvas
    panel: str = "#10141F"             # == surface
    sidebar_bg: str = "#0C1019"        # 侧边栏基底（比 canvas 略亮）
    glass_edge: str = "#232B3D"        # 侧边栏分隔边
    logger_bg: str = "#0B0E16"         # 日志/表格深底

    # ── 语义色（§4.1：彩色只出现在有语义的位置） ──
    accent: str = "#58E6C2"            # 薄荷青：当前主流程与主操作
    info: str = "#63B3FF"              # 天蓝：信息、检测与扫描
    ai: str = "#A78BFA"                # 紫罗兰：AI 判断与建议
    warning: str = "#F5B84B"           # 琥珀：待确认与警告
    error: str = "#FF7285"             # 珊瑚红：错误与高风险
    success: str = "#55D68B"           # 已通过

    # 旧字段别名（theme.py / widgets.py 既有引用，值对齐新色板）
    primary: str = "#58E6C2"           # == accent
    primary_hover: str = "#7BF0D4"
    primary_pressed: str = "#35C9A6"
    primary_muted: str = "#12372E"     # 品牌色低饱和底
    gradient_start: str = "#58E6C2"
    gradient_end: str = "#63B3FF"      # 薄荷青 → 天蓝
    ai_primary: str = "#A78BFA"        # == ai
    ai_secondary: str = "#8B6FF0"
    ai_muted: str = "#221D38"          # AI 面板/徽章低饱和底
    accent2: str = "#A78BFA"           # 兼容旧引用：品牌次色 = AI 紫
    status_idle: str = "#5E6B82"
    status_locked: str = "#A78BFA"

    # ── 文字（§4.1） ──
    text: str = "#F4F7FB"              # 主文本
    text_secondary: str = "#A7B0C0"    # 辅助文本
    text_disabled: str = "#66718A"

    # ── 阴影/遮罩 ──
    overlay_scrim: str = "rgba(3,6,12,0.78)"
    shadow_key: str = "0,10,28,0,3,9,20,90"  # 仅主按钮/Toast/弹窗/当前任务节点

    # ── 圆角（§4.2：按钮/输入 10、卡片 14、浮层 18） ──
    radius: int = 6                    # sm（徽章/小件）
    radius_md: int = 10                # 按钮/输入框/数据舱
    radius_card: int = 14              # 卡片
    radius_panel: int = 14             # 大型工作区
    radius_dialog: int = 18            # 浮层/命令面板

    # ── 间距（§4.2：4px 基础网格） ──
    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_6: int = 24
    space_8: int = 32

    # ── 动效时长（§7） ──
    page_enter_ms: int = 180           # 页面进入：淡入 + 12px 上移
    pulse_ms: int = 1600               # 状态轨当前节点呼吸周期
    nav_indicator_ms: int = 200        # 导航指示器滑动

    # ── 可达性硬约束（护栏测试断言：控件最小可点击高度，不可降） ──
    control_height: int = 44
    primary_height: int = 48
    focus_width: int = 2


TOKENS = DesignTokens()


def motion_enabled() -> bool:
    """动画开关（§10 减少动效）：HANHUA_REDUCED_MOTION 取 1/true/yes
    时关闭循环脉冲与位移动画，仅保留瞬时状态变化。"""
    return os.environ.get("HANHUA_REDUCED_MOTION", "0").strip().lower() \
        not in {"1", "true", "yes"}
