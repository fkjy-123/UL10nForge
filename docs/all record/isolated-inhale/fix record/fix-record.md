# isolated-inhale 修复记录（2026-08-13）

> 本轮价值：**无新修复**——验证 F13 与既有修复在正常游戏上的表现；
> 58 条判定误杀证明词对语境保护（F22 系）与脚本豁免修复有效。
> isolated-inhale 是标准 Unity Mono 驾驶/模拟类游戏（无 Undertale
> 系对话标记），质量门表现 8 款游戏最佳。

## 背景

isolated-inhale（270M，Assembly-CSharp.dll + level0 + StreamingAssets，
含 Discord/Steam 集成痕迹）——标准 Unity Mono 游戏，文本以
MonoBehaviour 字符串 + JSON 本地化为主，无对话脚本标记。

## 本轮无新修复（验证轮）

| 修复 | 状态 | 验证 |
|---|---|---|
| F13 对话脚本三修 | 已修复（interdream 轮） | 本游戏 9147 写回仅 1 条缺陷（无对话标记故几乎不触发） |
| 词对语境保护（F22 系） | 已修复 | 44 条 glossary_mismatch 放行——文件名段豁免/组合词对生效 |
| 脚本豁免（域名/代码片段） | 已修复 | 14 条 target_script_mismatch 放行 |
| 键名保护（key_name_mistranslated） | 生效 | RMB→人民币 正确拦截（键名是 RMB=鼠标右键，非货币） |

## 失败文本裁决（139 条终版）

| 类别 | 条数 | 裁决 |
|---|---|---|
| 判定误杀（代码演进后放行） | 58 | 44 词对误杀 + 14 脚本误判——F22 系/脚本豁免修复的实证 |
| 键名误翻（RMB→人民币） | 少量 | key_name_mistranslated 正确拦截 |
| 代码逻辑串翻译 | ~20 | target_script_mismatch 正确拦截（Awake() 方法体等） |
| 调试串/回显 | ~10 | untranslated 正确拦截 |
| 其他（半翻译/占位符） | 少量 | 质量门各规则正确拦截 |

## 已写回缺陷译文（终版 1 条）

`LBL_NO_CHIPS`（`asset#resources.assets#1371/json`）——意大利语
原文 `\n` 换行合并（newline_mismatch + line_content_mismatch）。
详见 [[f13-defect-written-list.md]]。登记人工重译（与 interdream
208 条 / incremental-rts F12 4 条同处理）。

## 修复验证

- 全量回归 **2045 passed**（F13 轮后基线，含 interdream 新增 3 测试）
- 质量门 9147 写回复验拦截 1 条（0.01%）——8 款游戏最低缺陷率
- 记忆命中 3——跨游戏记忆直填首轮生效

## 遗留问题（登记）

1. 1 条已写回缺陷译文（LBL_NO_CHIPS 换行合并）——人工重译
2. **多语言盲区**：识别层对中文/俄语文本未入翻（语言分布显示
   523 中文 + 483 俄语）——识别修复候选，需确认是否开发者残留
3. 语义审核 432 条不合格中术语类 280 条（64.8%）——模拟类输入
   术语（THRUST/STEER/Input/Value）1.8B 把握弱，建议人工批量
   核对术语表后重译；C5 门禁已拒绝 Load 沉淀（防污染）
