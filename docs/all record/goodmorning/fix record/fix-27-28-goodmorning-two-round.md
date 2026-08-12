# goodmorning 修复记录：两轮修复闭环（fix-27 / fix-28）

## 结论

三轮排查：3 失败 → 2 → 1。前两条为系统性误杀（fix-27/fix-28 修复，
均已单独提交）；最后 1 条（游戏标题回显）判定为合理失败不修。
**行为侧闭环**：完美译文被救回，无真实失败。

## 第一轮 → fix-27：键名强制保留（跨游戏污染源拦截）

**现象**：3 失败。其中 [3] `Camera Control - <#ffff00>Shift + RMB
</color>Zoom - <#ffff00>Mouse wheel.` 的译文（正确保留 Shift/RMB）
被 glossary_mismatch 误杀。

**根因**：force-reboot 中 RMB 被 1.8B 译「人民币」（SHIFT→移位、
RMB\nTO\nSCOPE→人民币\n给\n范围 同类）——当时质量门**无键名保留
检查**，错误译文通过质量门被 AgentMemory 沉淀成 active 词对
（evidence 4，同一错误重复出现=高证据污染）→ goodmorning 正确
译文被污染词对误杀；fix-26 词对直填还会把污染词对放大成强制译文。

**修复**（engine_strings.py + quality.py，提交 539b170）：
- PHYSICAL_KEY_NAMES_CASEFOLD 补 RMB/LMB/MMB（鼠标键名缺口）
- `key_name_mistranslated` 检查：译文有中文但原文键名被译掉 →
  判失败（防源头沉淀：RMB→人民币 被拒，不再进记忆）
- glossary 键名词对豁免：词对 source 是键名 → 检查跳过（键名
  不该被翻译，词对本身是污染）
- 排除兼作普通英语词的键名（control/pause/return…）：'Camera
  Control' 的 Control 是普通词，强制保留误杀
- 数据清理：3 条污染词对退休（保留审计痕迹）

**验证**：2 个回归测试。第一轮 3 → 第二轮 2（[3] 修掉）。

## 第二轮 → fix-28：单 token 词对子串命中需标签语境

**现象**：第二轮剩 [2] `you're all ready -\ntime to take on the day!`
译文「你们都准备好了——是时候开始这一天了！」（语义完美）仍被
glossary_mismatch 误杀。

**根因**：(TIME→时间) 词对（force-reboot 计时器 UI 词沉淀）子串
命中自然句 "time to"——意译「是时候」不含「时间」→ 误杀。fix-26
精确词对优先不覆盖（原文非精确命中）、fix-27 键名豁免不覆盖
（time 非键名）。本质：**单 token 普通词词对子串命中自然句必然
误杀意译**。

**修复**（quality.py，提交 954c242）：
- `_label_context_match`：单 token 词对子串命中处为**标签语境**
  才检查——标点邻接（'miss: 999' 的 miss 右邻冒号）、数字邻接、
  行首/行尾（'TIME' 单独一行）、TitleCase/全大写命中（'Open
  Settings menu' 的 Settings 是 UI 菜单词形态）
- 自然句纯小写命中（'time to' 前后都是字母词）→ 词对不适用，
  意译放行
- 多词短语词对（ENTER NAME）不受影响

**验证**：1 个回归测试。第二轮 2 → 第三轮 1。

## 第三轮 → 合理失败（不修）

**现象**：剩 [1] `good morning`（app.info 游戏标题）→ 模型回显
"Good morning." 判 untranslated_text。

**判定**：游戏标题保留原文是业界惯例（Steam 商店页游戏名不译）；
app.info 是元数据（引擎不解析，无功能破坏，不译或本地化均可）。
模型对问候语+标题形态稳定回显，重试无益 → **不修复**，记观察项：
若同一游戏内出现批量标题形态误译则升级识别层。

## 验证方式

- 每轮修复后全量测试通过才提交；提交后以最新版本重跑
- 第三轮：178 条翻译 1 失败 · 写回 175 条 PASS · 重开验证 True
- AgentMemory 首次实证直接应用：28 采纳 28 拒绝 0（跨游戏记忆
  开始真实工作，见 memory-report.md）

## 遗留观察项

- good morning 标题回显（单条，不修）
- 语境冲突 64 条：AgentMemory 多语境词对提示（随游戏数增长，
  记忆模块的语境分化信号，人工确认机制见 memory-report.md）
