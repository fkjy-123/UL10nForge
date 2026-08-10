# 修复 21：输入插件设备串结构跳过（InControl/Rewired 5 形态）

## 问题

第一跑 83 条失败中 **81 条**是输入插件（InControl/Rewired）的
**设备数据库内容**——sharedassets0.assets 多个输入配置对象
（obj=1840/1841/1871/1876/1878/1937/1975/1976/1977/1978/1979），
分布于 40+ 对象非单一对象，对象级跳过不适用：

| 形态 | 条数 | 样本 |
|---|---|---|
| 匹配正则 | 40 | `.*x[\-]*box[ ]*360.*`、`^([xX]iaoji )?Gamesir-G3[svw]?($| [0-9]+.*)` |
| 设备名 | 38 | `ipega media gamepad controller`、`Joy-Con (R)`、`idroid:con`、`idroid Snakebyte` |
| 版本占位 | 1 | `v?.??` |
| GUID 日志模板 | 1 | `CustomController device instance GUID: sourceId = ` |
| 首尾空白片段 | 1 | ` to JSON. `（写回容量截断 → object 闸门 WARN 根因） |

设备数据库运行时按名/正则匹配手柄——翻译破坏输入映射；且 1.8B 模型
对设备专名/正则回显恒败（untranslated 56 + target_script 26 双形态）。

## 修复方案（placeholders.py 五个通用形态）

```python
# 1. 设备匹配正则：'.*' 开头，或 '^'+首段无空格+元字符（防 markdown 误伤）
_INPUT_DEVICE_REGEX = re.compile(
    r"^\.\*[\s\S]*|^\^[^ \r\n]*[()\[\]?$|][\s\S]*")
# 2. 设备名四形态检测（冒号品牌 ID/品牌词+语境词/括号型号/纯品牌专名）
_INPUT_DEVICE_BRANDS = ("ipega", "idroid", "snakebyte", "gamesir",
                        "8bitdo", "madcatz", "3dconnexion", ...)
def _is_input_device_name(text) -> bool: ...
# 3. 版本占位模板（? 是占位信号；真实版本号 v2.5 走 _QUALIFIED）
_INPUT_VERSION_TEMPLATE = re.compile(
    r"^[vV]?[0-9?]+\.[0-9?]+\?+$|^[vV]?\?[0-9?]*\.[0-9?]+$")
# 4. C# 日志拼接模板尾部（'=' 是拼接点）
_GUID_LOG_TEMPLATE = re.compile(r"\bGUID:\s*[A-Za-z]+\s*=\s*$")
# 5. 首尾空白片段串（strip 前检测，非 CJK ≤48 字符）
_WHITESPACE_PADDED_FRAGMENT = re.compile(r"^\s+\S[\s\S]*\s+$")
```

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/placeholders.py | 5 个形态 + is_hard_structural 分支 |
| tests/test_placeholders.py | 4 个测试（正 23 反 8） |

## 验证

- 1522 passed（+7 本轮全部修复）
- 离线验证：83 条失败原文 **81 条**被结构跳过覆盖
- 第二跑 crash-back-in-time：见 analysis

## 防复发

- 任何输入插件（InControl/Rewired/Unity InputSystem）设备数据库自动覆盖
- 正则/设备名/冒号 ID 均为强形态信号，无自然语言误伤（Uka-Uka 长句、
  hihat cymbal、真实对话句全部保留）
