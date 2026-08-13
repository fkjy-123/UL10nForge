# 汉化助手 · 工具介绍词（供 UI 重做 Agent 的上下文入口）

> 用途：其他 Agent 生成 UI 重做计划前，先读本文件建立工具全貌；
> 详细产品重定位与视觉规范见《汉化助手 UI-UX 与产品体验重构设计规范》。

## 1. 一句话定位

**本地优先的 Unity 游戏智能汉化流水线**：检测 → 扫描 → 工具交叉验证 →
深度翻译（本地大模型）→ 语义审核 → 安全写回，全程离线、质量门可解释、
术语沉淀跨游戏复用。

## 2. 技术栈与架构

- **UI**：PySide6（Qt for Python），单窗口多页面（QStackedWidget 导航）
- **核心**：`hanhua/core/` —— 纯逻辑、零 UI 依赖，可被 headless runner
  独立驱动（scripts/all_record_runner.py）
- **推理**：本地 llama.cpp 四模型服务
  | 模型 | 用途 | 端口 |
  |---|---|---|
  | Hy-MT2-1.8B-Q6_K | 翻译 | 8080 |
  | Qwen3.5-4B-Q4_K_M | 语义审核（--reasoning off） | 8081 |
  | Qwen3-Reranker | 相似召回 | 8082 |
  | Qwen3-Embedding | 向量检索 | 8083 |
- **数据**：SQLite（项目 store / glossary 术语库 / agent_memory 经验记忆 /
  knowledge 知识库 / context_library 语境库）
- **页面协作**：AppState（QObject）信号——projectOpened / entriesChanged /
  analysisChanged / pipelinePhase / settingsChanged

## 3. 五步流水线与页面映射

| 阶段 | 说明 | 对应页面 |
|---|---|---|
| 1 游戏检测 | Unity 运行时识别（Mono/IL2CPP）、player 布局证据 | 首页工作台 |
| 2 文本扫描 | UnityPy/dnfile/metadata 结构化提取 | 首页工作台 |
| 3 自动工具分析 | Il2CppDumper 等外部工具交叉验证（缓存/置信度/耗时） | 首页工作台 |
| 4 翻译质量 | 深度翻译 + 五维质量门（占位符/标签/术语/语言/控制字符） | 翻译页 + 文本审校 |
| 5 写回验证 | 原生 locator、staging、重开验证、原子提交、输入哈希保护 | 翻译页 |

页面构成：**首页工作台**（拖放接入、统计卡、健康度评分、任务推荐、五步
rail 实时状态）→ **文本审校**（三栏：列表筛选 / 精修 / 语境+AI 审核面板）
→ **翻译页**（批量翻译、实时进度/日志/停止/重试、安全写回）→ **设置**
（API、术语表管理、字体、审核策略）。

## 4. 质量体系（UI 重做不得破坏）

- **测试门禁**：2057 用例全绿（基线硬门槛，UI 改动零回归）
- **质量门**：翻译/审核/写回共用 `validate_translation_quality`；
  术语词对带上下文保护——**只有组合词对可全局强制**，单 token 高频词
  （miss/right/locked…）拒绝沉淀或仅参考注入
- **审核沉淀闭环**：语义审核 → 术语词对 C5 门禁 → 跨游戏复用；
  审核结论落 store meta（审校页「需要优化」筛选）
- **多级记忆**：工作记忆（会话级）/ 经验记忆 AgentMemory（跨游戏、
  证据驱动、参考而非强制）/ 语境库（同游戏同指纹直填）/ 知识库（特殊情况模式）
- **失败审计**：翻译失败/写回失败自动导出 docs/fail record，全流程可复盘

## 5. UI 现状与已知痛点（2026-08-13 实证，重做计划应覆盖）

- ✅ 五步流水线 rail 已实时（扫描事件 + pipelinePhase 信号广播）
- ✅ 翻译进度已实时刷新首页分数（≥1s 节流广播 entriesChanged）
- ✅ 审校页选中映射已修正（proxy mapToSource）、reload 保留选中、
  AI 面板无判定时有降级提示
- ⚠️ 语义审核期间 Windows 会弹出瞬间终端窗口（审核链路 subprocess
  缺 CREATE_NO_WINDOW，修复中）
- ⚠️ 首页健康度「翻译完成」分母用文本总数（含 skipped/failed），
  应改为待翻译总数口径（修复中）
- 产品方向：从「工程工具/后台管理」升级为「专业 AI 游戏本地化工作台」
  （详见重设计规范）

## 6. UI 重做硬约束

1. `hanhua/core/` 不得因 UI 改动改变行为（headless runner 与 GUI 同源）
2. 零新增第三方依赖（纯 PySide6）
3. 不做实机游戏测试（2026-08-12 指令）——一切行为以测试为准
4. 术语对必须带上下文保护（全局强制仅限组合词对）
5. UI 与 core 经 AppState 信号/页面回调协作，不直接 import core 内部
6. push 远端仅在用户明确要求时执行（本地提交不受限）
