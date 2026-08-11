# fix-09：间隔动作词聚合重译 + self_heal 尾部缺口补全（F8-A/F8-B）

> 触发：a-catfiends 闭环后重跑（2026-08-11，F8 轮）发现 5 条失败。
> 复盘：历史第八跑闭环时 8 条失败被判定「翻译侧合理」接受，其中 6 条
> 间隔动作词回显被历史分析明确「语义上应放行」但未实现；本轮实现
> 翻译（用户指令：英文文本就要翻译）。本轮 5 条 = 4 条间隔动作词回显
> （历史遗留形态）+ 1 条 {w=3}{x} 尾部标签丢失（历史同句成功过，模型
> 行为波动暴露 self_heal 锚点盲区）。

## F8-A 间隔动作词聚合重译

**现象**：`{punch=3,2}* Y A W N *{w=3}{x}` 等 4 条（YAWN/GASP/SCOFF/
VOMITS）模型 4 次重试稳定回显 → untranslated_text 恒败。

**根因（两层）**：

1. **判定失效**：`_is_spaced_action` 只 `strip("* \t")`，`{punch=3,2}`
   前缀剥不掉 → parts 含 `{punch=3,2}*` 多字符 → 判定 False。回显靠
   `has_independent_lower_word`（单字母词 Y/A/W/N）判失败——判定路径
   绕过了设计意图（special_action 是「可翻译语义文本」的身份标记）。
2. **修复链无兜底**：special_action 回显触发词级补译/专名重译，但间隔
   词是单字母（Y/A/W/N 各 1 字母），词级补译 3<=len<=16 条件不满足、
   无 TitleCase 专名 → 全部落空 → 普通重试（模型仍回显）→ 耗尽失败。

**修复**（两处，通用规则）：

- `knowledge.py` `_is_spaced_action`：判定前剥 `{[^{}]*}` 对话动画标签
  （{punch}/{w=3}/{x} 是动画参数不是词）。
- `knowledge.py` 新增 `aggregate_spaced_letters`：`* Y A W N *` →
  `* YAWN *`（打字机逐字动画的视觉写法聚合为正常词）。
- `batch_translator.py` 修复链新增 `_repair_spaced_action_translation`
  （位置：专名重译后、多语言双跳前）：special_action 回显 →
  聚合版原文重译 → 质量门判定。

**实验实证**（1.8B 真实模型）：

| 输入 | 输出 | 结论 |
|---|---|---|
| `{punch=3,2}* Y A W N *{w=3}{x}`（原形态） | 乱码/回显 | 无法翻译 |
| `{punch=3,2}* YAWN *{w=3}{x}`（聚合形态） | `{punch=3,2}* 哎呀 *{w=3}{x}` | ✅ 中文 + 标签原位保留 |

## F8-B self_heal 尾部缺口补全

**现象**：`I am {punch=3,2}NOT who I used to be.{w=3}{x}` → 译文
「我已经不再是曾经的我了。{punch=3,2}」丢 `{w=3}{x}` → placeholder_
mismatch 恒败。**历史第六跑同句翻译成功**（「你已不再是从前那个你
了。」，标签全部原位保留 ✓）。

**根因**：`self_heal_format_tags` 缺口补全的锚点限制
`len(missing_idx) >= len(dst_texts)` 过度保守——丢 2 留 1（missing 2
>= dst 1）直接拒绝补全。历史只丢 1 个（{w=0.5}，missing 1 < dst）能补，
本轮模型丢 2 个 → 盲区暴露。

**修复**（placeholders.py）：锚点不足时**仅当**缺失是 src 尾部连续
缺口（最后一个缺失占位符本身位于原文末尾，如句末 `{w=3}{x}`）→
append 恢复的是原文原位置，可确定性补全。`'Press <color=red>E</color>
to continue'` 的 `</color>` 后还有文本（非原文末尾）→ 仍拒绝
（append 会拉长样式范围，须重试暴露）。

## 测试

- `tests/test_knowledge.py`：标签前缀间隔词判定 + 聚合函数 + 完整句
  不误判
- `tests/test_placeholders.py`：尾部缺口补全（a-catfiends 真实样本）
  + 中段缺口仍拒绝（对照）
- `tests/test_batch_translator.py`：聚合重译端到端（translate_text
  收到聚合版原文、译文通过质量门）+ 非间隔词不触发（对照）
- 回归确认：`test_partial_tag_missing_still_fails`（`</color>` 后仍有
  文本 → 拒绝补全）保持通过

## 重跑结果

**F8 修复后 5 失败 → 3 失败**（YAWN/GASP/VOMITS 通过聚合重译修复，
SCOFF/SIGH/fieldtrigger 仍败）：

1. **SCOFF/SIGH：模型能力边界（F10-A 解决）**。实时实测：1.8B 对聚合
   形态 `* SCOFF *`/`* SIGH *`/`* YAWN *`/`* GASP *` 仍稳定回显（只去
   空格不翻译，VOMITS 偶译「吐出物」质量差）——上一轮「聚合后可翻译」
   的实验结论不适用于这批词（动作旁白词不在模型翻译范围）。实现
   `_SPACED_ACTION_LEXICON` 封闭词典（约 120 个动作/音效词），
   `_repair_spaced_action_translation` 聚合后先查词典**确定性直填**
   （不走模型），未收录才交模型。实时验证：`{punch=3,2}* S C O F F *
   {w=3}{x}` → `{punch=3,2}* 嗤笑 *{w=3}{x}`（good=True，标签原位
   保留）。
2. **fieldtrigger：逻辑字符串（F10-B 解决）**。孤立纯小写长词（≥10
   字符）是触发器/字段名形态（fieldtrigger 12 字符实证）——single_
   visible 分支不再无条件放行，`isolated_lowercode_word` 跳过
   （structural）。对照：222am 场景词 shower/city/bedroom（短词）不受
   影响。翻译 fieldtrigger 会断链（游戏按原名查触发器）——跳过是
   正确行为，不是「该翻未翻」。

**结论：3 条剩余失败全部有确定性方案（词典直填 + 识别层跳过），
非模型随机性——同类形态不再复发。**
