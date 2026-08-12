# inch-by-inch 修复记录（2026-08-13）

> 本轮价值：F9 意译误杀修复的首次游戏级实证 + F10 污染词对六连修复的
> 触发源（4 条 natural_language 误杀 + 2 条词对污染误杀 + 2 条正确拦截）

## 失败文本根因裁决（8 条）

| # | 原文 | 译文 | 根因 | 处理 |
|---|---|---|---|---|
| 1 | Start Ingredients: 5 | 起始成分：5 | **词对污染**：agent_memory 自动沉淀 (START→开始) active，全局强制误杀名词短语（Start 在此是定语非按钮动词） | F10 数据修正：START 词对降级 retired；F10c 功能词/单字母沉淀防护 |
| 2 | RESUME | 摘要 | **正确拦截**：内置 UI 词典 Q1 门（RESUME→继续），「摘要」是 resume 名词义误译 | 保持拦截（非 F9/F10 修复对象） |
| 3 | RESUME | 摘要 | 同上 | 同上 |
| 4 | INFORMATION ON AN "AS-IS" BASIS… | 基于"现状"提供的信息… | **词对污染**：(ON→关于)/(on→在) 强制误杀介词 ON（CC0 许可文本） | F10 数据修正：ON/on 词对降级 retired；F10 检查端功能词过滤 |
| 5 | …at this size! | …这种规模的解毒剂… | **F9 修复对象**：句尾标点（!）被当标签标记，(size→大小) 误杀意译「规模」 | F9 已修复（tail-punctuation 豁免）→ 本轮实证通过 |
| 6 | Time for some science!… | 是时候进行一些科学研究了！… | **F9 修复对象**：句子首词大写 + 右邻小写词被当标签，(Time→时间) 误杀「是时候」 | F9 已修复（sentence-head 豁免）→ 本轮实证通过 |
| 7 | …turn the Destillator on! | …打开分离器就行了！ | **F9 修复对象**：同上（Destillator 意译不受 (on→在) 影响场景） | F9 实证通过；on 词对降级后无残留风险 |
| 8 | …put this in the microwave… | …放入微波炉中… | **F9 修复对象**：同上 | F9 实证通过 |

## 修复记录（F9 是质量门修复、F10 为六连）

### F9（先前，本轮实证）：_label_context_match 意译误杀修复

- 句首大写 + 右邻小写词 = 英文句子首词大写规则 → 词对豁免（Time for…）
- 句尾标点（.!?。！？）不是标签标记 → 词对豁免（at this size!）
- 句中 TitleCase 仍应用（Open Settings menu 的 Settings 是 UI 词形态）
- 复验：本游戏 4 条 natural_language 失败全部 PASS（修复后重跑质量门）

### F10（本轮六连）：单 token 污染词对根治

| 修复 | 位置 | 内容 |
|---|---|---|
| F10a 数据修正 | ~/.hanhua/agent_memory.db | 6 条污染词对降级 retired：ON→关于、on→在、off→关闭、OFF→关闭、START→开始、HEALTH→健康（保留记录可人工复核）；glossary.db 删除 <b> 标签垃圾词对 b→整句译文（审核错误提取） |
| F10b 语境豁免 | quality.py `_label_context_match` | 占位符花括号边界豁免：{health} 内词是变量不是可翻译文本（incremental-rts 实证 HEALTH→健康 误杀「生命值」） |
| F10c 沉淀防护 | agent_memory.py propose | 单 token 英文功能词（on/off/in…，共享表 placeholders.FUNCTION_WORDS）证据充足也绝不晋升 active——保持 pending 可人工复核，session 计数 blocked_function_words |
| F10d URL 剥离 | placeholders.py SAFE_KEEPERS | 完整 URL（https?://…）段剥离——支持页链接行（MacOS: https://…）回显保留 URL 是正确行为，不再被 untranslated_text/词对误杀 |
| F10e candidate 不强制 | runner + translate_page | glossary 三源合并只取 active——candidate（审核沉淀未跨游戏复现）仅参考不强制（与 format_for_prompt 设计对齐；<b> 标签垃圾词对正是在 candidate 桶被强制化） |
| C5 扩展 | glossary.py | _HIGH_FREQUENCY_WORD_PAIRS 补 health/unit/damage/speed/power（health 语境变体多：健康/生命值/血量，审核沉淀端拒绝） |

## 审核不合格裁决（5 条，均为弱误判）

| 键位 | 审核结论 | 裁决 |
|---|---|---|
| e88 Play with Tutorial | 「Play 应译开始而非播放」 | **误判**：译文已是「开始教程」，审核建议复读译文 |
| e105 Shrinking Progress 100% | 「Shrinking 应指进度减少」 | **误判**：译文「减少进度」即正确语义，审核复读 |
| e112 RESUME WITH CURRENT SIZE | 「Resume 被误译简历」 | **误判**：译文「使用当前大小继续」无简历（审核幻觉） |
| e133 Carry Text | 「Carry 应译携带」 | **误判**：译文「携带」即正确语义（审核复读） |
| e347 Entering the wrong code… | 「Explodium 被误译收入」 | **误判**（理由幻觉）；但译文有真实问题：**第一句漏译**（审核盲区，未抓到） |

审核误判率 5/56 ≈ 9%——集中在术语字面对应/幻觉两类（低危噪声，报告流程带
「需人工确认」标注）。e347 漏译未被审核发现 → 登记为审核盲区观察项
（多行文本结构性漏译，审核模型只看单条译文）。

## 遗留问题（登记）

1. e347 类多行文本漏译（第一句整句丢失）——审核盲区，待后续（不在本游戏特判）
2. 4B 审核弱误判率 ~9%（术语字面对应/幻觉）——低危噪声，人工确认流程兜底
