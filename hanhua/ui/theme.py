"""夜航工作台深色设计系统：颜色 token + 全局 QSS。

设计约束（来自夜航工作台规范）：
- 面板提亮、深蓝底；薄荷青主色、柠檬黄仅提示、珊瑚红仅失败。
- 青紫渐变只允许出现在品牌轨道与进度完成段。
- 页面分区优先使用分隔线、留白与颜色面，不为每段内容套卡片。
- QSS 不包含 transition/animation/keyframes（Qt 不支持），动效全部在 Python。
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication
from hanhua.ui.design_system import TOKENS

# ── 设计 token ──────────────────────────────────────────────
BG = TOKENS.background
PANEL = TOKENS.panel
CARD = TOKENS.surface
CARD_HOVER = TOKENS.surface_hover
RAISED = TOKENS.surface_raised
BORDER = TOKENS.border
BORDER_STRONG = TOKENS.border_strong
ACCENT = TOKENS.primary
ACCENT_HOVER = TOKENS.primary_hover
ACCENT_PRESSED = TOKENS.primary_pressed
ACCENT_BG = TOKENS.primary_muted
ACCENT2 = TOKENS.accent2
GRAD_START = TOKENS.gradient_start
GRAD_END = TOKENS.gradient_end
SIDEBAR_BG = TOKENS.sidebar_bg
GLASS_EDGE = TOKENS.glass_edge
TEXT = TOKENS.text
TEXT_SECONDARY = TOKENS.text_secondary
TEXT_DISABLED = TOKENS.text_disabled
SUCCESS = TOKENS.success
WARNING = TOKENS.warning
ERROR = TOKENS.error
INFO = TOKENS.info
STATUS_IDLE = TOKENS.status_idle
STATUS_LOCKED = TOKENS.status_locked
LOGGER_BG = TOKENS.logger_bg
RADIUS = TOKENS.radius
RADIUS_CARD = TOKENS.radius_card
PRIMARY_TEXT = "#071713"  # 主按钮上的深色文字

_QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QWidget {{ background: transparent; }}
QWidget#root {{ background: {BG}; }}

/* ── 侧边栏（纯色 + 1px 高亮边，不套渐变） ────────────────── */
QFrame#sidebar {{
    background: {SIDEBAR_BG};
    border-right: 1px solid {GLASS_EDGE};
}}
QFrame#brandBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {GRAD_START}, stop:1 {GRAD_END});
    border: none;
    margin: 10px 30px 0 30px;
    border-radius: 2px;
}}
QLabel#appTitle {{
    font-size: 19px; font-weight: 700;
    color: {TEXT};
}}
QLabel#appSub {{ color: {TEXT_DISABLED}; font-size: 9pt; }}
QLabel#projectCardName {{ font-size: 10pt; font-weight: 600; }}
QLabel#projectCardPath {{
    color: {TEXT_DISABLED}; font-size: 8pt;
    white-space: pre-wrap;
}}
QListWidget#navList {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget#navList::item {{
    padding: 10px 14px;
    margin: 2px 10px;
    border-radius: 7px;
    color: {TEXT_SECONDARY};
    border-left: 3px solid transparent;
}}
QListWidget#navList::item:hover {{ background: {CARD}; color: {TEXT}; }}
QListWidget#navList::item:selected {{
    background: {ACCENT_BG};
    color: {ACCENT};
    font-weight: 600;
}}
QListWidget#navList::item:disabled {{ color: {TEXT_DISABLED}; }}
/* 导航指示条：选中项旁的 3px 主色条，切换时 180ms 滑动 */
QFrame#navIndicator {{
    background: {ACCENT};
    border-radius: 1px;
    border: none;
}}

/* ── 按钮（四类全状态） ───────────────────────────────────── */
/* 次按钮（默认） */
QPushButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px 16px;
    min-height: {TOKENS.control_height}px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {CARD_HOVER}; border-color: {BORDER_STRONG}; }}
QPushButton:pressed {{ background: #182A47; }}
QPushButton:disabled {{ color: {TEXT_DISABLED}; background: {PANEL}; border-color: {BORDER}; }}
QPushButton:focus {{ border: {TOKENS.focus_width}px solid {ACCENT}; }}

/* 主按钮：明亮薄荷青纯色 + 深色文字，不做渐变 */
QPushButton[primary="true"] {{
    background: {ACCENT};
    border: none;
    color: {PRIMARY_TEXT};
    font-weight: 700;
    min-height: {TOKENS.primary_height}px;
}}
QPushButton[primary="true"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[primary="true"]:pressed {{
    background: {ACCENT_PRESSED};
    margin-top: 1px; margin-bottom: -1px;
}}
QPushButton[primary="true"]:disabled {{ background: #294057; color: {TEXT_DISABLED}; }}

/* 危险按钮：透明底 + 珊瑚红 */
QPushButton[danger="true"] {{
    background: transparent;
    border: 1px solid {ERROR};
    color: {ERROR};
}}
QPushButton[danger="true"]:hover {{ background: rgba(255, 111, 125, 0.12); }}
QPushButton[danger="true"]:pressed {{ background: rgba(255, 111, 125, 0.20); }}
QPushButton[danger="true"]:disabled {{ color: {TEXT_DISABLED}; border-color: {BORDER}; }}

/* 幽灵按钮：仅 hover 反馈 */
QPushButton[ghost="true"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {TEXT_SECONDARY};
}}
QPushButton[ghost="true"]:hover {{ background: {CARD}; color: {TEXT}; }}

/* ── 输入控件 ───────────────────────────────────────────── */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 5px 10px;
    selection-background-color: {ACCENT};
    selection-color: {PRIMARY_TEXT};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ min-height: {TOKENS.control_height}px; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    background: {CARD_HOVER};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: {TOKENS.focus_width}px solid {ACCENT};
}}
QLineEdit:disabled, QComboBox:disabled {{ color: {TEXT_DISABLED}; }}
QComboBox::drop-down {{ border: none; width: 32px; }}
QComboBox QAbstractItemView {{
    background: {RAISED};
    border: 1px solid {BORDER};
    border-radius: 7px;
    outline: none;
    selection-background-color: {ACCENT_BG};
    selection-color: {TEXT};
}}
QComboBox QAbstractItemView::item {{ min-height: 30px; padding: 4px 10px; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: transparent;
    border: none;
    width: 18px;
}}

/* ── 表格（审校/术语表） ─────────────────────────────────── */
QTableView, QTableWidget {{
    background: {LOGGER_BG};
    alternate-background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
    gridline-color: transparent;
    selection-background-color: {ACCENT_BG};
    selection-color: {TEXT};
}}
QTableView::item:hover, QTableWidget::item:hover {{ background: {CARD_HOVER}; }}
QTableView:focus {{ border: {TOKENS.focus_width}px solid {ACCENT}; }}
QHeaderView::section {{
    background: {PANEL};
    color: {TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 7px 10px;
    font-size: 9pt;
}}
QTableCornerButton::section {{ background: {PANEL}; border: none; }}

/* ── 滚动条 ─────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {INFO}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 8px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG}; border-radius: 4px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {INFO}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── 标签页（去 pane 外框） ──────────────────────────────── */
QTabWidget::pane {{ border: none; background: transparent; top: 0; }}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_SECONDARY};
    padding: 9px 24px;
    border: none;
    font-size: 10pt;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

/* ── 进度条（完成段使用 primary→info 短渐变） ────────────── */
QProgressBar {{
    background: {CARD};
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {GRAD_START}, stop:1 {GRAD_END});
    border-radius: 4px;
}}

/* ── 任务状态轨道（贯穿四页的产品记忆点） ─────────────────── */
QFrame#brandRail {{
    background: {CARD};
    border: none;
    border-radius: 3px;
    min-height: 2px;
    max-height: 2px;
}}
QFrame#brandRail[progress="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {GRAD_START}, stop:1 {GRAD_END});
}}
QFrame#statusNode {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 7px;
}}
QFrame#statusNode[status="running"] {{
    border-color: {ACCENT};
}}
QFrame#statusNode[status="succeeded"] {{
    border-color: {SUCCESS};
}}
QFrame#statusNode[status="failed"] {{
    border-color: {ERROR};
}}
QFrame#statusNode[status="warning"] {{
    border-color: {WARNING};
}}
QLabel#statusNodeDot {{
    min-width: 8px; max-width: 8px;
    min-height: 8px; max-height: 8px;
    border-radius: 4px;
    background: {STATUS_IDLE};
}}
QLabel#statusNodeDot[status="running"] {{ background: {ACCENT}; }}
QLabel#statusNodeDot[status="succeeded"] {{ background: {SUCCESS}; }}
QLabel#statusNodeDot[status="failed"] {{ background: {ERROR}; }}
QLabel#statusNodeDot[status="warning"] {{ background: {WARNING}; }}
QLabel#statusNodeDot[status="locked"] {{ background: {STATUS_LOCKED}; }}
QLabel#statusNodeTitle {{ font-weight: 600; font-size: 9.5pt; }}
QLabel#statusNodeDetail {{ color: {TEXT_SECONDARY}; font-size: 8.5pt; }}
QLabel#statusNodeMetrics {{ color: {TEXT_DISABLED}; font-size: 8pt; }}

/* ── 数据舱（翻译页指标：panel 底 + 左侧 2px 语义色） ─────── */
QFrame#metricStrip {{
    background: {PANEL};
    border: none;
    border-left: 2px solid {BORDER_STRONG};
    border-radius: 0;
}}
QFrame#metricStrip[accent="success"] {{ border-left-color: {SUCCESS}; }}
QFrame#metricStrip[accent="warning"] {{ border-left-color: {WARNING}; }}
QFrame#metricStrip[accent="error"] {{ border-left-color: {ERROR}; }}
QFrame#metricStrip[accent="info"] {{ border-left-color: {INFO}; }}
QLabel#metricStripValue {{ font-size: 17px; font-weight: 700; }}
QLabel#metricStripLabel {{ color: {TEXT_SECONDARY}; font-size: 8.5pt; }}

/* ── 其它 ───────────────────────────────────────────────── */
QToolTip {{
    background: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
}}
QMenu {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 26px; border-radius: 6px; }}
QMenu::item:selected {{ background: {CARD_HOVER}; }}
QMenu::item:disabled {{ color: {TEXT_DISABLED}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
QCheckBox {{ spacing: 8px; color: {TEXT_SECONDARY}; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border-radius: 4px;
    border: 1px solid {BORDER_STRONG};
    background: {CARD};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox:disabled {{ color: {TEXT_DISABLED}; }}
QStatusBar {{
    background: {PANEL}; color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
}}
QStatusBar::item {{ border: none; }}
QFrame#card {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QFrame#card:hover {{ border-color: {BORDER_STRONG}; }}
QFrame#metricChip {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 7px;
}}
QLabel[class="metricLabel"] {{ color: {TEXT_SECONDARY}; font-size: 9pt; }}
QLabel[class="metricValue"] {{ color: {TEXT}; font-weight: 600; }}
QFrame#pipelineStep {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QFrame#pipelineStep[status="succeeded"] {{ border-color: {SUCCESS}; }}
QFrame#pipelineStep[status="failed"] {{ border-color: {ERROR}; }}
QFrame#pipelineStep[status="blocked"] {{ border-color: {WARNING}; }}
QFrame#pipelineStep[status="running"] {{ border-color: {ACCENT}; }}
QLabel#capabilityBadge {{
    min-height: 22px; padding: 1px 8px; border-radius: 11px;
    color: {TEXT_SECONDARY}; background: {CARD};
}}
QLabel#capabilityBadge[status="succeeded"] {{ color: {SUCCESS}; background: #10302A; }}
QLabel#capabilityBadge[status="failed"] {{ color: {ERROR}; background: #3A2024; }}
QLabel#capabilityBadge[status="blocked"] {{ color: {WARNING}; background: #3A3020; }}
QLabel#capabilityBadge[status="running"] {{ color: {ACCENT}; background: {ACCENT_BG}; }}
QLabel[class="stepTitle"] {{ font-weight: 650; }}
QLabel[class="stepDetail"], QLabel[class="stepMetrics"] {{ color: {TEXT_SECONDARY}; font-size: 8.5pt; }}
QFrame#dropZone {{
    border: 2px dashed {BORDER_STRONG};
    border-radius: {RADIUS_CARD}px;
    background: {PANEL};
}}
QFrame#dropZone[state="drag-active"] {{
    border-color: {ACCENT};
    background: {ACCENT_BG};
}}
QFrame#dropZone[state="scanning"] {{
    border-style: solid;
    border-color: {INFO};
}}
QFrame#dropZone[state="ready"] {{
    border-style: solid;
    border-color: {SUCCESS};
}}
QFrame#dropZone[state="blocked"] {{
    border-style: solid;
    border-color: {WARNING};
}}
/* 游戏档案编辑区：左侧黄色标记，不套大卡片 */
QFrame#profileCard {{
    background: {PANEL};
    border: none;
    border-left: 3px solid {WARNING};
    border-radius: {RADIUS}px;
}}
QFrame[class="sectionRule"] {{
    background: {BORDER};
    min-height: 1px;
    max-height: 1px;
    border: none;
}}
QLabel[class="pageTitle"] {{ font-size: 18px; font-weight: 600; }}
QLabel[class="title"] {{ font-size: 26px; font-weight: 700; }}
QLabel[class="subtitle"] {{ color: {TEXT_SECONDARY}; font-size: 10pt; }}
QLabel[class="statValue"] {{ font-size: 25px; font-weight: 700; }}
QLabel[class="statLabel"] {{ color: {TEXT_SECONDARY}; font-size: 9pt; }}
QPlainTextEdit#logView {{
    background: {LOGGER_BG};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 9.5pt;
    color: #c3cbd8;
}}
QFrame#toast {{
    background: {RAISED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 7px;
    border-left: 4px solid {INFO};
}}
QFrame#toast[success="true"] {{ border-left-color: {SUCCESS}; }}
QFrame#toast[error="true"] {{ border-left-color: {ERROR}; }}
QFrame#toast[warning="true"] {{ border-left-color: {WARNING}; }}
"""


def apply_theme(app: QApplication):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.Base, QColor(CARD))
    palette.setColor(QPalette.AlternateBase, QColor(CARD_HOVER))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(CARD))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor(PRIMARY_TEXT))
    palette.setColor(QPalette.ToolTipBase, QColor(PANEL))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    app.setPalette(palette)
    app.setStyleSheet(_QSS)
