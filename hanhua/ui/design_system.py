"""工作台视觉 token v2（任务二：按 UI-UX 重构规范执行）。

规范要点（docs/汉化助手 UI-UX 与产品体验重构设计规范.md）：
- 背景 #080D18（暗色中性底，非纯黑非纯蓝），Surface 三级（#0D1424/
  #111A2C/#16233A），层级优先「背景差 > 阴影 > 微弱边框」。
- 品牌色青绿 #48E6C1；AI 语义色紫（#A78BFA/#7C5CFC）——见紫色即 AI。
- 状态四色：绿成功 #45D483 / 琥珀警告 #F5B84B / 红错误 #F06A78 /
  蓝信息 #5CA8FF；黄（#F5B84B 系）待人工。
- 圆角五级：sm 6 / md 8 / lg 12 / panel 14 / dialog 16。
- 页面禁止散落语义颜色与交互尺寸（全部经 token 引用）。
- 可达性硬约束：控件最小可点击高度 44px（护栏测试断言，不可降）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesignTokens:
    # ── 背景层级（§5.2：App Background / Surface 1/2/3） ──
    background: str = "#080D18"        # App Background
    panel: str = "#0D1424"             # Surface 1（页面底板）
    surface: str = "#111A2C"           # Surface 2（卡片/控件底）
    surface_hover: str = "#16233A"     # Surface 3（hover）
    surface_raised: str = "#1A2942"    # 悬浮层（下拉/工具条/Toast）
    border: str = "#223049"            # 低透明度蓝灰（微弱边框）
    border_strong: str = "#3D4F70"     # 输入框/可编辑区/选中边框
    sidebar_bg: str = "#0A111F"        # 侧边栏基底
    glass_edge: str = "#2C3B57"        # 侧边栏高亮边
    logger_bg: str = "#050A12"         # 日志/表格深底

    # ── 品牌（§6.1：青绿主色，仅主按钮/选中/进度/CTA） ──
    primary: str = "#48E6C1"
    primary_hover: str = "#6EF0D3"
    primary_pressed: str = "#2BCBA8"
    primary_muted: str = "#12383D"     # 品牌色低饱和底（选中项/徽章）
    gradient_start: str = "#48E6C1"    # 仅品牌轨道/进度完成段
    gradient_end: str = "#4FB0FF"

    # ── AI 语义色（§6.2：紫色=AI，审核/推荐/分析/路由） ──
    ai_primary: str = "#A78BFA"
    ai_secondary: str = "#7C5CFC"
    ai_muted: str = "#26204A"          # AI 面板/徽章低饱和底
    accent2: str = "#A78BFA"           # 兼容旧引用：品牌次色 = AI 紫

    # ── 状态（§6.3：颜色只表达状态，不装饰） ──
    success: str = "#45D483"
    warning: str = "#F5B84B"           # 琥珀：待处理/需确认
    error: str = "#F06A78"             # 珊瑚红：仅失败
    info: str = "#5CA8FF"
    status_idle: str = "#5D6C85"
    status_locked: str = "#A78BFA"     # 锁定：紫灰

    # ── 文字 ──
    text: str = "#F2F6FC"
    text_secondary: str = "#A8B6CC"
    text_disabled: str = "#64748E"

    # ── 阴影/遮罩 ──
    overlay_scrim: str = "rgba(4,8,16,0.78)"
    shadow_key: str = "0,10,28,0,3,9,20,90"  # 仅主按钮/Toast/弹窗/当前任务节点

    # ── 圆角（§8：Button 8 / Input 8 / Badge 6 / Card 12 / 工作区 14 / Dialog 16）──
    radius: int = 6                    # sm（徽章/小件）
    radius_md: int = 8                 # md（按钮/输入框/数据舱）
    radius_card: int = 12              # lg（卡片/表格）
    radius_panel: int = 14             # 大型工作区
    radius_dialog: int = 16            # Dialog/命令面板

    # ── 间距（§7） ──
    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_6: int = 24
    space_8: int = 32

    # ── 可达性硬约束（护栏测试断言：控件最小可点击高度，不可降） ──
    control_height: int = 44
    primary_height: int = 48
    focus_width: int = 2


TOKENS = DesignTokens()
