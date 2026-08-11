# eyeless-jack 修复记录

> 闭环轮次：run1（2 失败）→ run2（1 失败）· 193 翻译 / 1 失败 / 193 写回
>
> 本轮代码修复：**F20 下划线标识符组成部分豁免**——Pixabay 音乐
> 作者用户名致谢名单误杀（eyeless-jack 实证暴露）。

## F20：下划线标识符组成部分豁免

- **触发**：`MUSIC: Tim_Kulig_Free_Music, Brotheration_Records,
  Eremit_der_Schatten`（资产致谢名单 4 条）——用户名各段被当普通
  英文词，质量门 untranslated_text 误杀
- **形态**：下划线连接（`_`）是标识符/用户名/文件名的形态特征；
  真实英文句子用空格。`[A-Za-z]+(?:_[A-Za-z]+)+` 匹配原文收集各段
  入 `underscore_identifier_words`
- **接入**（hanhua/core/batch_translator.py）：
  - 收集：`_ENGLISH_WORD.findall` 展开下划线匹配组（约 2023-2031 行）
  - 短语分支豁免（约 2102-2104 行）
  - 单词循环豁免（约 2193-2195 行）
- **判定依据**：译文保留用户名是正确行为——用户名/文件名非翻译对象，
  与 proper_name_echo（纯 TitleCase 专名回显豁免）同一原则
- **防过宽**：豁免严格限定下划线形态——`Open the file`（无下划线）
  正常半翻译仍失败（对照测试覆盖）✓
- **测试**：tests/test_batch_translator.py
  - `test_underscore_identifier_words_allowed`（Tim_Kulig_Free_Music
    保留 → 合法）
  - `test_underscore_identifier_does_not_mask_real_half_translation`
    （`Open the file` 仍失败 → 不掩盖真半翻译）
  - 全量回归：test_batch_translator.py 225 passed
- **实证**：run2 MUSIC 致谢名单 4 条由失败转成功（+1 条译文总量），
  无新增失败 ✓

## 观察项（不修复，记录判断依据）

1. **`Look in the mirror` 回显（1 条，确定性）**：run1/run2 逐字相同
   回显 → 该温度与采样下确定性失败。1.8B 模型对无上下文短完整句
   （4 词祈使句）保守回显，属**模型能力边界**而非判定误杀：
   - 无通用规则可表达「这类短句必须译出」而不误伤大量合法回显
     （专名/UI 词/标题，与 F18/F19 豁免范围重叠）
   - 原文保真写回原值，玩家可见英文原句，无逻辑/崩溃风险
   - 记录为观察项，随模型升级（≥7B）自然消解；届时重跑本游戏验证
2. **字体 runtime_verified（PASS）**：本游戏静态字体替换命中（内嵌
   字体对象可替换），与 eggs-for-bart 的 payload_deployed（WARN）形
   成对照——32 位老游戏两路径皆已验证，无代码问题
