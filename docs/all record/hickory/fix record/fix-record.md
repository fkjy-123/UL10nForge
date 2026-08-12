# hickory 修复记录（2026-08-13）

## 全局 F 系列修复（与 honorplusplus 共用，代码层已落地）

- **F4 审核链路治本**（probe 带 Bearer key + `_clear_stale_review_port`
  杀 8081 孤儿实例）：本游戏实证——此前 3 次重跑审核恒 0 判定，
  F4 后第 4 次重跑 **18 条真实判定**（不合格 1）。详见
  `docs/all record/honorplusplus/fix record/fix-record.md`
- F5 runner 输出 GBK 崩溃（UTF-8 reconfigure）
- F6 审核模型名展示（SemanticReviewer.model_name）
- F7 质量门中置「翻译为」解释句式拦截

## 本游戏新发现（登记待办，不在本游戏特判）

### 待办 B1：glossary_mismatch 误伤拟声词（失败 2/3）

- **现象**：`What – clk – happening…` → `什么——clk——正在发生……`
  被判 glossary_mismatch 失败。译文本身正确（`clk` 是时钟 tick
  拟声词，保留原文合理）
- **根因**：glossary 强制词对把 `clk` 或相邻词命中为应替换词，
  译文保留原文 → 误判「术语未替换」
- **待决**：拟声词/保留词的 glossary 豁免规则（与 honorplusplus 待办
  A2 回显豁免同族：**保留≠漏译**），待多游戏样本交叉后统一修

### 质量门正确拦截实证（成功案例）

- `Resume` → `简历`：**真实错误**（游戏菜单语境 Resume = 继续，
  不是简历）。builtin_ui_mismatch 正确拦截，失败清单记录，未写回
- 审核正确拦截：e6 多句长文本只译一句（`So much chaos! Desolo and
  Benjamin pulled through like always. Jonathan saw for loops in
  Daniel's shaders. ...` → 只输出中间一句）——信息不完整，审核
  拦截正确
