# 222am 地毯式排查记录

- 游戏目录：D:\游戏\222am
- 时间：2026-08-11 16:29:36

## 1 识别
- 文本文件：1 · 二进制资源：5
- 识别条目：66
- 形态统计：
  - asset_unity: 67 文件 / 16 条
  - mono_csharp: 2 文件 / 135 条
  - mono_unityscript: 2 文件 / 21 条
- 状态分布：
  - pending: 66
  - translated: 0
  - failed: 0
  - skipped: 211
- 置信度分布：
  - high: 7
  - medium: 59
  - low: 0
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending 使用已验证 TMP/UGUI 运行时中文回退
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：66 · 完成：66（记忆命中 0） · 失败：0
- 请求：62 · 输入 2143 tokens · 输出 499 tokens
- 耗时：29.1s · 吞吐 136 条/分

## 3 写回
- 文本文件：1 · 写入译文：66
- 输入保护：True · 重开验证：True · 变更文件：32
- 总体闸门：WARN · 字体：payload_deployed

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
