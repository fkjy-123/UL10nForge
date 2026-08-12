# force-reboot 修复记录：三轮修复闭环（fix-24 / fix-25 / fix-26）

## 结论

三轮排查定位三组系统性根因，三次修复后第四轮 **失败 26 → 0，闭环**。
每轮修复单独提交，随后以最新版本重跑验证（用户指令：修复后先提交再用最新版本继续）。

## 第一轮 → fix-24：词库型 TextAsset 整文件跳过

**现象**：164 失败（识别 401 条中 144 条是脏话检测黑名单词库条目）。

**根因**：data.unity3d#obj268 是 1100+ 行单词词库（脏话黑名单/词典/名单），
是**对比数据非显示文本**——单词行（无空格/≤40 字符/纯 ASCII 词）占比 ≥90%
即词库特征，被识别器当显示文本逐行翻译。

**修复**（extractor.py，提交 673b52d）：
- `_is_lexicon_word()`：`^[A-Za-z0-9][A-Za-z0-9'_.-]{0,39}$` 单词形态
- 判定：单词行占比 ≥90% 且行数 ≥30 → 整文件跳过（reason: `textasset_lexicon`）
- 防误伤：对话文本（31 行以上仍正常提取）、短词表（<30 行不判）、
  `=` 赋值行混排（词库通常纯单词行）均保留提取

**验证**：4 个回归测试（词库→空+skipped 计数 / 对话不误判 / 短词表保留 /
赋值行混排保留）。第一轮 164 → 第二轮 19。

## 第二轮 → fix-25：单词词表译例沉淀 + 格式模板豁免 untranslated_text

**现象**：19 失败（JUMP/VSYNC 回显 16 + 日期格式 3）。

**根因 A（回显）**：JUMP/Vsync/VSYNC 是单 token 全大写/驼峰键名，1.8B 模型
带译例仍稳定回显（纯能力边界，非识别问题）。

**修复 A**（knowledge.py，提交 9fac435）：
- `_is_single_lexicon_word()`：单 token 词命中动作动词/常用名词词表
- learn() 沉淀 `single_lexicon_word` kind + map_to（JUMP→跳跃、Vsync→垂直同步），
  跨游戏复用；词表新增 "vsync": "垂直同步"
- 专名保留检测（ZARBUL 之类）不学，防污染

**根因 B（格式串）**：yyyy-MM-dd HH:mm:ss 日期/数字格式模板回显被 quality
untranslated_text 误判「未翻译」。

**修复 B**（quality.py，提交 9fac435）：
- `_is_format_template()`：`^[0-9{}:\-./,_%#+TZzHhMmSsFfKkyd ]+$`
  且非纯字母 → 回显不判 untranslated_text
- 防误伤：纯字母串（普通词）不受影响

**验证**：3 个回归测试 + knowledge 库实测（format_reference_pairs 含
(JUMP, 跳跃)/(Vsync, 垂直同步)）。第二轮 19 → 第三轮 26（数字变多，见下）。

## 第三轮 → fix-26：三根因——精确词对优先 / 格式模板补豁免 + 自愈 / 词对确定性直填

**现象**：26 失败，三组独立根因：

### 根因 A：JUMP 类 16 条——1.8B 能力边界，译例不够

知识库词对、system prompt 译例、references 译例**三者齐备**模型仍回显。
验证结论：单全大写词对 1.8B 稳定回显（chat 与 native 两路均验证），
必须**确定性直填**而非继续依赖模型。

**修复 A**（batch_translator.py）：
- `__init__` 构建 `_glossary_exact`（casefold→译文 精确索引：术语表 +
  knowledge_pairs + agent_pairs 全量）
- `_chat_each` 语言选项直填之后、模型调用之前：原文精确命中词对 →
  直填译文 + 质量门复查（`_apply_quality`）→ 通过则 translated
  （meta `deterministic_fill=glossary_pair`），被拒（词对污染）恢复原状
  走正常模型链
- 专名词对（FOXYPAW→FOXYPAW）直填=回显，质量门专名豁免链放行，
  行为与模型一致
- 顺序优先于模型：精确命中词对就是本条目的权威译名，比 1.8B 更稳

### 根因 B：ENTER NAME/Layer 2/Damage Up 等 7 条——AgentMemory 词对子串冲突

AgentMemory 沉淀独立词对 (NAME→名称)、(Layer 1→第1层) 等；quality
glossary_mismatch 循环用**子串匹配**（source_term_applies），正确译文
「输入姓名」被 (NAME→名称) 子串命中误判失败。

**修复 B**（quality.py）：
- 精确词对优先：原文精确匹配某词对 source 时只查该词对，子串词对
  全部跳过——原文精确命中表示该词对就是权威译名，其它子串词对语义不相关
- 精确词对仍是权威：译文不含其 target 照常判失败（翻译义务不豁免）
- 豁免链（保留型/法语/专名邻接/动词用法/歌词）对精确词对照常生效

### 根因 C：yyyy-MM-dd 3 条——格式豁免只补了 untranslated_text 半面

fix-25 豁免了 quality 侧 untranslated_text，但 batch_translator
`_apply_quality` 的 target_script_mismatch 判定（`_has_disallowed_
chinese_target_letters` 残留英文）仍拦——格式串纯 ASCII 回显必然命中。

**修复 C**（batch_translator.py）：
- 目标脚本判定两个分支加 `_is_format_template` 豁免
- 格式模板自愈：模型「修正」格式串（.ss→:ss 实证）是格式破坏 →
  重建 QualityResult 恢复原文（不可译文本任何改动都是破坏）
- echo_exempt 打标新增 `format_template`（写回/统计可见是回显保留
  非真译文；记忆写入跳过防「原文→原文」无效记忆污染）

**验证**：5 个回归测试（格式串回显豁免 ×3 参数 / 模型改动自愈恢复 /
精确词对优先 + 权威性保持）。全量测试 1884 passed。
**第三轮 26 → 第四轮 0，闭环。**

## 验证方式

- 每轮修复后全量测试通过才提交；提交后以最新版本重跑本游戏
- 第四轮：401 条翻译 0 失败 · 写回 375 条 · 重开验证 True
- 数据库实测：knowledge.db 含 single_lexicon_word 词对（JUMP→跳跃、
  Vsync→垂直同步）可跨游戏复用

## 遗留观察项

- 单全大写键名词对直填依赖**词对质量**：learn 沉淀错误词对会被质量门
  拒绝（修复 A 的复查兜底）——但词对一旦通过直填即跳过模型，后续
  词对更新（同源异译）需人工在术语/知识库修正
- RESUME→摘要（foxhunt 观察项）在 force-reboot 未复现，观察继续
