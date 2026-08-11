# deepest-sword fix record

> 2026-08-11 · run1 3 失败 → F4/F5/F6 修复 → run2 0 失败闭环。

## 历程

| 轮次 | 结果 | 说明 |
|---|---|---|
| run1 | 3 失败（149 成功） | v{0} 误报 / Speedrun.com 误报 / MAX 真半翻 |
| run2 | **0 失败（152 成功）** | F4/F5/F6 修复后一次通过 |

## 本场代码修复

### F4：SAFE_KEEPERS 后缀边界 \b → ASCII lookahead（`hanhua/core/placeholders.py`）

- **现象**：`Leaderboards on Speedrun.com` → `Speedrun.com上的排行榜`
  （译文完全正确）被 target_script_mismatch 拒。
- **根因**：Python re 的 `\b` 是 Unicode 词边界，中文（\w）算词字符——
  `com` 后紧跟中文「上的排行榜」时 `\b` 不成立 → SAFE_KEEPERS 域名分支
  不剥 → com 当小写普通词残留误判。
- **修复**：域名/小写用户名/版本号/文件扩展名 4 个后缀分支的 `\b` 全部
  改为 `(?![A-Za-z0-9])`（只排除 ASCII 词字符继续拼接——comedy 的 com
  后接字母仍不剥；中文/标点/空白照常构成边界）。
- **影响面**：'Speedrun.com上的…'、'itch.io页面'、'0.4.0beta说明'、
  'SPOLOUS.exe游戏' 等译文中最常见的中文紧邻形态全部修复。

### F5：has_independent_lower_word 花括号单字母豁免（`hanhua/core/quality.py`）

- **现象**：`v{0}`（版本号模板）回显被判 target_script_mismatch。
- **根因**：单字母 v 被当独立小写词 → proper_name_echo（原文与译文字母
  序列相同=专名/载体回显豁免）失效。
- **修复**：单字母小写 + 前后紧邻 `{`/`}`（格式串载体）→ 不算独立
  小写词。'v{0}'、'{0}v' 修复；'hello world'（普通词）、"Playtime's"
  （撇号属格）行为不变。

### F6：词级补译放宽全大写 UI 词典词（`hanhua/core/batch_translator.py`）

- **现象**：`MAX SEARCH OPTIMIZED` → `MAX 搜索优化版` 恒败（MAX 半翻）。
- **根因**：词级补译只处理纯小写词（`w[0].islower() and not w.isupper()`）
  ——全大写形态被当专名跳过；但 MAX 在 UI 词典（=最大）是普通语义词，
  且 SEARCH 触发 `_is_uppercase_action` → 专名回显豁免被正确阻断 →
  补译也不处理 → 死锁。
- **修复**：补译条件放宽——纯小写普通词 或 全大写+UI 词典词（MAX/ON/OFF
  类）可补译；TitleCase（Gamejolt）与全大写非词典词维持跳过。
- **实测**：run2 补译链生效——模型对 MAX 补译回显（1.8B 能力边界）→
  确认保留 → word_residue_exempt 豁免放行，0 失败收敛。

### F7（本场顺带）：runner 结束清理只删本游戏 slug 目录（`scripts/all_record_runner.py`）

- **现象**：death-trips 闭环时 sweep 库清理 WinError 32（project.db 被占用）。
- **根因**：`_discard_sweep_library` 删 `project.app_dir`（整个
  `~/.hanhua_sweep`）而非本游戏 slug 目录——双游戏并行时删除并行
  runner 正在使用的工作区（代码注释已记录 crash/crusty 实证，实现与
  注释矛盾）。
- **修复**：改为删 `store.db` 的父目录（本游戏 slug 目录），与启动
  清理目标一致。

## 测试

- 新增 4 个回归测试：SAFE_KEEPERS 中文紧邻后缀剥除（F4）、版本模板
  单字母豁免（F5）、全大写词典词补译 + 全大写非词典专名对照（F6）。
- 全量 1537 passed 无回归。

## 沉淀

- 知识库 fail_case：v{0} 版本模板回显、Speedrun.com 域名中文紧邻、
  MAX 全大写词典词半翻（见 knowledge 沉淀记录）。
- 无哑信号：跳过 494 条均为结构/类型引用（type_reference 等），
  已由识别器结构性判定。
