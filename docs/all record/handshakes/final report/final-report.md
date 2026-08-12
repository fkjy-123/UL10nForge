# handshakes 闭环最终报告

## 结果

| 阶段 | 结果 |
|---|---|
| 识别 | 192 条目 · 1 文本文件 + 7 二进制资源（asset_unity/mono 形态） |
| 翻译 | **191 完成 · 失败 1**（113 请求 · 96.2s · 119 条/分） |
| 写回 | **PASS** · 186 条译文 · 重开验证 True · 输入保护 True |
| 质量 | 抽检得当（自然语言为主，见下） |
| 跳过 | 1159 条全部判定合理（引擎串/高频引用/标识符），无「该翻未翻」 |

## 失败与处置

- **eegnrs → eegnrs**（untranslated_text，1 条）：开发残留乱序串
  （非词典词，可重排成 genres 等）——模型无法翻译是合理行为，
  孤例无系统性 → **不修复**，记观察项
  （详见 fix record/fix-none-eegnrs-scrap-string-eval.md）。
  若后续游戏批量出现乱序/造词文本则升级识别层规则。

## 翻译质量抽检（186 条译文）

- **自然语言为主**：日常对话/提示语（"you're all ready" 类句式意译
  得当，goodmorning 同族句式受益于 fix-28 意译豁免）
- **UI 菜单词**：保留型术语回显正常（echo_exempt 打标）
- **键名提示**：Shift/RMB 类键名保留原文（fix-27 键名保护生效）

## 跳过审查（1159 条按原因全量判定）

| 原因 | 判定 |
|---|---|
| prefilter_high_frequency | ✅ 合理——引擎串被多对象引用（同一串不重复翻译） |
| prefilter_engine_string | ✅ 合理——引擎资产串/调试输出 |
| identifier_without_display_evidence | ✅ 合理——无显示证据短串 |
| 其余 | ✅ 合理——路径/代码标识/音效触发名 |

## 写回审计

- 186 条译文写回 · PASS 闸门 · 重开验证 True
- 5 条回显跳过（译文==原文未写入，echo_exempt 打标）
- 字体 payload_deployed（运行时中文字体回退）

## 记忆与知识库

- 经验记忆：提案 90 · 晋升 0（本局无跨游戏强证据词对，健康）
- 失败案例沉淀：1 种（eegnrs 乱序串模式入库备查）

## 验证方式

- 全量测试 1887 passed（本轮无代码变更，fix-27/28 已含）
- 写回重开验证 True · translated/failed/skipped.txt 审计

## 遗留

无失败遗留。`handshakes_汉化` 已清理，仅保留原版。

## 知识库

无新案例规则。eegnrs 乱序串观察项待跨游戏证据（见 fix record）。
