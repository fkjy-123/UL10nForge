# foxhunt-chapter1 闭环最终报告

## 结果

| 阶段 | 结果 |
|---|---|
| 识别 | 633 条目（233 pending / 400 skipped）· 5 文件（1 文本 + 4 二进制） |
| 翻译 | **232 完成 · 失败 1**（173 请求 · 145.3s · 96 条/分） |
| 写回 | **WARN** · 231 条译文 · 31 变更文件 · 重开验证 True · 字体 payload_deployed |
| 质量 | 抽检得当（菜单词族 CONTINUE/OPTIONS/EXIT/QUIT 全对；专名 SunCubes/FoxHunt 保留） |
| 跳过 | 400 条全部判定合理（引擎串/调试日志/音效触发名/Input 轴名），无「该翻未翻」 |

## 失败与处置

- **RESUME → 摘要**（builtin_ui_mismatch，1 条）：单条模型误译。
  同语境 CONTINUE→继续 翻译正确，无同类失败 → **不修复**，记观察项
  （详见 fix record/fix-none-resume-mistranslation-eval.md）。
  若后续游戏复现同族 UI 菜单词误译，升级为强制词对修复。

## 跳过审查（400 条按原因全量判定）

| 原因 | 条数 | 判定 |
|---|---|---|
| prefilter_high_frequency | 169 | ✅ 合理——主体是 `UnityEngine.UI.MaskableGraphic+CullStateChangedEvent, ...` 引擎串（同一串被百余对象引用） |
| prefilter_engine_string | 85 | ✅ 合理——引擎串（EleventhClue 等线索 ID） |
| unverified_user_string | 50 | ✅ 合理——引擎资产串（PostFX/Shaders/Motion Blur）+ Debug.Log 调试输出（Got one/Time:/cubes active）+ Input 轴名（Mouse X），无真实 UI 文本 |
| prefilter_key_identifier | 42 | ✅ 合理——thunk1/shaker1/click2 音效触发名 |
| identifier_without_display_evidence | 17 | ✅ 合理——ESC 等无显示证据短串 |
| hard_structural / engine_core / code_identifier | 各 10 | ✅ 合理——路径/引擎查找键/代码标识 |
| localization_key_list | 6 | ✅ 合理——wind/poof/clue 音效名与线索 ID |

## 写回审计

- 8 条逻辑键 report（CONTINUE/OPTIONS/EXIT/QUIT → 继续/选项/退出）——
  **全部翻译正确**，仅 report 提示复核，无回退。
- rawstr 扩容写入 116 条（UTF-8 字节 > 原文）——原生容量对齐路径，fit_bytes
  已处理 NUL/占位符保护。
- 回显跳过 1 条（[ESC] 译文==原文，未写入）。
- runtime=WARN：字体运行时层警告（payload_deployed 已部署），非失败。

## 验证方式

- 全量测试 1872 passed（本轮无代码变更）
- 写回重开验证 True · 输入保护 True
- translated.txt 抽检 + skipped.txt 全量来源审计 + writeback.txt 逻辑层审计

## 遗留

无。游戏闭环，`foxhunt-chapter1_汉化` 已清理，仅保留原版。

## 知识库

无新案例。RESUME→继续 观察项待跨游戏证据（见 fix record）。
