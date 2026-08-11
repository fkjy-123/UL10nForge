# eyeless-jack 分析报告（终版）

## 概览

| 项 | 值 |
|---|---|
| 游戏 | eyeless-jack（无眼杰克，生存恐怖，Assembly-CSharp + 资源） |
| 目录 | D:\游戏\eyeless-jack |
| 闭环轮次 | run1（2026-08-12 01:07，2 失败）→ run2（2026-08-12 01:14，1 失败） |
| 识别条目 | 194（asset_unity 691 / mono_csharp 88，跳过 587） |
| 翻译 | 193 / 194（Hy-MT2-1.8B-Q6_K，49.2s，235 条/分） |
| 写回 | 193 条 · 48 文件变更 · container/object PASS · 字体 runtime_verified |

## 失败收敛过程

| 轮次 | 失败数 | 失败文本 | 处置 |
|---|---|---|---|
| run1 | 2 | `MUSIC: Tim_Kulig_Free_Music, Brotheration_Records…` 致谢名单（4 条）；`Look in the mirror` | F20 修复致谢名单误杀 |
| run2 | 1 | `Look in the mirror`（回显，确定性） | 记录观察项（模型能力边界） |

## 失败分类（run2 终版）

1. **`Look in the mirror`（1 条，确定性回显）**：
   - 现象：两轮运行均回显原文，质量门 untranslated_text 正确拦截
   - 根因：1.8B 模型对无上下文短完整句（4 词祈使句）保守回显——
     与 driftapocalypse/eggs 观察一致，属模型能力边界，非判定规则误杀
   - 证据：run1/run2 结果逐字相同 → 该温度与采样下确定性，重跑无收益
   - 处置：**不修复**。无通用规则可表达「这种短句必须译出」而不误伤
     大量合法回显（专名/UI 词/标题）；原文保真写回原值，无逻辑风险。
     记录为观察项，随模型升级自然消解。

## F20 修复内容（本次闭环代码变更）

**问题**：Pixabay 音乐致谢名单 `MUSIC: Tim_Kulig_Free_Music, Brotheration_Records, Eremit_der_Schatten`
（资产 4 条）——用户名各段被当作普通英文词误杀（`Tim`/`Kulig`/`Free` 等全
非词典词），质量门报 untranslated_text。

**修复**（batch_translator.py，三处接入）：
- 收集：正则 `[A-Za-z]+(?:_[A-Za-z]+)+` 匹配原文，各段入
  `underscore_identifier_words` 集合（下划线连接是标识符/用户名/文件名的
  形态特征——真实英文句子用空格，不用下划线）
- 短语分支 + 单词循环各加一段豁免：`word.casefold() in underscore_identifier_words → continue`

**判定依据**：译文保留用户名是正确行为（用户名/文件名不是可翻译文本），
与既有 proper_name_echo（纯 TitleCase 专名回显豁免）对齐。

## 正确性复核

- run2 新增 1 条译文：MUSIC 致谢名单由失败转成功（F20 直接证据）✓
- 未发现「下划线豁免掩盖真半翻译」：对照用例
  `Open the file`（无下划线，正常半译）仍失败 → 豁免严格限定
  在下划线形态内 ✓
- 回显跳过 587 条（UnityEngine 类型引用/输入轴/按钮枚举/日志），
  无该翻而跳 ✓
- 写回：输入保护 ✓ 重开验证 ✓ 原子提交 ✓ revert 0 ✓

## 结论

**已闭环**。193/194 翻译写回；唯一失败 `Look in the mirror` 为确定性
模型能力边界（原文保真、无逻辑风险），按观察项记录不修复。本轮交付
F20 下划线标识符组成部分豁免修复，通过 run2 全流程实证。
