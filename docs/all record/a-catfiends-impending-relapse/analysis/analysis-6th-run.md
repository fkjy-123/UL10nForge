# a-catfiends-impending-relapse 第六跑核查分析

运行时间：2026-08-10 19:54 ｜ 修复基线：commit 6dc7639（mono 诊断拦截 / 纯标签硬结构 / 记录升级）

## 1. 总览

| 指标 | 数值 | 结论 |
|---|---|---|
| 提取条目 | 1595（含 skipped） | 池子全量 |
| 成功翻译 | 253 | 逐条核查 |
| 写回写入 | 247 | 无 rejected，无未写入 |
| 回显跳过（译文==原文） | 6 | 与 writeback 清单全对账 ✓ |
| 失败 | 7 | 全部翻译侧，识别侧 0 bug |
| 文件 | 7（level0/level1/resources/sharedassets1/Cinemachine.dll/Unity.ProBuilder.dll/app.info） | 四态闸门全 PASS |

## 2. 成功文本逐条核查

- 逐条含：来源/键位/对象（组件类型）/原文/译文/置信度/原因/角色/质量评分/翻译评价/需要优化/写回状态 ✓
- 247 条「写回：已写入」与 writeback.txt「写入译文：247」完全一致
- 6 条回显逐条在 writeback.txt 列明（2×Fungus.Flowchart 标签 + LYNCH + 2×ProBuilder 颜色名）
- 抽样质量：对话译文自然（「你已不再是从前那个你了。」），Fungus 标签 `{w=3}{x}` 全部原位保留 ✓

## 3. 失败文本归因（7 条）

| # | 原文 | 失败原因 | 判定 |
|---|---|---|---|
| 1-4,6 | `{punch=..}* Y A W N *{w=3}{x}` 等大写间隔动作 | untranslated_text | 合理：大写间隔是视觉表现手法（Y A W N 逐字拉伸），翻译破坏节奏。质量门判定「失败」是严格的（语义上应放行） |
| 5 | `* S I G H *{w=3}{x}` | placeholder_mismatch | 模型把标签移动成 `*S I G H* * {w=3}{x}`，质量门正确拦截 ✓ |
| 7 | `UCLA Gold` | untranslated_text | 合理：专名色，ProBuilder 颜色表条目 |

7 条全部是翻译侧（模型行为），工具侧无 bug。识别侧 0 bug（对比前几跑）。

## 4. skipped 抽查（诊断/标签拦截效果）

- ProBuilder.dll：诊断/日志词拦截后 pending 10→3（编辑器 DLL 测试日志不再进池）
- Poly2Tri.dll：5→0
- Fungus.dll：10→0
- Cinemachine.dll 保留 2 条（SOLO、**ANY CAMERA** 为真实 UI，验证非误伤）
- skipped 总计 1342 条（编码词/结构文本/诊断串），抽样未发现该翻未翻

## 5. 发现的新问题（进入修复 7）

**专名误译 2 条（第六跑唯一残余质量问题）**：

1. `YOU ARE INVESTIGATING BACTERIAL PHENOMENA DEEP WITHIN THE VACUUM CAVERNS OF THE GREATER LABYRINTH` → 「您正在深入调查**大咽部**的真空洞穴中发生的细菌现象」——LABYRINTH（迷宫）被模型误译成解剖词「咽部」，且专名 GREATER LABYRINTH 丢失
2. `GLISLYA SPECIALIST FROM THE ACADEMY OF CORRADAILE` → 「来自科拉达莱学院的专业讲师」——GLISLYA（种族/地名专名）丢失

**根因（工具侧）**：`build_system_prompt` 的 `known_names` 参数（【已确认专名·全游戏保持一致】注入段）**从未被任何调用方传入**——自动专名收集从未实现，术语段从未生效。

**修复（见 fix record/fix-07-known-names.md）**：`collect_known_names` 自动收集全大写词典外词注入 prompt。

**边界**：GREATER LABYRINTH→咽部属多义词误译（模型自信产出流畅错误译文），质量门无法拦（非回显/非占位符问题）；专名注入可救 GLISLYA 类丢失，多义词误译属 1.8B 模型能力边界，2/253 条可接受。
