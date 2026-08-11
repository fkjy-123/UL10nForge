# ffs-full-game-demo 修复记录（术语污染事故 + F23 方向检查）

## 事故：术语表污染全局误杀 2077 条（2026-08-12 重跑实证）

**触发链**：ffs 完整重跑（验证 il2cpp 清单持久化）翻译阶段失败 2083
条——99.7%（2077）是 `glossary_mismatch`。抽查译文质量高（
`Right Tilt→右侧倾斜`、`pick the right door→正确的门`），属误杀。

**根因（数据污染）**：审核沉淀形态 2 用「原文首词」当术语 source——
第 1 轮审核建议「Left Paddle 译为左拨片」「Left Stick Button 应译为
左摇杆按钮」「Right 被误译为正确」等十几条不同语境建议，全被提取成
单词对（Left→左摇杆按钮、Right→右拨片、Stick→操纵杆右、Throttle→
油门苦力帽向右、Wheel→方向盘按钮6…），写进全局术语库强制所有游戏
所有文本。普通文本 right=正确的/右边，译文不可能含「右拨片」→ 误杀。

**污染规模**：20 条词对（ffs 第 1 轮 14 + faerie 10 重叠），target 多为
审核建议残渣（含方向字/数字：换挡器6/旋钮模式1/油门苦力帽向右）。

**修复三端（系统性，防再生）**：
1. **沉淀端**（reviewer.py `extract_term_pairs`）：
   - 形态 2（纯中文建议）：source 用整个短原文（≤5 词无标点）→ 组合
     词对（Left Paddle→左拨片）精确匹配；长原文/含标点丢弃
   - 形态 1：source 限 ≤5 词（防完整建议句提取）
   - 建议前缀剥除（译为/应译为…）+ 中英文引号统一
2. **数据清洗**：glossary.db 删除 20 条污染词对（195 条剩余）
3. **判定端**（quality.py）：**F23 方向语义检查**——输入绑定语境（原文
   含设备词 stick/button/hat/pov/switch/trigger/shoulder/wheel/throttle/
   dial/shifter/paddle/pedal/lever/knob 或键位后缀 `:xxx`）+ 原文含方向
   词（left/right/up/down）+ 译文有中文 → 译文必须含对应方向字
   （左/右/上/下）；缺失 → direction_mismatch 失败。兜住删除术语后
   的真错（`Hat Right→正确`、`POV Down-Right→视角：下方` 丢方向）。

**实证**：2083 条失败样本 × 新判定 → 通过 1971（94.6%），仍失败 112
全部为真错（方向译错 98 + 回显 11 + 换行 3）。测试 20 条固化 +
全量 1646 passed。

**防再犯**：
- 沉淀端防再生（首词提取禁止）
- 方向词单字对永不入库（来源必然是语境建议）
- 审核沉淀词对 target 含方向字/数字 = 语境残渣信号

## 附带：恢复流程二次实证

重跑写回成功后库被清理（keep_library=False 默认）→ 补翻前库不存在
（`no such table: entries`）。恢复路径（faerie 先例二次实证）：
scan_all 重建 → 导出解析 → 新质量门验证导入（6998 条，通过=导入
translated，失败=留 pending）→ 补翻 pending 976 → 写回。

## 观察项（模型边界，不修复）

1. 方向组合文本（Left Hat Up-Left 类）1.8B 译「左帽抬起-左」——方向
   字在但苦力帽语义不达；direction_mismatch 拦截后保留原文（安全）
2. 教学文本 `Observe the spelling…` 多行换行 mismatch——译文丢失换行
   结构，写回前需保留原文换行（2 条）
3. `C Right`/`C Left` 回显——孤立按键缩写，保留原文（安全）
