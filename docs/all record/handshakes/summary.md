# handshakes 地毯式排查记录

- 游戏目录：D:\游戏\handshakes
- 时间：2026-08-12 22:18:07

## 1 识别
- 文本文件：1 · 二进制资源：7
- 识别条目：192
- 语言分布（抽样预检，多语言游戏盲区）：
  - 英文/ASCII: 1323 条
  - 其他/无字母: 24 条
- 形态统计：
  - asset_unity: 3 文件 / 0 条
  - mono_csharp: 1 文件 / 0 条
  - mono_other: 23 文件 / 0 条
- 状态分布：
  - pending: 192
  - translated: 0
  - failed: 0
  - skipped: 1159
- 置信度分布：
  - high: 184
  - medium: 8
  - low: 0
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending 使用已验证 TMP/UGUI 运行时中文回退
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：192 · 完成：191（记忆命中 0） · 失败：1
- 请求：113 · 输入 3999 tokens · 输出 720 tokens
- 耗时：96.2s · 吞吐 119 条/分

## 3 写回
- 文本文件：1 · 写入译文：186
- 输入保护：True · 重开验证：True · 变更文件：34
- 总体闸门：PASS · 字体：runtime_verified（LEGACY_EVIDENCE_UNSCOPED：旧协议证据，未含逐码点 attestation/覆盖证明）

## 4 分析（闭环）
- [x] 失败文本根因系统彻查（1 条 eegnrs 乱序串，评估为开发残留不修，见 fix record/fix-none-eegnrs-scrap-string-eval.md）
- [x] 跳过文本逐条判定（1159 条全部判定合理，无该翻未翻）
- [x] 闭环后删除汉化输出目录（已清理，仅保留原版）
- [x] 成功文本质量抽检（final report/final-report.md）
- [x] 修复后用升级版本重跑本游戏全流程（第一轮即闭环，无需重跑）
- [ ] 语义审核不合格项确认与优化（免实测免审核流程，--no-review）
- [ ] 写回问题根源修复（写回 PASS 正常，无遗留）
- [ ] 写回后实机测试（用户指令免实机测试）

记录文件：
- text/translated.txt / text/failed.txt / text/skipped.txt
- review/review-report.md / review.json（语义审核）
- writeback/writeback.txt
- fix record/fix-none-eegnrs-scrap-string-eval.md（失败项评估）
- final report/final-report.md（闭环最终报告）
