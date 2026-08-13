# headache 地毯式排查记录

- 游戏目录：D:\游戏\headache
- 时间：2026-08-12 23:13:29（第三轮：fix-30/31 键名提示误杀链修复后）
- 状态：**闭环通过**（第三轮 194 完成 / 5 失败全为正确拦截，
  final report/final-report.md）

## 1 识别
- 文本文件：2 · 二进制资源：9
- 识别条目：721
- 语言分布（抽样预检，多语言游戏盲区）：
  - 英文/ASCII: 3311 条
  - 其他/无字母: 34 条
  - 日语: 2 条
  - 中文: 2 条
- 形态统计：
  - asset_unity: 12 文件 / 0 条
  - il2cpp_metadata: 1 文件 / 0 条
- 状态分布：
  - pending: 721
  - translated: 0
  - failed: 0
  - skipped: 2629
- 置信度分布：
  - high: 109
  - medium: 90
  - low: 522
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending IL2CPP 使用静态字体替换：legacy Font 内嵌 TTF / TMP_FontAsset 版本化 bundle 替换（写回阶段执行）
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：199 · 完成：194（记忆命中 5） · 失败：5
- 请求：76 · 输入 3193 tokens · 输出 736 tokens
- 耗时：72.4s · 吞吐 161 条/分

## 3 写回
- 文本文件：2 · 写入译文：175
- 输入保护：True · 重开验证：True · 变更文件：10
- 总体闸门：PASS · 字体：runtime_verified（LEGACY_EVIDENCE_UNSCOPED：旧协议证据，未含逐码点 attestation/覆盖证明）

## 4 分析（闭环）
- [x] 成功文本质量抽检（译文是否得当/是否无关文本）——第三轮 194 完成
- [x] 语义审核不合格项确认与优化——用户指令：本轮不做云端语义审核（--no-review）
- [x] 失败文本根因系统彻查——9→5 收敛：press space ×5 词对污染、press e ×2 引号缺失（fix-30/31）；剩余 5 条全为正确拦截（模型丢键名输出×4 + VOLUME 半翻译×1）
- [x] 跳过文本逐条判定——2629 跳过：TMP 资产对象整对象（fix-31 新）、词表/输入轴名、引擎串/键标识
- [x] 写回问题根源修复——输入保护/重开验证 PASS
- [x] 写回后实机测试——用户指令：本轮不做实机测试
- [x] 修复后用升级版本重跑本游戏全流程（闭环）——第三轮 194/5
- [ ] 闭环后删除汉化输出目录

记录文件：
- text/translated.txt / text/failed.txt / text/skipped.txt
- review/review-report.md / review.json（语义审核）
- writeback/writeback.txt
