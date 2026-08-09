"""工作台视觉 token；页面禁止散落语义颜色与交互尺寸。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesignTokens:
    # 夜航工作台：深海蓝底 + 提亮靛蓝面板，薄荷青主色。
    # 紫色仅作少量辅助，不使用青紫渐变作为默认装饰。
    background: str = "#0C1424"
    panel: str = "#14213A"
    surface: str = "#1B2C4A"
    surface_hover: str = "#24395E"
    border: str = "#30496E"
    border_strong: str = "#4D6F9F"
    primary: str = "#58F0C6"          # 薄荷青（主色）
    primary_hover: str = "#7AF7D5"
    primary_pressed: str = "#35CAA6"
    primary_muted: str = "#173E43"
    accent2: str = "#8B7CFF"          # 品牌次色（紫，面积 ≤8%）
    gradient_start: str = "#58F0C6"   # 仅品牌轨道/进度完成段使用
    gradient_end: str = "#65A8FF"
    sidebar_bg: str = "#101B30"       # 侧边栏基底
    glass_edge: str = "#38557E"       # 侧边栏高亮边
    text: str = "#F4F8FF"
    text_secondary: str = "#B4C5DD"
    text_disabled: str = "#6F829E"
    success: str = "#58F0C6"
    warning: str = "#FFD166"          # 柠檬黄：仅待处理/跳过/需确认
    error: str = "#FF6F7D"            # 珊瑚红：仅失败
    info: str = "#65A8FF"
    status_idle: str = "#6F829E"
    status_locked: str = "#8B7CFF"
    surface_raised: str = "#213656"   # 下拉菜单/悬浮工具条/选中数据舱
    logger_bg: str = "#09111F"
    overlay_scrim: str = "rgba(5,10,20,0.76)"
    shadow_key: str = "0,10,28,0,3,9,20,90"  # 仅主按钮/Toast/弹窗/当前任务节点
    radius: int = 7
    radius_card: int = 10
    # 可达性硬约束：控件最小可点击高度 44px（既有护栏测试断言）
    control_height: int = 44
    primary_height: int = 48
    focus_width: int = 2
    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_6: int = 24
    space_8: int = 32


TOKENS = DesignTokens()
