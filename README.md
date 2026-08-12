# 汉化助手 — Unity 游戏本地化工具

面向 Unity 游戏的本地化工具：**扫描识别 → 批量翻译 → 质量检查 → 安全写回 → 经验积累**。主力翻译为本地小模型（Hy-MT2-1.8B，llama.cpp 运行，完全离线），配套术语库、翻译记忆、20+ 项确定性质量检查与经验记忆模块。项目目标不是「用更强模型翻得更好」，而是**让各组件各司其职**：规则保证结构安全，记忆保证一致性，模型负责语义翻译，审核负责质量把关。

> 说明：本项目在 `D:\游戏` 目录的 118 款游戏中做过识别审计、40+ 款完成过全流程闭环（扫描→翻译→写回→重开验证）。这些是实测样本，不等于对所有 Unity 游戏通用。具体已验证范围见「能力边界」。

---

## 功能与验证状态

| 功能 | 说明 | 验证状态 |
|---|---|---|
| 文本来源覆盖 | 本地化文件（JSON/CSV/TSV/XML/TXT/INI）、TextAsset（含老 Unity 4.x/5.x str 字段）、MonoBehaviour 序列化字符串、Addressables bundle（Unity Localization 表）、Mono #US 堆、IL2CPP global-metadata.dat（v24~v39） | 各来源均有端到端实测游戏 |
| 批量翻译 | 游戏档案 + 术语表 + 翻译记忆 + 相邻上下文注入；翻译后经质量门过滤 | 40+ 游戏闭环使用 |
| 质量检查 | 20+ 确定性硬规则（占位符/富文本标签/数字/键名/词对/格式模板）+ 失败原因分类 + 定向重译 | 1900+ 单元测试覆盖 |
| 安全写回 | 仅写回「质量通过 + 置信度合格」条目；文件/容器/对象/运行时四态校验 + 重开验证 + 原子发布 | 各来源端到端实测 |
| 经验记忆 | AgentMemory：跨游戏短语记忆，证据驱动晋升，被拒降级退休 | 已上线，跨游戏复用有实证 |
| 知识库 | 六域知识库（unity_structure / fail_case / text / component_compat / quality / writeback），106+ 种子案例 | 已上线 |
| 语义审核 | 强模型五维审核（术语/语境/专名/语义/风格）基础设施 | 已建成，runner 默认关闭（--no-review），**未接入生产流程** |
| 深度审核分级 | PASS / MINOR / MAJOR / CRITICAL 四级 + Qwen3-4B 语义审核 | **规划中**，见实施计划 |
| 向量检索 | Embedding / Reranker | **规划中**，见实施计划 |

## 使用（Windows）

```bash
# 完整发行包：解压后双击根目录「启动汉化助手.bat」（包内自带 Python 3.12.10 与 llama.cpp 运行时）

# 开发环境
pip install -r requirements.txt
python main.py
```

流程：设置页选翻译后端（在线 API / 本地 Hy-MT2）→ 拖入游戏文件夹 → 五阶段工作台（检测 → 扫描 → 分析 → 翻译 → 写回）→ 写回成功后「开始游戏」启动汉化副本。

命令行排查（免界面全流程 + 全环节记录）：

```bash
python scripts/all_record_runner.py "D:\游戏\<游戏目录>" --no-review
# 输出：docs/all record/<游戏>/（summary.md + text/ + writeback/）
```

## 质量保障体系

翻译流程：`检索 → 翻译 → 检查 → 筛选 → 修正 → 记忆`（「深审」环节规划中，见下）。

### 1. 硬规则检查（确定性，优先于 AI）

质量门对每条译文执行 20+ 项检查，失败即拦截，不进入翻译池：

- **结构安全**：占位符（`{player}` / `%s` / `{0}`）、富文本标签（`<color>` / `<b>` / `<size>`）、换行、数字、控制字符
- **键名保护**：物理键名（RMB/Shift/Esc/SPACE…）强制保留或中文通称豁免（空格=space、esc=escape、右键=rmb）——按键提示译掉键名玩家找不到键
- **词对防污染**：glossary 词对子串命中需标签语境（TIME→时间 不误杀 "time to"→是时候）；键名词对全豁免
- **动作词残留**：TOSS TRASH→「TOSS 垃圾」半翻译判失败重译；引号内 UI 原文引用豁免
- **对象级跳过**：词表对象（打字游戏单词库）、TMP 字体/精灵资产、输入绑定路径、引擎配置——翻译即破坏玩法/断引用，跳过不译

### 2. 失败原因分类与定向重译

失败原因优先级链（input_token → key_name → glossary → action_word → untranslated）逐层暴露问题、逐层修复；attempt 预算跨轮共享，耗尽不再重跑同链。

### 3. 审核（现状 + 规划）

**现状**：质量门为「通过 / 不通过 + 原因」二值判定；语义审核基础设施（`hanhua/core/reviewer.py` 的 `SemanticReviewer`，强模型五维审核）已建成但默认关闭。

**规划**：PASS / MINOR / MAJOR / CRITICAL 四级审核 + 风险分流 + Qwen3-4B 深度审核 + 反馈式重译。详见 `docs/翻译质量保障系统实施计划.md`。

### 4. 经验记忆（AgentMemory）

跨游戏自动学习的离散知识单元：只收质量门通过且非回显的译文 → 多次一致证据晋升 active → 高置信直接应用（仍过质量门复查）、一般置信注入 prompt → 被拒绝的记忆降级直至退休。语境冲突可审计（memory-report.md）。

### 5. 排查实证（历史记录）

