# hickory 地毯式排查记录

- 游戏目录：D:\游戏\hickory
- 时间：2026-08-14 00:46:16

## 1 识别
- 文本文件：（续跑，见上轮 summary.md） · 二进制资源：（续跑，见上轮 summary.md）
- 识别条目：1114
- 语言分布（抽样预检，多语言游戏盲区）：
  - 英文/ASCII: 1051 条
  - 其他/无字母: 65 条
- 形态统计：
- 状态分布：
  - pending: 0
  - translated: 348
  - failed: 0
  - skipped: 766
- 置信度分布：
- 工具状态：
- 阻断步骤：

## 2 翻译
- 总条目：1116 · 完成：348（记忆命中 0） · 失败：0
- 请求：0 · 输入 0 tokens · 输出 0 tokens
- 耗时：0.0s · 吞吐 0 条/分

## 3 写回
- 文本文件：1 · 写入译文：311
- 输入保护：True · 重开验证：True · 变更文件：2
- 总体闸门：PASS · 字体：runtime_verified
- 字体发布门：PASS — 覆盖 COVERED：6 个消费者完整，0 个未覆盖，缺字 0 个码点

## 4 分析（待办）
- [ ] 成功文本质量抽检（译文是否得当/是否无关文本）
- [ ] 语义审核不合格项确认与优化（review/review-report.md）
- [ ] 失败文本根因系统彻查（同类问题全解）
- [ ] 跳过文本逐条判定（该翻→识别修复；不该翻→记录判定）
- [ ] 写回问题根源修复
- [ ] 修复后用升级版本重跑本游戏全流程（闭环）
- [ ] 闭环后删除汉化输出目录

记录文件：
- text/translated.txt / text/failed.txt / text/skipped.txt
- review/review-report.md / review.json（语义审核）
- writeback/writeback.txt
