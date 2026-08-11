# field-hospital-web 修复记录（F25 口语助动词豁免）

## 问题：叙事文本被音游术语误杀（2026-08-12 首轮实证）

field-hospital-web 首轮翻译失败 1 条——`resources.assets` obj=39 的
aftermath note（阵亡士兵纪念文本）：

```
原文：John Evans passed at age 87.\nHe fought bravely for the Republic
during the War and ended up with the rank of Corporal. Shortly after he
met Florence and married her. His sons, Matthew and Ralph, are gonna
miss him dearly.
译文：约翰·埃文斯在87岁时去世。他在战争期间为共和国英勇战斗，最终
获得了下士军衔。不久之后，他与弗洛伦斯相识并结婚。他的儿子马修和
拉尔夫会非常想念他。
失败：newline_mismatch + line_content_mismatch + glossary_mismatch
```

译文质量很高（忠实完整），glossary_mismatch 是误杀。

**根因**：知识库词对 `(miss, 未命中)`（deadbeat 音游 HUD 判定标签
沉淀，loaned_word 型）命中叙事文本的 miss=想念。`_glossary_verb_usage`
（动词用法豁免）检查术语词前邻助动词（to/can/will/be 等 + 代词），
但 **`gonna`（going to 口语缩写）不在前邻词表**——`are gonna miss`
的 miss 前邻 gonna → 豁免失败 → 误杀。

## 修复（F25，系统性通用规则）

**quality.py `_glossary_verb_usage` 前邻词表**加口语助动词缩写：

```
gonna（going to）、wanna（want to）、gotta（got to）、
lemme（let me）、dunno（don't know）、oughta（ought to）、
ain't（am not/is not…）
```

英语对话/叙事文本高频出现这些口语缩写（游戏对话尤甚），其后术语词
（miss/like/have 等）必然是动词用法，与术语表的标签含义无关。

**防过宽**：`miss: 999` 标签格式（deadbeat 实证）前邻冒号 → 不豁免；
UI 词典词/专名形态术语不适用此豁免（既有守卫不变）。

## 实证

- 单行版 `His sons, Matthew and Ralph, are gonna miss him dearly.` →
  「他的儿子马修和拉尔夫会非常想念他」→ F25 后通过（测试断言
  glossary_mismatch 不在）
- 完整文本：glossary_mismatch 消除（测试断言），换行合并仍由
  newline_mismatch 正确拦截
- 测试：test_glossary_sanitize.py +10 → 全量 1656 passed

## 观察项（模型边界，不修复）

**多行叙事文本换行合并**：1.8B 把多段文本（`\n` 分隔）译成单段——
ffs 教学文本 2 条 + 本游戏 1 条 = 第三次出现。质量门 newline_mismatch
/line_content_mismatch 正确拦截（换行丢失 = 显示结构风险），写回保留
原文安全。系统 prompt 第 9 条已要求保留换行（Hy-MT2 无 system prompt
遵循度低）。方向：待强模型升级验证，或写回侧换行结构恢复（译文按
原文行数重分——切分点不可机械确定，风险高，不引入）。
