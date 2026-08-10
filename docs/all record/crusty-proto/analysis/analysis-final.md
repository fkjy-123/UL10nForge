# crusty-proto 最终分析（第二轮闭环）

## 结论

**闭环达成：识别 500 → 翻译 102 完成 · 失败 0 → 写回 PASS（100 条译文）**

第一轮 failed 1（Eflatun.SceneReference.dll 日志模板句）→ fix-23
（`_LOG_TEMPLATE_TAIL` 结构跳过）→ 第二轮 0 失败。耗时 49.6s。

## 第一轮失败根因（1 条）

| 原文（截断） | 根因 |
|---|---|
| `The address is not found in the Scene GUID to Address Map. Address: ` | Eflatun.SceneReference.dll 调试日志模板句。`Address: ` 是 C# 代码 `"..." + address` 的拼接尾巴——DLL #US 字符串表把日志模板拆成「正文 + 续行拼接点」两段，模型无法翻译（缺右值），玩家不可见 |

## fix-23 方案

`_LOG_TEMPLATE_TAIL = re.compile(r"(?:[A-Za-z]+:|\w+\s*=)\s*$")`：
形态 = 句尾是「词: 」或「词= 」的续行拼接点（C# 字符串跨行 `+` 拼接的
典型形态）+ **长度 ≥20 字符**（防 `Press: ` 类短 UI 提示误伤）→ 结构跳过。

与 fix-21 的 `_GUID_LOG_TEMPLATE`（`GUID: xxx = `）同族——C# 日志模板
家族第三形态（前两者：GUID 日志、输入插件串）。

## 质量抽检（translated.txt）

| 原文 | 译文 | 判定 |
|---|---|---|
| Player | 玩家 | ✅ |
| FATAL ESCAPE | 致命的逃亡 | ✅ |
| CRUSTY PROTO | CRUSTY PROTO | ✅ 专名保留 |
| (working title) | （暂定名称） | ✅ |
| <b>3DI70R</b> - Coding, Modelling, Animation | <b>3DI70R</b> – 编程、建模、动画制作 | ✅ 富文本保留 |
| Thank you for playing | 感谢您的参与。 | ✅ |

## skipped 审计（398 条）

| 来源 | 条数 | 判定 |
|---|---|---|
| resources.assets（asset 内部串） | 194 | ✅ |
| sharedassets8/assets10（场景资源） | 34+17 | ✅ |
| Assembly-CSharp.dll | 34 | ✅ 代码内部串 |
| level0（关卡数据） | 25 | ✅ |
| Unity.Cinemachine.dll | 24 | ✅ 插件内部 |
| 其余 | 70 | ✅ |

无该翻而跳过的漏网。

## 经验沉淀

- **DLL #US 字符串表的日志模板分裂**：Unity 插件 DLL 的字符串表常把
  完整日志拆成「模板正文 + 拼接尾巴」多段（`Address: `、`GUID: xxx = `），
  这类段落在语义上无法独立翻译，且玩家不可见——**形态级结构跳过**是
  唯一正确解（逐条豁免会漏，硬翻译会恒败）
- 尾巴形态「词: 」/「词= 」+ ≥20 字符的高置信判据可推广到所有 C# 日志
