# RESUME：重启后给 Agent 的接手指令

> 2026-08-11 创建。重启新会话后，把本文件全文作为指令发给 agent
> （或让 agent 先读本文件）。同步读 `docs/地毯式排查升级计划.md`
> （§0.4 知识库体系、§0.5 双游戏并行、§0.6 当前进度）。

---

**Unity 汉化工具：知识库体系搭建（第一优先）→ 地毯式排查双游戏并行（0.25.0）**

我是项目负责人。请先读计划文档 `C:\Users\mingming\Desktop\AI项目\unity游戏汉化工具\docs\地毯式排查升级计划.md`（§0.4 知识库体系搭建、§0.5 双游戏并行、§0.6 当前进度），项目根在 `C:\Users\mingming\Desktop\AI项目\unity游戏汉化工具`，全部中文交流。

**第一阶段（第一优先，必须完成后再进入第二阶段）：知识库体系搭建**

按 `C:\Users\mingming\Desktop\新建 文本文档.txt` 的六库方案搭建（Unity结构库/失败案例库/文本类型规则库/组件兼容库/翻译质量库/写回验证库）。现状核查：只有 `~/.hanhua/knowledge.db`（knowledge_items 单表，domain=text 25 条译例 / fail_case 88 条模式串）+ glossary.db，对照六库仅失败案例库部分存在（结构不符，缺游戏/环境/根因/影响范围/修复版本字段），其余 4 库没有。实施步骤：
1. 扩展现有 knowledge.db 按 domain 分库（不另起炉灶）：`unity_structure`（kind: unity_version/resource_type/text_location/detect_method/extract_plan/known_issue）、`fail_case`（note 升级为结构化 JSON：game/env/issue/phenomenon/root_cause/solution/impact/fixed_version，保留 pattern/hits）、`text`（增强 kind: ui_text/dialogue/skill/equipment/achievement/system_msg/debug/param/code + note 含优先级/要求）、`component_compat`（kind: text/textmeshpro/dropdown/ui_toolkit/rewired/input_system…）、`quality`（kind: scoring_case/term_consistency/common_error）、`writeback`（kind: writeback_case/test_flow）——接口用 `hanhua/core/knowledge.py` 的 KnowledgeStore.upsert/list
2. 迁移现有 88 条 fail_case + 25 条 text 到新结构（不丢 pattern/hits）
3. 种子数据从 docs 五份指南提取：Unity游戏文本位置与提取全景指南/Unity文本识别与提取资料大全/写回资料大全/写回调查报告/本地模型游戏翻译质量与游戏性保障指南 + 识别形态清单（asset_unity/mono_csharp 等）+ 质量门规则
4. 查询接口（按 domain/kind 查询 + 命中统计；format_reference_pairs 继续注入 text 域译例）
5. runner 闭环接入：record_case 登记完整字段、写回记录自动登记 writeback 域、每游戏登记 unity_structure（Unity 版本/形态）
6. 验证：CLI 查询测试 + 完成定义（六库可查询、种子就位、闭环沉淀生效）——写 `docs/知识库体系.md` 记录架构

**第二阶段（知识库建完后启动）：地毯式排查双游戏并行**

对 `D:\游戏` 下 ~120 款 Unity 游戏逐个闭环（识别/翻译/写回），**始终同时并行跑两个独立游戏**（各自独立 runner 进程/项目库 `~/.hanhua_sweep/projects/<slug>`/日志/记录目录，共享 10500 llama-server）。每款游戏：逐条验证失败 → 根因 → 修复（代码+测试）→ 重跑至 failed=0 → 三件文档（analysis/analysis-final.md、fix record/、final report/final-report.md）→ 删 `<游戏>_汉化` 只留原版 → 知识库沉淀。断点续作：deadbeat run2 剩 30 失败（根因已定位见计划 §0.6：slash 解释垃圾×10 / miss 回显×8 / 歌词中文源误放行重大 bug / DeAD\nbEAt / encore 1 / 歌词分块尾部回显），6 项修复已设计未实现（中文源收紧 CJK≥2 且占字母≥50%、_artistic_case_echo 逐行化、词级补译解释模式拦截、multiline 行级回显豁免、_glossary_keep_echo、encore 空格标签）；222am 仅剩 hiss pop collection。两者闭环后进下一对（death-trips + deepest-sword）。

**硬性约束**：中文回复；中途别停别问直接做；本地提交仅当有 commit 价值（push 只在收尾 0.25.0 时做，用户明确要求）；禁止临时补丁/单游戏特判/硬编码；python 调用加 PYTHONUTF8=1 PYTHONIOENCODING=utf-8；知识库升级持续进行不能忘；模型服务复用（llama-server 10500，API key 从 `Get-CimInstance Win32_Process` 查 llama-server.exe 命令行取）。全部游戏闭环后：版本跳 0.25.0、重写 README、本地提交、push 远端。
