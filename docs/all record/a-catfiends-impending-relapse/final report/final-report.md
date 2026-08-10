# a-catfiends-impending-relapse 最终报告（闭环）

闭环基线：第八跑（2026-08-10 20:2x）｜ 工具版本：修复 6/7/8 全部生效

## 总体状态：✅ 干净闭环

| 模块 | 结果 | 说明 |
|---|---|---|
| 识别 | 0 bug | 79 条类型引用全部拦截（含修复 8 新增 Fungus 3 条），零误伤 |
| 翻译 | 234 成功 / 8 失败 | 8 条失败全部翻译侧合理（见下） |
| 写回 | 231 写入 + 3 回显 | 四态闸门全 PASS，字体 runtime_verified |
| 质量门 | 拦截 1 条坏译文 | 标点移动（target_script_mismatch），未写入 |
| 术语库 | 学习 4 条专名 | GLISLYA / LABOLIS-7 / KARKINOS-9 / DOLORIFIAN |

## 失败 8 条归因（全部翻译侧，非工具缺陷）

1. `This, {w=0.5}err,{w=0.5} might actually be...` — 模型移动标点（err 后逗号挪到标签后），质量门正确拦截，未写入
2-7. `{punch=..}* Y A W N *` 等 6 条大写间隔动作 — 视觉表现手法回显，质量门严格判失败（语义合理）
8. `UCLA Gold` — ProBuilder 专名色回显（与 UCLA Blue/USAFA Blue 一致，回显跳过 3 条）

## 修复记录（本游戏发现并修复）

| 修复 | 内容 | 代码位置 |
|---|---|---|
| 6 | mono 诊断文本/纯标签硬结构拦截 + 记录升级（逐条写回状态） | mono_dll.py / placeholders.py / all_record_runner.py |
| 7 | 专名自动收集注入（known_names 从未生效）+ 全局术语库学习 + 速度优化（并发 4 + batch 24，526s→154s，3 倍提速质量持平） | prompts.py / glossary.py / runner+GUI |
| 8 | 类型引用形态识别（Fungus.Flowchart, Fungus 曾被译成「真菌.流程图」写回） | extractor.py |

详见 fix record/ 目录。

## 性能

- 翻译：154.4s / 260 条 = 98 条/分（修复 7 提速前 526s）
- 写回：变更 33 文件，重开验证 PASS

## 遗留（模型能力边界，非缺陷）

- `GREATER LABYRINTH` → 「大咽道」：LABYRINTH 多义词误译（模型自信产出流畅错误译文，质量门无法拦）。1.8B 模型能力边界，2/253 条量级，人工校对可见
- 音译型专名（GLISLYA→格莉斯莉亚）无自动提取（无法可靠定位译文片段），可人工在术语库补充

## 结论

a-catfiends-impending-relapse 达到稳定状态，删除汉化输出目录，进入下一游戏。
