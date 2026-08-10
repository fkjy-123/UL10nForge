# 修复 23：C# 日志拼接模板句结构跳过（_LOG_TEMPLATE_TAIL）

## 问题

crusty-proto 第一轮 1 条失败（Eflatun.SceneReference.dll）：

```
The address is not found in the Scene GUID to Address Map. Address:
```

C# 日志跨行拼接（`Debug.Log("... Address: " + address)`）在 DLL #US
字符串表里分裂成两段：「模板正文」与「拼接尾巴」（`Address: ` 结尾带
冒号空格）。尾巴段无右值可译，模型无法产出有效译文 → 恒败。

## 修复方案（hanhua/core/placeholders.py）

```python
_LOG_TEMPLATE_TAIL = re.compile(r"(?:[A-Za-z]+:|\w+\s*=)\s*$")
```

is_hard_structural 分支：

```python
if len(s) >= 20 and _LOG_TEMPLATE_TAIL.search(s):
    return True    # C# 日志拼接模板句（'Address: ' 尾部拼接点）
```

- 形态：句尾是「词: 」或「词= 」（C# 续行拼接点的典型形态）
- 长度 ≥20 防 `Press: ` 短 UI 提示误伤（交互提示是玩家可见文本，
  `Press: ` 应正常翻译；实测 18 字符以下均安全）

与 fix-21 `_GUID_LOG_TEMPLATE`（`GUID: xxx = `）同族：C# 日志模板家族。

## 先探索后回滚的方案（教训）

初稿尝试「短语整体专名豁免」（把 `Scene GUID to Address Map` 整短语
当专名放行）→ 37 个测试失败；修复后剩 2 个回归（WELCOME HOME 全大写
误放行、the End 功能词开头误放行）→ **整体回滚**。教训：豁免方案按
**语义**放行（专名）会把非专名一起放过；按**形态**跳过（日志尾巴）
只命中真日志句，无放行面。

## 修复代码位置

| 文件 | 位置 |
|---|---|
| hanhua/core/placeholders.py | `_LOG_TEMPLATE_TAIL` + is_hard_structural 分支 |
| tests/test_placeholders.py | test_log_template_tail_is_structural（正例 crusty 样本 + CustomController 样本；反例 `Press: `、正常句、地址行） |

## 验证

- 全量 1523 passed（+1）
- crusty-proto 第二轮：failed 1 → 0，skipped 403 → 398（1 条转结构跳过）
- 反例确认：`Press: `、`The address was not found. Please try again.`
  （正常玩家句）、`Address: 123 Main Street, New York`（真实地址行）
  均不跳过

## 防复发

- 形态判据（尾部拼接点 + 长度）与日志模板家族（GUID/输入插件/尾巴）
  统一为 is_hard_structural 结构跳过——DLL #US 日志分裂段玩家不可见，
  结构跳过比翻译更稳（无模型不确定性）
- 所有反例入测试锁定，防长度阈值或形态误伤
