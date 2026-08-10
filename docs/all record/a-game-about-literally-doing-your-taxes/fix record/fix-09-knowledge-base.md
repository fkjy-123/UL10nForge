# fix-09 知识库全链路（特殊文本 → 质量门 → 学习 → 译例注入）

游戏：a-game-about-literally-doing-your-taxes（闭环于 2026-08-10）

## 背景

taxes 的 `TOSS TRASH` 条目标记「该翻未翻」：模型回显原文（或被当专名豁免）。
前八轮反复失败，根因链复杂：

1. 全大写动作指令（TOSS TRASH）无小写词、不在 UI 词典 → 被 proper_name_echo
   当专名豁免 → 回显放行
2. 模型输出半翻译「TOSS 垃圾」（保留动作动词 TOSS）→ 质量门对「有中文」
   的译文不判失败 → 放行
3. 降级重试走 native_translate（Hy-MT2 无 system prompt 契约）→ 知识库规则
   进不去 → 重试仍失败
4. 术语库 learn_proper_names 把 TOSS 学成专名（TOSS → TOSS 保留映射）→
   与译例冲突，模型采纳「TOSS 是专名」→ 半翻译

## 修复（全部通用机制，无单游戏特判）

| # | 内容 | 文件 |
|---|---|---|
| 1 | **知识库创建**：多形态分库（text 文本形态 / file 文件知识 / rule 抽象规则），内置种子规则 + SQLite 持久库（domain/kind/pattern/action/map_to/note/hits，幂等 upsert） | `hanhua/core/knowledge.py`（新建） |
| 2 | **质量门 special_action**：全大写动作指令（含动作动词）与间隔动作词回显一律判失败，不再依赖小写词/UI 词典判断 | `quality.py` |
| 3 | **质量门 action_word_residue**：译文残留原动作动词（TOSS 垃圾）判失败 | `quality.py` |
| 4 | **learn 沉淀**：跑完从「该翻未翻」条目（回显 + 动作残留拒绝）自动入库；uppercase_action 用动作词表机械直译生成 map_to（TOSS TRASH → 丢垃圾） | `knowledge.py` |
| 5 | **译例注入 references**：knowledge 精确对照并入 glossary → native_translate 的 terms 机制带出「TOSS TRASH translates to 丢垃圾」 | `knowledge.py` / runner / GUI |
| 6 | **prompt 注入**：`build_system_prompt` 加 knowledge_lines 块（特殊情况规则优先遵守） | `prompts.py` / runner / GUI |
| 7 | **单行 repair 保护**：chat 版 multiline 修复只对真多行条目生效，单行失败落到 native 降级（带译例）——原实现把单行条目标记 segmented_attempts 后不再重试 | `batch_translator.py` |
| 8 | **learn_proper_names 排除动作动词**：TOSS 不学成专名（与译例冲突的根因） | `glossary.py` |
| 9 | **备份清理可靠化**：写回清理线程同步 join 等待（CLI 退出不再杀线程）+ runner 闭环删 `_汉化` 目录与全部 backup（做完一个删一个） | `project.py` / `all_record_runner.py` |

## 验证

- taxes 最终跑：**96 条翻译 0 失败，全部写回**（此前 2 条 TOSS TRASH 卡死）
- TOSS TRASH → **丢垃圾**（完整链路：质量门拒绝 → learn 沉淀 map_to → references
  译例 → native 输出 → 质量门通过）
- 术语库清理误学条目 TOSS（保留映射与译例冲突）
- 全量测试 1438 通过（新增 test_knowledge.py 20 条 + quality/writeback 断言更新）
- D:/游戏 残留清空：17 个 backup（各 353MB）+ 1 个 `_汉化` 目录全部删除，释放约 6GB

## 遗留（模型能力边界）

- `RESUME` → 「摘要」（应为「继续」，UI 按钮语义）：1.8B 多义词流畅误译，
  质量门无法拦，人工校对可见
- `TAXES DONE` → 「已缴纳的税款」（应为「税务办理完毕」）：同上
