# doog-hololive-fangame 地毯式排查记录

- 游戏目录：D:\游戏\doog-hololive-fangame
- 时间：2026-08-11 19:59:08

## 1 识别
- 文本文件：1 · 二进制资源：4
- 识别条目：2651
- 形态统计：
  - asset_unity: 22 文件 / 2271 条
  - il2cpp_metadata: 1 文件 / 3150 条
- 状态分布：
  - pending: 2651
  - translated: 0
  - failed: 0
  - skipped: 2772
- 置信度分布：
  - high: 172
  - medium: 1043
  - low: 1436
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending IL2CPP 使用静态字体替换：legacy Font 内嵌 TTF / TMP_FontAsset 版本化 bundle 替换（写回阶段执行）
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：1215 · 完成：1194（记忆命中 0） · 失败：21
- 请求：1210 · 输入 45304 tokens · 输出 10224 tokens
- 耗时：526.6s · 吞吐 136 条/分

## 3 写回
- 文本文件：1 · 写入译文：1109
- 输入保护：True · 重开验证：True · 变更文件：4
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
