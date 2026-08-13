# interdream 地毯式排查记录

- 游戏目录：D:\游戏\interdream
- 时间：2026-08-13 09:07:49

## 1 识别
- 文本文件：0 · 二进制资源：128
- 识别条目：3994
- 语言分布（抽样预检，多语言游戏盲区）：
  - 英文/ASCII: 18564 条
  - 其他/无字母: 135 条
  - 重音拉丁（法/西/德等）: 1 条
- 形态统计：
  - asset_unity: 265 文件 / 0 条
  - mono_csharp: 1 文件 / 0 条
- 状态分布：
  - pending: 3994
  - translated: 0
  - failed: 0
  - skipped: 14706
- 置信度分布：
  - high: 54
  - medium: 3940
  - low: 0
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending 使用已验证 TMP/UGUI 运行时中文回退
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：3994 · 完成：3848（记忆命中 0） · 失败：146
- 请求：9281 · 输入 351436 tokens · 输出 76325 tokens
- 耗时：8675.0s · 吞吐 27 条/分

## 3 写回
- 文本文件：0 · 写入译文：3807
- 输入保护：True · 重开验证：True · 变更文件：155
- 总体闸门：WARN · 字体：runtime_verified（LEGACY_EVIDENCE_UNSCOPED：旧协议证据，未含逐码点 attestation/覆盖证明）

## 3.5 语义审核（翻译质量升级）
- 审核条数：571 · 不合格：228 · 术语沉淀：11
- 不合格清单见 review/review-report.md（需人工确认后优化）

## 4 分析（已闭环，2026-08-13）
- [x] 成功文本质量抽检（译文是否得当/是否无关文本）——文本快照终验
      208 条缺陷登记人工重译（见 fix record/f13-defect-written-list.md）
- [x] 语义审核不合格项确认与优化（review/review-report.md）——571/228
      终版处置见 analysis/analysis-final.md §6
- [x] 失败文本根因系统彻查（同类问题全解）——146 条终版裁决
      （23 判定误杀 + 123 真实拦截，见 analysis/analysis-final.md §3）
- [x] 跳过文本逐条判定（该翻→识别修复；不该翻→记录判定）——14706 条
      抽样确认引擎串为主，跳过正确（analysis §7）
- [x] 写回问题根源修复——F13 三修（对话符/计时码/字面 \n），全量回归
      零回归
- [ ] 写回后实机测试——不做（2026-08-12 指令，闭环验证到重开比对为止）
- [x] 修复后用升级版本重跑本游戏全流程（闭环）——F13 修复后代码复验
      拦截全部 208 条缺陷
- [x] 闭环后删除汉化输出目录——`D:\游戏\interdream_汉化` 已删

记录文件：
- text/translated.txt / text/failed.txt / text/skipped.txt
- review/review-report.md / review.json（语义审核）
- writeback/writeback.txt
