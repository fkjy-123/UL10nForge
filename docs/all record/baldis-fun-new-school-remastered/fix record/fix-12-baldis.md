# fix-12 baldis 六类失败根因（专名联想/彩色标签/词表/动作词/换行合并/纯小写回显）

游戏：baldis-fun-new-school-remastered（闭环于 2026-08-11，628/0 干净闭环）

## 背景

baldis 首轮 637/15 → 修复 5 项 → 640/6 → 新增 6 项修复（A-E + 恢复链）
→ 627/1（换行合并修复生效，暴露纯小写回显新失败）→ 引用两跳扩展 →
628/0。共经历 4 轮，前 3 轮失败全为真实模型跑出，逐条根因追查（含真实
模型 prompt 实测）。

## 失败与修复（全部通用机制，无单游戏特判）

### 第一轮修复（6 类，15→6）

| # | 失败条目 | 根因 | 修复 |
|---|---|---|---|
| 1 | UCLA Gold 回显 | 多词短语末位词（Gold）是版本后缀，被 UI 词典词判定拒绝 | `_ui_check_words`：多词跳过末位版本词，单词语义仍保留 |
| 2 | Playtime's 属格碎片 | 属格 `'s` 的 `s` 被 `\b[a-z]+\b` 视为独立小写词 | has_independent_lower_word 先剥离 rich-text + 跳过撇号前单字母 |
| 3 | "Jump During Playtime" 引号专名 | 交互动作词检查把引号内 TitleCase 短语当英文残留 | `quoted_proper_terms` 公共函数（译文引号内词必须在原文中），交互检查与 proper_name_echo 共用 |
| 4 | 词表条目回显 | `*shit`/`*beaner` 等词表条目（前置星号）被当普通文本翻译失败 | `_STAR_PREFIXED_WORD` → 结构跳过 |
| 5 | xChDC-Gs%OmaMl+g 混合符号 | 含 `%#&^$@\|` 强符号的 token 被当文本翻译失败 | `_MIXED_SYMBOL_TOKEN`（≥8 字符 + 字母，先剥离 rich-text，`!~` 语气词不拒）→ 结构跳过 |
| 6 | `//` 注释行 | 脚本注释行被当文本翻译 | `//` + 空白 → comment 跳过（URL `//host` 仍走协议相对 URL 判定） |

### 第二轮修复（6 项，6→1）

| # | 失败条目 | 根因 | 修复 |
|---|---|---|---|
| A | Error please contact game owner\nand check log. | 1.8B 稳定把多行合并为单行中文；multiline repair 逐行重译时首行被模型回显英文（`Error, please contact the game owner.`），重建失败 | **换行合并兜底**：换行原因（newline/line_content）是唯一失败原因 + 译文含中文 + 无空段（\n\n 是段漏译证据）→ 放行首译，meta 记 line_merged 供校对筛选 |
| B | Shirt Decal → T-shirt Decal | 模型把专名联想补词（Shirt→T-shirt）；`has_translatable_tail` 拦截导致专名引用重译不触发 | 专名引用重译触发条件从 untranslated_text 扩展到 target_script_mismatch；移除 has_translatable_tail（纯专名回显也重译，模型按引用保留专名） |
| C | Bossfight → bossfight | 模型小写化专名，被当英文残留 | 小写化专名豁免（原文 TitleCase 词在译文小写出现 → 放行），UI 词典词除外；**英语功能词（the/and 等）排除**（"The End is near"→"这是 the End 的开始" 的 the 是真实半翻，反例测试保障） |
| D | <color=green>Paused</color> 整对丢失 | 模型用引号替代彩色强调（稳定行为），完整标签对整体丢失 | 缺失占位符全是完整标签对 + 译文含中文 → 放行（样式整对损失无崩溃风险）；**单标签缺失/{0} 数据占位符仍失败**（反例测试） |
| E | *shit/*beaner（TextAsset 词表） | 词表条目含星号但不在 token 规则覆盖 | `_STAR_PREFIXED_WORD` 规则 + extractor/txt_format 注释行分支对齐 |

### 第三轮修复（2 项，1→0）

| # | 失败条目 | 根因 | 修复 |
|---|---|---|---|
| F | Error...（换行兜底不生效） | multiline repair 失败后复查把 quality_reasons 覆盖成修复结果原因（target_script_mismatch）→ 兜底「仅换行原因」判定失准 | **首译失败状态快照**：protected/multiline repair 失败后恢复（translation/status/reasons/meta），后续降级链基于首译判定 |
| G | outstanding citizen 回显 | 模型对纯小写普通词整句回显（untranslated_text）；降级链无分支覆盖（专名重译需 TitleCase、词级补译需译文含中文） | 词级补译触发扩展到「译文无中文 + untranslated_text」；`_repair_word_residue` 裸翻译输出仍回显（无中文）→ 逐词引用两跳（实测：裸→回显 / 引用→杰出公民 3/3） |

## 关键实证链

| 场景 | 修复前 | 修复后 |
|---|---|---|
| UCLA Gold | Gold 版本词被 UI 词典拒绝 → 失败 | 末位版本词跳过 → 通过 |
| 引号专名 "Jump During Playtime" | 动作词误判 → 失败 | quoted_proper_terms 豁免 → 通过 |
| *shit 词表 | 翻译回显恒败 | 星号前缀 → 结构跳过 |
| 彩色强调 <color>Paused</color> | 引号替代被判标签缺失 → 失败 | 完整标签对放宽 → 通过 |
| 换行合并（Error...and check log.） | repair 首行回显 → 恒败 | 首译状态恢复 + 换行合并兜底 → 放行 |
| outstanding citizen | 纯回显 → 恒败 | 引用两跳 → 杰出的公民 |
| The End is near → 这是 the End 的开始 | 小写化专名豁免误放行 | 功能词排除 → 仍失败（反例） |

## 验证

- baldis 最终跑：**628 条翻译 0 失败，全部写回**（637/15 → 640/6 → 627/1 → 628/0）
- 关键条目译文抽查：T恤贴纸 / 杰出的公民 / 农业活动目前处于"暂停"状态… /
  三角形按钮：暂停（在BOSS战模式下退出）
- 全量测试 **1479 通过 + 27 skipped，0 失败**（新增 11 个回归测试，含 4 条反例）
- D:/游戏/baldis-fun-new-school-remastered `_汉化` 目录与备份已删（做完一个删一个）
