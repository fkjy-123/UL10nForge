# hickory 地毯式排查记录

- 游戏目录：D:\游戏\hickory
- 时间：2026-08-13 04:56:13

## 1 识别
- 文本文件：1 · 二进制资源：2
- 识别条目：151
- 语言分布（抽样预检，多语言游戏盲区）：
  - 英文/ASCII: 1189 条
  - 其他/无字母: 33 条
- 形态统计：
  - asset_unity: 1 文件 / 0 条
  - mono_csharp: 1 文件 / 0 条
  - mono_other: 16 文件 / 0 条
- 状态分布：
  - pending: 151
  - translated: 0
  - failed: 0
  - skipped: 1071
- 置信度分布：
  - high: 78
  - medium: 73
  - low: 0
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending 使用已验证 TMP/UGUI 运行时中文回退
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：151 · 完成：148（记忆命中 1） · 失败：3
- 请求：33 · 输入 1977 tokens · 输出 618 tokens
- 耗时：42.0s · 吞吐 211 条/分

## 3 写回
- 文本文件：1 · 写入译文：120
- 输入保护：True · 重开验证：True · 变更文件：28
- 总体闸门：PASS · 字体：runtime_verified

## 3.5 语义审核（翻译质量升级）
- 审核条数：18 · 不合格：1 · 术语沉淀：0
- 不合格清单见 review/review-report.md（需人工确认后优化）

## 4 分析（待办）
- [x] 成功文本质量抽检（译文是否得当/是否无关文本）
- [x] 语义审核不合格项确认与优化（review/review-report.md）
- [x] 失败文本根因系统彻查（同类问题全解）
- [x] 跳过文本逐条判定（该翻→识别修复；不该翻→记录判定）
- [x] 写回问题根源修复
- [x] 写回后重开比对验证（免实机测试指令 2026-08-12；实机测试计划已删除）
- [x] 修复后用升级版本重跑本游戏全流程（闭环）
- [x] 闭环后删除汉化输出目录

记录文件：
- text/translated.txt / text/failed.txt / text/skipped.txt
- review/review-report.md / review.json（语义审核）
- writeback/writeback.txt
