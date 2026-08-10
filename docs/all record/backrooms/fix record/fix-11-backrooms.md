# fix-11 backrooms 五类失败根因（提取器对齐/数字邻接/词级补译/专名重译/保留术语）

游戏：backrooms（闭环于 2026-08-11，211/0 干净闭环）

## 背景

backrooms 首轮 209 成功 / 4 失败，全部为真实模型跑出的失败。逐条根因
追查（含真实模型 prompt 实测）→ 修复 6 项通用机制 → 次轮 210/1（新
发现保留型术语误拒）→ 修复 → 211/0。

## 失败与修复（全部通用机制，无单游戏特判）

| # | 失败条目 | 根因 | 修复 | 文件 |
|---|---|---|---|---|
| 1 | `nolog=`（boot.config） | **extractor 内联版漂移**：`_extract_txt_text` 缺 txt_format.extract_txt 的 kv_empty 分支——`if m and m.group("value").strip()` 为空值时落 else 走 plain → 配置项被翻译 → 模型回显恒败。txt_format 有该分支（Morfosi 实证修过），extractor 未对齐 | extractor 改为与 txt_format 相同的三层 kv 分类（value 空 → kv_empty skipped；should_skip → kv_structural；否则 kv） | `extractor.py` |
| 2 | 开发致谢 8 行（4chan） | **数字邻接词碎片**：译文保留 `4chan` 被 `_ENGLISH_WORD` 拆出小写碎片 `chan` → 孤立小写词误判英文残留（target_script_mismatch） | **数字邻接词豁免**：`_ENGLISH_WORD` 提取的词紧邻数字（`\d` 直接邻接，空格隔开不算）→ 该词为数字混合形态（网站/用户名/版本号），且要求原文也含该词（防模型幻觉）→ 豁免 | `batch_translator.py` |
| 3 | `itch page` 漏翻残留 | 模型对长句整译时漏翻短语，译文已含中文但残留 `itch page`。**词级补译 v1 缺陷**：裸短语翻译 `itch page` → `痒页面`（1.8B 把 itch.io 的 itch 当普通词直译，实测稳定误译） | **词级补译两跳**：① 裸短语翻译；② 输出纯中文（可能直译误译）→ 逐词保留引用重试 `[(itch,itch),(page,page)]`——模型确认的专名会保留原文（实测 `itch page`+引用 → 3/3 `itch 页面`）；两跳不一致 → 引用版可信（模型识别专名），一致 → 用第二意见 | `batch_translator.py` |
| 4 | `Markiplier was here` 纯回显 | 模型对专名+短句回显，重试仍失败 | **专名 references 重译**：译文纯回显（untranslated_text）+ 原文含 TitleCase 专名 + 其余可译（含小写词）→ 注入 `(专名,专名)` 引用重译整句（模型把专名当术语保留、只译其余，实测 → `Markiplier 在这里`）；纯专名回显（Crash Bandicoot 无小写可译部分）不触发 | `batch_translator.py` |
| 5 | `Enter custom FPS...`（次轮新发现） | **保留型术语误拒**：learn_proper_names 自动沉淀 `FPS→FPS`（上轮译文保留 FPS）→ 质量门 glossary_mismatch 要求译文含 `FPS`——本轮模型译出更忠实的 `输入自定义帧率...`（不含 FPS）→ 被拒 | **保留型术语放宽**：term→term 原样术语（learn 自动沉淀的专名/缩写保留映射）被模型翻译成中文是合理行为（FPS→帧率 优于强制保留）——译文含中文翻译时不算 mismatch；纯回显（无中文）仍判失败 | `quality.py` |
| 6 | （同 3 的根治） | itch.io 的 itch 跨游戏高频被直译「痒」——模型对低频小写专名不稳定（同一行实测 4 次：3 次 itch 页面 / 1 次痒页面） | **内置平台名保留引用** `("itch","itch")` + 知识库 text/platform_name 形态规则（on/at + 平台名 + page/store 语境 → keep_source）。带引用整行实测 4/4 全部保留 itch | `translator.py` `knowledge.py` |

## 关键实证链

| 场景 | 修复前 | 修复后 |
|---|---|---|
| boot.config `nolog=` | plain 被翻译回显恒败 | kv_empty skipped（extractor 对齐） |
| 译文保留 4chan | chan 碎片误判残留 → 失败 | 数字邻接豁免 → 通过 |
| 残留 itch page | 裸短语直译「痒页面」（误译） | 逐词引用两跳 → itch 页面 |
| Markiplier was here | 纯回显失败 | 专名引用重译 → Markiplier 在这里 |
| FPS 术语沉淀后 | 「帧率」译文被拒 | 保留型术语放宽 → 通过 |
| itch 平台名 | 模型直译「痒」（不稳定） | 内置引用 4/4 保留 → itch 页面 |

## 验证

- backrooms 最终跑：**211 条翻译 0 失败，全部写回**（209/4 → 210/1 → 211/0）
- 关键条目译文抽查：itch 页面 / Markiplier 在这里 / 4chan 保留 / 输入自定义帧率
- 全量测试 **1465 通过 + 27 skipped，0 失败**（新增 9 个回归测试）
- D:/游戏/backrooms `_汉化` 目录与备份已删（做完一个删一个）
