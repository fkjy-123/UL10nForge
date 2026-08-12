# fix-30/31 键名提示误杀链修复（headache 实证 2026-08-12）

## 现象与根因链

headache 第二轮 192 完成 9 失败。失败原因优先级链（input_token_mismatch
→ key_name_mistranslated → glossary_mismatch → action_word_residue）
逐层暴露问题——每修一层，同一译文暴露下一层误杀：

| 失败（第二轮） | 根因 | 修复 |
|---|---|---|
| PRESS SPACE TO CONTINUE/RESTART ×5 「按空格键以继续」 | (SPACE→空间) 词对污染：happy-cat-tavern 的 UI 词 Space→空间 learn 沉淀 active，fix-27 词对豁免只覆盖 _KEY_LABEL_CASEFOLD（强制表），space 因有中文通称「空格」被排除出强制表 → 词对豁免漏网，译文「按空格键」被判 glossary_mismatch | **fix-31**：词对豁免扩到 PHYSICAL_KEY_NAMES_CASEFOLD 全键名集 |
| PRESS E TO INTERACT. ×2「点击"PRESS E"以进行互动」 | action_word_residue 无引号豁免——引号内短语在原文出现是模型引用 UI 提示原文（untranslated_text 分支已有 quoted_terms 豁免，两处不一致是缺陷） | **fix-31**：剥离引号内容后检查引号外残留（引号外双写仍拦） |
| RMB TO PICK UP THE HAMMER ×1「拿起锤子」 | 键名丢失真失败（无 RMB/右键） | 不修（拦截正确，fix-30 判定） |
| VOLUME: ×1「VOLUME：音量」 | 半翻译模型行为 | 不修（观察项） |

fix-30（先于 fix-31 提交）：键名中文通称豁免表（space→空格、escape→
esc/退出键、rmb→右键…）——input_token_mismatch 与 key_name_mistranslated
两处检查豁免；escape 从键名强制表排除（兼作普通词「逃跑」）。

## 污染数据清理（agent_memory.db）

退休 6 条（保留审计痕迹）：
- (SPACE→空间) id=1184 active 7 证据——**误杀主犯**
- (Space→空间) id=1501 active 2 证据——happy-cat-tavern learn 源头
- 「媒体 X」机器垃圾译文 4 条（PRESS SPACE TO CONTINUE→媒体 SPACE
  继续、PRESS E TO INTERACT→媒体 E 进行互动 ×2、PRESS BTN→媒体
  BTN）——PRESS→「媒体」语义错译通过形态质量门被沉淀

## 直填表防线（batch_translator）

`_glossary_exact` 直填表过滤键名 source：原文 "SPACE" 精确命中不再
直填「空间」（词对虽退休，历史 active 期间已应用的路径加防御）。

## 验证（第三轮）

- 失败 9 → 5；**PRESS SPACE ×5 误杀全部消除**（glossary_mismatch
  失败清零）
- 剩余 5 条全部为质量门**正确拦截**（非误杀）：
  - 「按交互」×2：模型第三轮输出漂移（丢了 E 键名）→ input_token_mismatch
  - 「用锤子敲打玻璃」「拿起锤子」×2：RMB 键名丢失真失败
  - VOLUME 半翻译 ×1：观察项
- 全量回归 1907 passed

## 测试

- tests/test_f31_glossary_key_alias.py（6 测试）：SPACE 词对不再误杀、
  SHIFT 回归、RMB→人民币 仍拦、引号 PRESS E 放行、无引号残留仍拦、
  引号外双写仍拦
- tests/test_f31_tmp_asset.py（4 测试）：TMP 资产对象跳过（详见
  fix-31 提交，TMP 资产名是 <font>/<sprite> 引用键）
- tests/test_f30_key_zh_alias.py（6 测试，fix-30）
