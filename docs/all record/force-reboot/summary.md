# force-reboot 地毯式排查记录

- 游戏目录：D:\游戏\force-reboot
- 时间：2026-08-12 22:05:35

## 1 识别
- 文本文件：2 · 二进制资源：4
- 识别条目：401
- 语言分布（抽样预检，多语言游戏盲区）：
  - 英文/ASCII: 4112 条
  - 其他/无字母: 53 条
  - 重音拉丁（法/西/德等）: 2 条
  - 俄语/西里尔: 1 条
- 形态统计：
  - asset_unity: 1 文件 / 0 条
  - mono_csharp: 1 文件 / 0 条
  - mono_other: 11 文件 / 0 条
- 状态分布：
  - pending: 401
  - translated: 0
  - failed: 0
  - skipped: 3771
- 置信度分布：
  - high: 326
  - medium: 75
  - low: 0
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending 使用已验证 TMP/UGUI 运行时中文回退
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：401 · 完成：401（记忆命中 0） · 失败：0
- 请求：52 · 输入 1795 tokens · 输出 253 tokens
- 耗时：35.5s · 吞吐 677 条/分

## 3 写回
- 文本文件：2 · 写入译文：375
- 输入保护：True · 重开验证：True · 变更文件：32
- 总体闸门：WARN · 字体：runtime_verified（LEGACY_EVIDENCE_UNSCOPED：旧协议证据，未含逐码点 attestation/覆盖证明）

## 4 分析（闭环）
- [x] 失败文本根因系统彻查（三轮修复见 fix record/fix-24-25-26-force-reboot-triple-round.md）
- [x] 修复后用升级版本重跑本游戏全流程（第四轮 26 失败 → **0**，闭环）
- [x] 闭环后删除汉化输出目录（已清理，仅保留原版）
- [x] 成功文本质量抽检（final report/final-report.md）
- [x] 跳过文本逐条判定（3771 条全部判定合理：词库型 TextAsset 整文件跳过 144 + 引擎串/高频引用）
- [ ] 语义审核不合格项确认与优化（免实测免审核流程，--no-review）
- [ ] 写回问题根源修复（写回 PASS/WARN 正常，无遗留）
- [ ] 写回后实机测试（用户指令免实机测试）

记录文件：
- text/translated.txt / text/failed.txt / text/skipped.txt
- review/review-report.md / review.json（语义审核）
- writeback/writeback.txt
- fix record/fix-24-25-26-force-reboot-triple-round.md（三轮修复记录）
- final report/final-report.md（闭环最终报告）
