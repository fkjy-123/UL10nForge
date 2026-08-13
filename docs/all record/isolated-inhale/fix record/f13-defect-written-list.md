# isolated-inhale F13 修复前已写回缺陷译文清单（终版）

> 生成：2026-08-13 · isolated-inhale 全流程闭环后
> 数据源：runner 导出 text/translated.txt（写回最终值，项目库已按惯例清理）
> 复验：F13 修复后代码（F13a 对话词对豁免 + F13b 字面 \n 行首 `* `保护 + F13c 裸 ^NN 保护）
> 数量：1 条（写回最终值复验）
> 处置：登记人工重译（本游戏特判，不自动回写）
> 对照：翻译运行中快照 → 终版 1 条（全量覆盖）

## 拦截原因分布
- `('newline_mismatch', 'line_content_mismatch')`: 1

## 清单
### 1. asset#resources.assets#1371/json/LBL_NO_CHIPS  ('newline_mismatch', 'line_content_mismatch')
- 原文：'<Key>Nessun chip disponibile!</>\nInserisci nuovi chips a lato per ripristinare.'
- 写回：'<Key>没有可用的芯片！</>请插入新的芯片以恢复功能。'