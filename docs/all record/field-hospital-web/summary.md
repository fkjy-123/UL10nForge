# field-hospital-web 地毯式排查记录

- 游戏目录：D:\游戏\field-hospital-web
- 时间：2026-08-12 14:10:11

## 1 识别
- 文本文件：1 · 二进制资源：4
- 识别条目：403
- 语言分布（抽样预检，多语言游戏盲区）：
  - 英文/ASCII: 640 条
  - 其他/无字母: 81 条
- 形态统计：
  - asset_unity: 3 文件 / 663 条
  - mono_csharp: 1 文件 / 56 条
- 状态分布：
  - pending: 403
  - translated: 0
  - failed: 0
  - skipped: 318
- 置信度分布：
  - high: 65
  - medium: 338
  - low: 0
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending 使用已验证 TMP/UGUI 运行时中文回退
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：403 · 完成：402（记忆命中 0） · 失败：1
- 请求：294 · 输入 12565 tokens · 输出 4932 tokens
- 耗时：235.1s · 吞吐 103 条/分

## 3 写回
- 文本文件：1 · 写入译文：400
- 输入保护：True · 重开验证：True · 变更文件：31
- 总体闸门：PASS · 字体：runtime_verified

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
