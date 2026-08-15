"""序列化脚本类注册表：确定性类名 → 对象级 disposition（识别 L9）。

L6 已能从 MonoBehaviour 的 m_Script PPtr 解析出确定性脚本类名
（extractor._script_class_of），但此前只用在 InputSystem/Timeline 两个
信号集合上。本注册表把它推广为登记制：

- config：引擎/资源配置类——对象内字符串是运行时按名查找的键或
  资产元数据（字体名/精灵名/动作名），翻译必断引用。确定性跳过
  （取代/先于 is_tmp_asset_object 等串池信号猜测，证据分层）；
- display：显示组件类——对象内字符串多为显示文本，确定性证据
  优先于「小配置对象」等形态猜测（猜测不得推翻确定性）；
- 未登记类名：不判定（走既有启发式链），由提取器收集进报告
  「待登记类队列」——每遇一个新游戏类名，人工过一遍后加一行，
  而非新增一条正则（与 morphology.py 形态注册表同模式）。

每行带出处分组（与 L7 字段白名单登记制同模式），新增必须可审计。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class ClassEntry:
    name: str
    disposition: str   # config / display
    group: str         # 出处分组（可审计）


# config 出处分组：
#  tmp_asset  = TMP 字体/精灵资产（headache 实证：资产名是 <font>/
#               <sprite> 按名引用键，翻译断引用→字体/表情丢失）
#  input      = InputSystem 配置（morfosigame/deadbeat 实证：动作名
#               按原名查找，翻译破坏按键交互）
#  timeline   = Timeline 演出配置（morfosigame 实证：轨道/剪辑名
#               翻译破坏反序列化）
# display 出处分组：
#  ui_text    = TMP/UI 文本组件（指南 §3.2 显示组件）
_CLASS_ROWS: tuple[ClassEntry, ...] = (
    # ── config ──
    ClassEntry("TMP_FontAsset", "config", "tmp_asset"),
    ClassEntry("TMP_SpriteAsset", "config", "tmp_asset"),
    ClassEntry("InputActionAsset", "config", "input"),
    ClassEntry("InputActionMap", "config", "input"),
    ClassEntry("InputActionReference", "config", "input"),
    ClassEntry("PlayerInput", "config", "input"),
    ClassEntry("InputControlScheme", "config", "input"),
    ClassEntry("TimelineAsset", "config", "timeline"),
    ClassEntry("PlayableDirector", "config", "timeline"),
    # ── display ──
    ClassEntry("TextMeshProUGUI", "display", "ui_text"),
    ClassEntry("TMP_InputField", "display", "ui_text"),
    ClassEntry("TextMeshPro", "display", "ui_text"),
)

CONFIG_CLASSES: frozenset[str] = frozenset(
    e.name for e in _CLASS_ROWS if e.disposition == "config")
DISPLAY_CLASSES: frozenset[str] = frozenset(
    e.name for e in _CLASS_ROWS if e.disposition == "display")


@lru_cache(maxsize=None)
def disposition(script_class: str) -> str | None:
    """脚本类名 → 'config' / 'display' / None（未登记，走启发式链）。"""
    if script_class in CONFIG_CLASSES:
        return "config"
    if script_class in DISPLAY_CLASSES:
        return "display"
    return None
