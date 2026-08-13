# alisa-demo 地毯式排查记录

- 游戏目录：D:\游戏\alisa-demo
- 时间：2026-08-10 23:44:45

## 1 识别
- 文本文件：1 · 二进制资源：9
- 识别条目：818
- 形态统计：
  - asset_unity: 40 文件 / 901 条
  - mono_csharp: 1 文件 / 205 条
- 状态分布：
  - pending: 818
  - translated: 0
  - failed: 0
  - skipped: 290
- 置信度分布：
  - high: 63
  - medium: 755
  - low: 0
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending Unity Mono 游戏结构不完整：需要同名 *_Data/Managed/UnityEngine.CoreModule.dll
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：818 · 完成：818（记忆命中 0） · 失败：0
- 请求：903 · 输入 33091 tokens · 输出 7653 tokens
- 耗时：468.0s · 吞吐 105 条/分

## 3 写回
- 文本文件：1 · 写入译文：787
- 输入保护：True · 重开验证：True · 变更文件：13
- 总体闸门：PASS · 字体：runtime_verified（LEGACY_EVIDENCE_UNSCOPED：旧协议证据，未含逐码点 attestation/覆盖证明）

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
