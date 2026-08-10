# 修复 18：插件内部串结构跳过（YarnSpinner 键/C# 插值/调试行/节点标签）

## 问题

第一跑 233 条失败中 **229 条**是 YarnSpinner 字符串表键（`line:hash`）：
对话文本以 `line:` + FNV 哈希键引用、真实文本在**同一对象**的邻近字符串
（obj=1354 实证：214 个键 + 对话文本同对象，文本已正确提取翻译）。
键不是玩家可见文本，模型回显恒败（untranslated 216 / target_script 15 双形态）。

另 4 条插件内部串：

| 原文 | 形态 | 性质 |
|---|---|---|
| `ACTION edge` | 全大写节点类型 + edge | YarnSpinner 对话图编辑器节点边标签 |
| `Can't save variables to JSON: {nameof(variableStorage)} is not set` | C# 编译期插值残留 | YarnSpinner 错误日志模板 |
| `(Debug): 1000` | (Debug): 前缀 | 调试 HUD 输出行 |
| `SFX` | 全大写 3 字母缩写 | 界面标准术语（见修复 19） |

## 修复方案（placeholders.py 四个通用形态）

```python
# YarnSpinner 字符串表键
_LINE_HASH_IDENTIFIER = re.compile(r"^line:[0-9a-fA-F]{6,}$")
# C# 编译期插值残留（{nameof(x)} / {typeof(T)}）：日志模板
_C_SHARP_INTERPOLATION = re.compile(r"\{nameof\(|\{typeof\(|\{nameof\b")
# 调试 HUD 输出行
_DEBUG_PREFIX_LINE = re.compile(r"^\([Dd]ebug\)\s*:")
# YarnSpinner 编辑器节点边标签
_UPPERCASE_EDGE_LABEL = re.compile(r"^[A-Z]{2,} edge$")
```

is_hard_structural 各加分支（`_GUID_IDENTIFIER` 家族——内部键标识）。

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/placeholders.py | 4 个正则 + is_hard_structural 4 分支 |
| tests/test_placeholders.py | `test_yarnspinner_line_hash_and_log_forms_are_structural`（正 7 反 4） |

## 验证

- 1515 passed（+1）
- 第二跑 count-my-coins：**233 → 1**（剩余 Krapos 见修复 20）

## 防复发

- `line:hash` 与 `_GUID_IDENTIFIER` 同家族（对话系统/资源内部键标识），
  任何对话插件（YarnSpinner/Dialogue System）自动覆盖
- C# 插值模板/调试前缀/节点标签均为强形态信号，无自然语言误伤
