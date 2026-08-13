# ffs-full-game-demo 地毯式排查记录

- 游戏目录：D:\游戏\ffs-full-game-demo
- 时间：2026-08-12 14:03:01

## 1 识别
- 文本文件：（续跑，见上轮 summary.md） · 二进制资源：（续跑，见上轮 summary.md）
- 识别条目：11373
- 语言分布（抽样预检，多语言游戏盲区）：
  - 英文/ASCII: 11359 条
  - 日语: 5 条
  - 其他/无字母: 5 条
  - 中文: 4 条
- 形态统计：
- 状态分布：
  - pending: 769
  - translated: 7135
  - failed: 70
  - skipped: 3399
- 置信度分布：
- 工具状态：
- 阻断步骤：

## 2 翻译
- 总条目：11373 · 完成：7135（记忆命中 0） · 失败：70
- 请求：0 · 输入 0 tokens · 输出 0 tokens
- 耗时：0.0s · 吞吐 0 条/分

## 3 写回
- 文本文件：1 · 写入译文：6333
- 输入保护：True · 重开验证：True · 变更文件：19
- 总体闸门：PASS · 字体：runtime_verified（LEGACY_EVIDENCE_UNSCOPED：旧协议证据，未含逐码点 attestation/覆盖证明）

## 4 分析（待办）
- [ ] 成功文本质量抽检（译文是否得当/是否无关文本）
- [ ] 语义审核不合格项确认与优化（review/review-report.md）
- [ ] 失败文本根因系统彻查（同类问题全解）
- [ ] 跳过文本逐条判定（该翻→识别修复；不该翻→记录判定）
- [ ] 写回问题根源修复
- [ ] 写回后实机测试（按实机测试计划逐项验证）
- [ ] 修复后用升级版本重跑本游戏全流程（闭环）
- [ ] 闭环后删除汉化输出目录

记录文件：
- text/translated.txt / text/failed.txt / text/skipped.txt
- review/review-report.md / review.json（语义审核）
- writeback/writeback.txt
