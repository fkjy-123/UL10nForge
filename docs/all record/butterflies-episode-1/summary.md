# butterflies-episode-1 地毯式排查记录

- 游戏目录：D:\游戏\butterflies-episode-1
- 时间：2026-08-11 02:30:15

## 1 识别
- 文本文件：3 · 二进制资源：9
- 识别条目：2065
- 形态统计：
  - asset_unity: 15 文件 / 2245 条
  - mono_csharp: 2 文件 / 141 条
  - mono_other: 1 文件 / 0 条
- 状态分布：
  - pending: 2065
  - translated: 0
  - failed: 0
  - skipped: 2904
- 置信度分布：
  - high: 184
  - medium: 1881
  - low: 0
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending 使用已验证 TMP/UGUI 运行时中文回退
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：2065 · 完成：2065（记忆命中 0） · 失败：0
- 请求：768 · 输入 25534 tokens · 输出 4875 tokens
- 耗时：431.9s · 吞吐 287 条/分

## 3 写回
- 文本文件：3 · 写入译文：1880
- 输入保护：True · 重开验证：True · 变更文件：38
- 总体闸门：PASS · 字体：runtime_verified

## 4 分析（待办）
- [ ] 成功文本质量抽检（译文是否得当/是否无关文本）
- [ ] 失败文本根因系统彻查（同类问题全解）
- [ ] 跳过文本逐条判定（该翻→识别修复；不该翻→记录判定）
- [ ] 写回问题根源修复
- [ ] 修复后用升级版本重跑本游戏全流程（闭环）
- [ ] 闭环后删除汉化输出目录

记录文件：
- text/translated.txt / text/failed.txt / text/skipped.txt
- writeback/writeback.txt
