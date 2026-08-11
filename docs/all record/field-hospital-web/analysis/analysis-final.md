# field-hospital-web 分析报告（闭环最终版）

## 1 游戏概况与语言分布

- 游戏：Field Hospital（战争叙事游戏，文本少）
- 文本量：721 识别条目（asset_unity 663 + mono_csharp 56；库状态
  translated 402 · failed 1 · skipped 318）
- 语言分布（预检实证）：**英文/ASCII 640 + 其他/无字母 81**——纯
  英文游戏（无字母 81 为引擎结构串）
- 翻译池：403 条 actionable

## 2 失败收敛过程

| 轮次 | 失败数 | 处置 | 确定性 |
|---|---|---|---|
| 首轮（08-12） | 1 | F25 口语助动词豁免 + 多行换行观察项（见 fix record） | 确定（逐条验证） |

## 3 失败分类（首轮 1 条）

### 3.1 叙事文本术语误杀（→ F25 修复，glossary 部分收敛）

| 形态 | 样本 | 真相 |
|---|---|---|
| 口语助动词 + 术语词 | `His sons, Matthew and Ralph, are gonna miss him dearly.` 译文「他的儿子马修和拉尔夫会非常想念他」 | 知识库词对 (miss, 未命中)（音游 HUD 判定标签，deadbeat 沉淀）误命中 miss=想念——`_glossary_verb_usage` 前邻词表缺口语助动词 gonna → 误杀。F25 加 gonna/wanna/gotta/lemme/dunno/oughta/ain't → 动词用法豁免生效 |

### 3.2 多行换行（观察项，模型边界）

| 形态 | 样本 | 真相 |
|---|---|---|
| 多段叙事文本换行合并 | `John Evans passed at age 87.\nHe fought bravely…` 译文并成一段 | 1.8B 合并多段换行（与 ffs 教学文本 2 条同类，第三次出现）；newline_mismatch/line_content_mismatch 正确拦截，保留原文安全。修复后该条 glossary_mismatch 已消除（测试断言），换行仍失败 → 观察项 |

## 4 正确性复核

- 首轮翻译 402/403 成功（235s），1 条失败全因可解释
- F25 修复后：`gonna miss` 叙事文本不再误杀（单行版通过质量门测试
  实证）；完整文本的换行合并仍由质量门正确拦截（观察项）
- 写回：400 条译文 PASS · revert 0 · 字体部署
- 回归：tests/test_glossary_sanitize.py +10 → 全量 1656 passed
- 知识库命中：FAIL-00027（containment jsonc 后缀）跨游戏复用

## 5 结论

**闭环成立**。首轮 1 条失败 = 叙事文本被音游术语 (miss, 未命中)
误杀（口语助动词 gonna 缺口）+ 多行换行合并（模型边界观察项）。
F25 系统性豁免后术语误杀消除；写回 400 条 PASS。实机测试按用户
指令跳过，云端审核停用。
