# hunt 修复记录（2026-08-13）

## 本游戏无代码修复（74 条 0 失败 0 写回问题）

全局 F 系列修复（F4~F7）沿用生效，本游戏为**首对零修复闭环**：
hunt 74 条翻译 0 失败、72 条写回 PASS（字体 runtime_verified）、
审核 11 条真实判定。

## 观察项登记（不在本游戏特判）

1. **4B 审核弱误判实证**（2/11 = 18%，高于 honorplusplus 的 ~8%）：
   - e5 `(PRESS SPACE TO PLAY)` → 「按空格键开始」被指「应使用播放」——
     原文 PLAY 在游戏启动按钮语境 = 开始，译文正确，审核按字面挑错
   - e64 `What do you bitches want?` → 「你们这些贱人想要什么？」被指
     「应使用混蛋」——译文「贱人」准确传达原文性别指向侮辱（bitches），
     审核给出的「正确译文」与译文等价
   - 结论：4B 审核误判集中在「术语字面对应」与「语气词选择」两类，
     均为低危噪声；真问题（截断续写/否定/漏译）仍能准确拦截。
     审核报告的不合格清单需人工裁决（流程已有「需人工确认」标注）
2. **经验记忆实证**：提案 26 · 晋升 1 · 直接应用 4（采纳 4 / 拒绝 0）·
   退休 0——记忆门禁工作正常（与 goodmorning 的 28/28 实证一致）

## 关联修复

- 扁平布局 Mono 识别（F8，hotel-paradise 实证，本游戏不受影响）：
  老 Unity standalone/WebGL 导出 Data 散根目录、无 *_Data 宿主 →
  `_detect_mono_architecture` 兼认 `game_dir/Managed`。见
  `docs/all record/hotel-paradise/fix record/fix-record.md`
