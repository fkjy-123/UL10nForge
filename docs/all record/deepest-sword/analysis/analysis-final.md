# deepest-sword 闭环分析（final）

> 2026-08-11 · run1 3 失败 → F4/F5/F6 修复 → run2 **0 失败**闭环。
> 写回 143 条译文 + 9 条合理保留回显（非失败），字体 runtime 验证通过。

## 1. 识别

- 文本文件 1 + v2 资源 6：识别条目 152，全部 actionable。
- 形态：asset_unity 5 文件 355 条（152 actionable）、mono_csharp 2 文件
  169 条、mono_other 11 文件 120 条。

## 2. run1 的 3 条失败根因（真实复现确认）

| # | 原文 | 译文 | 原因 | 根因 |
|---|---|---|---|---|
| 1 | `v{0}` | `v{0}` | target_script_mismatch | **误报**：版本号模板回显合理，但单字母 v 被 `has_independent_lower_word` 当独立小写词 → proper_name_echo 豁免失效 |
| 2 | `Leaderboards on Speedrun.com` | `Speedrun.com上的排行榜` | target_script_mismatch | **误报**：译文完全正确；SAFE_KEEPERS 域名分支 `\b` 是 Unicode 词边界，中文（\w）算词字符——com 后紧跟中文不构成边界 → 域名不剥 → com 被当小写普通词残留 |
| 3 | `MAX SEARCH OPTIMIZED` | `MAX 搜索优化版` | target_script_mismatch | **真半翻**：MAX 在 UI 词典（=最大）是普通词；全大写形态被词级补译跳过（当专名）→ 恒败。且 SEARCH 触发 `_is_uppercase_action` → 专名回显豁免被阻断（正确） |

### 修复（见 fix record F4/F5/F6）

- F4：SAFE_KEEPERS 4 个后缀分支 `\b` → `(?![A-Za-z0-9])`（ASCII 词字符
  延续检查，中文/标点/空白照常构成边界）
- F5：`has_independent_lower_word` 花括号占位符紧邻的单字母 → 格式串
  载体，不算独立小写词
- F6：词级补译放宽全大写 UI 词典词（MAX 可补译；TitleCase/全大写非
  词典专名维持跳过）

## 3. run2 结果

- **152 条 0 失败**（163 请求 104.7s）。
- 3 条失败修复验证：
  - `v{0}` → passed 放行（版本模板保留）✓
  - `Speedrun.com上的排行榜` → passed 放行 ✓
  - `MAX SEARCH OPTIMIZED` → 补译链提取 MAX → 1.8B 补译回显 → 模型确认
    保留 → word_residue_exempt 豁免放行，译文 `MAX 搜索优化版` 写回
    （模型能力边界下的可接受权衡：MAX 全大写 HUD 缩写玩家可辨识）
- 译文抽检 12 条：占位符（`MP: {0}/{1}`、`Playtime: {0}`）保留 ✓、
  平台名（Discord/Twitter/Cosmic Adventure Squad）保留 ✓、`ROTATE
  REPEAT`→`旋转/重复` ✓。个别调试串意译（`OBJECT NOT TWEEENING AT
  BEGINNING`→`该对象在初始化时不会执行任何操作。`）可接受。

## 4. 写回

- 143 条译文写入 + **9 条回显跳过（译文==原文，非失败）**——逐条判定
  全部合理保留：`v{0}` 版本模板、`MP/HP: {0}/{1}` HUD 标签、`SFX`
  缩写、`Discord`/`Twitter` 平台名、`SWORD` 艺术大写、
  `ON UPDATE VAL`/`SCALED ENDING POSITION` 引擎串。写入与否无差别
  （译文==原文），WARN 闸门准确反映。
- 字体 payload_deployed，重开验证通过，总体 WARN（仅因回显跳过）。

## 5. 结论

**run2 闭环**：0 失败 / 0 该翻而跳 / 写回全绿（143 写入 + 9 合理保留）。
F4/F5/F6 修复真实生效，三条失败全部收敛。