`D:\游戏` 全量游戏按计划双游戏并行排查（`docs/地毯式排查升级计划.md`）：40+ 游戏完成闭环，多数最终 0 失败（部分经过多轮修复收敛）；每轮暴露的系统性问题以模块级修复解决（fix-16 ~ fix-31），不按游戏打补丁，全部修复有回归测试。

## 已验证文本来源

| 来源 | 提取 | 写回 |
|---|---|---|
| 本地化文件（JSON/CSV/TSV/XML/TXT/INI） | ✅ | ✅ 保留编码与换行策略 |
| TextAsset（含老 Unity 4.x/5.x str 字段） | ✅ | ✅ 可变长重建 + 重开验证 |
| MonoBehaviour 序列化字符串 | ✅ | ✅ 对象级重开验证 + 逻辑键 revert 防线 |
| Addressables bundle（Unity Localization 表） | ✅ | ✅ 按 Entry ID 写回 + catalog CRC 同步 |
| Mono 程序集（C# #US 堆） | ✅ | ✅ 固定容量写回，超长截断报告 |
| IL2CPP global-metadata.dat | ✅ 原生 + Il2CppDumper 交叉验证 | ✅ 全池重开比对（v24~v39） |

AssetBundle/SerializedFile 重建写回；Mono #US 与 IL2CPP 池受原容量限制。未知 runtime/版本显示 blocked，不假报成功。

## 能力边界（实测范围，非承诺）

- **样本范围**：识别审计覆盖 `D:\游戏` 118 款；全流程闭环 40+ 款。样本覆盖不等于所有 Unity 游戏通用
- **IL2CPP**：metadata 写回验证过 v24/27/29/31/39，cosl（v31）、minato（v39）端到端闭环
- **老 Unity（4.x/5.x）**：WebFile 容器、str 类型 TextAsset 已验证；`.fnt` 位图字体游戏被正确阻断而非假报成功
- **不可汉化**：运行时拼接/加密文本、服务器下发文本、贴图内文字（需 OCR，超范围）
- **字体**：Windows x64 Mono 自动注入思源黑体；IL2CPP/x86 不在字体运行时范围内（即使能提取也不保证显示）
- **语义错译**：形态完整但语义错的译文（如 PRESS→「媒体」）质量门形态上无法拦截——依赖语义审核（规划中）与记忆门禁（坏译文不沉淀）
- **未见实机验证**：按现行流程，闭环验证到「写回 + 重开比对」为止，不做游戏内实机测试

## 技术架构

```
hanhua/
├── core/                  # 解析/翻译/存储/写回（与 UI 解耦）
│   ├── unity/             # UnityPy / dnfile / IL2CPP 提取与写回
│   ├── tooling/           # Il2CppDumper / BMFont 隔离编排
│   ├── quality.py         # 质量门（20+ 硬规则 + 失败原因分类）
│   ├── batch_translator.py# 批量翻译（记忆直填/模型/质量门/重试链）
│   ├── reviewer.py        # 语义审核（强模型五维，默认关闭）
│   ├── agent_memory.py    # AgentMemory 经验记忆（证据驱动）
│   ├── memory.py          # 项目存储 + 会话级翻译记忆
│   ├── knowledge.py       # 六库知识库
│   └── glossary.py        # 术语库
├── ui/                    # PySide6 界面
├── scripts/               # all_record_runner.py（命令行排查）
├── tools/                 # Il2CppDumper、BMFont（固定版本+SHA-256 隔离）
├── fonts/                 # 思源黑体与 TMP 图集载荷
├── font_plugin/           # 运行时字体回退插件（C#）
├── tests/                 # 1900+ 测试
└── docs/                  # 计划/指南/闭环记录/审计报告
```

## 数据存储

- 全局设置 `~/.hanhua/settings.json`；项目库 `~/.hanhua/projects/<hash>/`
- 术语库 `glossary.db`；六库知识库 `~/.hanhua/knowledge.db`；经验记忆 `~/.hanhua/agent_memory.db`
- 翻译记忆随项目保留，重复翻译不重复扣费

## 开发

```powershell
# 全量测试（1900+）
python -m pytest -q

# 真实外部工具集成测试（需安装 Il2CppDumper/BMFont）
$env:HANHUA_RUN_REAL_TOOLS='1'
python -m pytest tests/test_tooling_adapters.py -q
```

## 未来规划（翻译质量保障系统）

规划中的完整版架构：**Qwen3-Embedding-0.6B（检索）→ Hy-MT2-1.8B（翻译）→ 硬规则 → Qwen3-Reranker-0.6B（语境匹配）→ 风险分流 → Qwen3-4B（深度审核）→ 修正/重译 → 知识沉淀**，四大知识库（术语/语境/特殊文本/翻译记忆）+ 错误案例库 + 游戏专属知识 + 向量检索。当前已实现与待实现差距、五阶段实施路线见 **`docs/翻译质量保障系统实施计划.md`**。

## 版本记录

- **0.25.x**（2026-08）：地毯式排查第九轮收官（fix-24~31：词库跳过/词表对象/键名通称/词对污染链/TMP 资产），force-reboot ~ headache 6 游戏闭环；AgentMemory 上线
- **0.24.x**：写回 C1-C10 校验闸门与验证闭环；识别 L1-L8 留档与证据分层；翻译失败原因分类体系
- **0.22.x**：语义审核基础设施（`reviewer.py`，默认关闭）；实机测试计划文档
- **0.20.x**：六库知识库体系；地毯式排查双游戏并行（40+ 游戏闭环）
- **0.15.x**：识别治理框架（形态注册表 + 未知形态告警）
- **0.13.x**：翻译计数同源；提取器噪音剔除；开始游戏按钮
- **0.12.0**：引擎配置对象保护（morfosigame 输入失效根因修复）
- **0.11.0**：内置 Python 3.12 环境，发行包免安装
