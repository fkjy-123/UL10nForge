# isolated-inhale 地毯式排查记录

- 游戏目录：D:\游戏\isolated-inhale
- 时间：2026-08-13 12:48:55

## 1 识别
- 文本文件：1 · 二进制资源：7
- 识别条目：10031
- 语言分布（抽样预检，多语言游戏盲区）：
  - 英文/ASCII: 16912 条
  - 重音拉丁（法/西/德等）: 1107 条
  - 中文: 523 条
  - 俄语/西里尔: 483 条
  - 其他/无字母: 188 条
- 形态统计：
  - asset_unity: 5 文件 / 0 条
  - mono_csharp: 1 文件 / 0 条
  - mono_other: 25 文件 / 2 条
- 状态分布：
  - pending: 10031
  - translated: 0
  - failed: 0
  - skipped: 9184
- 置信度分布：
  - high: 1264
  - medium: 8767
  - low: 0
- 工具状态：
  - bmfont: verified
  - il2cpp_dumper: verified
- 阻断步骤：
  - translation_quality: pending 占位符、标签、术语、语言与控制字符验证
  - font: pending 使用已验证 TMP/UGUI 运行时中文回退
  - writeback: pending 使用原生 locator、staging、重开验证与原子提交

## 2 翻译
- 总条目：10031 · 完成：9892（记忆命中 3） · 失败：139
- 请求：6137 · 输入 254746 tokens · 输出 52514 tokens
- 耗时：6234.3s · 吞吐 95 条/分

## 3 写回
- 文本文件：1 · 写入译文：9147
- 输入保护：True · 重开验证：True · 变更文件：34
- 总体闸门：PASS · 字体：runtime_verified（LEGACY_EVIDENCE_UNSCOPED：旧协议证据，未含逐码点 attestation/覆盖证明）

## 3.5 语义审核（翻译质量升级）
- 审核条数：1372 · 不合格：432 · 术语沉淀：88
- 不合格清单见 review/review-report.md（需人工确认后优化）

## 4 分析（已闭环，2026-08-13）
- [x] 成功文本质量抽检（译文是否得当/是否无关文本）——9147 写回复验
      仅 1 条缺陷（0.01%，8 款最低）
- [x] 语义审核不合格项确认与优化（review/review-report.md）——1372/432
      终版处置见 analysis/analysis-final.md §4
- [x] 失败文本根因系统彻查（同类问题全解）——139 条终版裁决
      （58 判定误杀 + 81 真实拦截，见 analysis §2）
- [x] 跳过文本逐条判定（该翻→识别修复；不该翻→记录判定）——9184 条
      抽样确认；多语言盲区（中/俄语未入翻）登记观察项（analysis §5）
- [x] 写回问题根源修复——本轮无新修复（F13 等既有修复验证轮）
- [x] 修复后用升级版本重跑本游戏全流程（闭环）——终验复验拦截 1 条
- [x] 闭环后删除汉化输出目录——`D:\游戏\isolated-inhale_汉化` 已删

记录文件：
- text/translated.txt / text/failed.txt / text/skipped.txt
- review/review-report.md / review.json（语义审核）
- writeback/writeback.txt
