# 汉化助手 — Unity 游戏智能汉化工具

面向 Unity 游戏的本地化工具：**扫描识别 → 深度翻译 → 质量保障 → 安全写回 → 经验记忆** 全链路闭环。以本地小模型为主力（Hy-MT2-1.8B），用「翻译 + 知识 + 语境 + 检索 + 审核 + 修正 + 记忆」的体系化架构取代「原文 → 模型 → 中文」的单向翻译——这是本项目区别于普通翻译工具的核心。

> **目标**：不只是「把英文变成中文」，而是逐渐变成**理解游戏上下文的翻译系统**——多义词（Resume→继续 vs 简历）、游戏术语、格式安全、跨游戏一致的专名，都被体系消化。

---

## ✨ 核心特性

| 特性 | 说明 |
|---|---|
| **全文本来源** | 本地化文件、TextAsset、MonoBehaviour 序列化串、Addressables 表、Mono #US、IL2CPP metadata（v24~v39 全版本验证） |
| **深度翻译** | 游戏档案 + 术语表 + 翻译记忆 + 相邻上下文注入，统一质量门过滤坏译文 |
| **质量保障体系** | 20+ 硬规则检查（占位符/标签/Rich Text/数字/键名/词对）+ 失败原因分类 + 定向重译，1900+ 测试锁定 |
| **安全写回** | 只写回「质量通过 + 置信度合格」条目；四态闸门（文件/容器/对象/运行时）+ 重开验证 + 原子发布 |
| **经验记忆 AgentMemory** | 跨游戏自动沉淀：证据驱动晋升、语境敏感、拒绝降级退休——处理越多游戏越稳定 |
| **六库知识库** | unity_structure / fail_case / text / component_compat / quality / writeback 六域，106+ 种子案例 |
| **本地优先** | Hy-MT2-1.8B（llama.cpp）完全离线，GPU 自动加速 CPU 回退；在线 API 可选 |
| **解压即用** | 内置 Python 3.12 与 llama.cpp，零环境配置 |

---

## 🚀 快速开始（Windows）

```bash
# 方式一：解压完整包后双击根目录「启动汉化助手.bat」（解压即用，零依赖）

# 方式二：开发环境
pip install -r requirements.txt
python main.py
```

启动后：设置页选翻译后端（在线 API / 本地 Hy-MT2）→ **拖入游戏文件夹** → 五阶段工作台（检测 → 扫描 → 分析 → 翻译 → 写回）→ 写回成功后「开始游戏」一键启动汉化副本。

命令行排查（免界面全流程 + 全环节记录）：

```bash
python scripts/all_record_runner.py "D:\游戏\<游戏目录>" --no-review
# 输出：docs/all record/<游戏>/（summary.md + text/ + writeback/）
```

---

## 🧠 质量保障体系（核心）

翻译流程不是「模型 → 中文」，而是七环节闭环：

```
检索 → 翻译 → 检查 → 筛选 → 深审 → 修正 → 记忆
```

### 1. 硬规则检查（优先于 AI）

质量门对每条译文执行 20+ 确定性检查，坏译文在进池前拦截：

- **结构安全**：占位符（`{player}` / `%s` / `{0}`）、富文本标签（`<color>` / `<b>` / `<size>`）、换行、数字、控制字符
- **键名保护**：物理键名（RMB/Shift/Esc/SPACE…）强制保留或中文通称豁免（空格=space、esc=escape、右键=rmb）——按键提示译掉键名玩家找不到键
- **词对防污染**：glossary 词对子串命中需标签语境（TIME→时间 不误杀 "time to"→是时候）；键名词对全豁免（SPACE→空间 类污染词对跨游戏误杀已根除）
- **动作词残留**：TOSS TRASH→「TOSS 垃圾」半翻译判失败重译；引号内 UI 原文引用豁免
- **对象级跳过**：词表对象（打字游戏单词库 1700 条）、TMP 字体/精灵资产、输入绑定路径、引擎配置——翻译即破坏玩法/断引用

### 2. 失败原因分类与定向重译

失败原因优先级链（input_token → key_name → glossary → action_word → untranslated）逐层暴露问题、逐层修复；attempt 预算跨轮共享，耗尽不再重跑同链。

### 3. 审核分级（未来：PASS / MINOR / MAJOR / CRITICAL）

当前质量门为「通过 / 不通过 + 原因」；语义审核基础设施（强模型五维审核：术语/语境/专名/语义/风格）已建成。规划中的四级制与深度审核见《翻译质量保障系统实施计划》。

### 4. 经验记忆（AgentMemory）

跨游戏自动学习的离散知识单元：只收质量门通过且非回显的译文 → 多次一致证据晋升 active → 高置信直接应用（仍过质量门复查）、一般置信注入 prompt → 被拒绝的记忆降级直至退休。语境冲突可审计（memory-report.md）。

### 5. 地毯式排查实证

`D:\游戏` 全量游戏按计划双游戏并行闭环排查（`docs/地毯式排查升级计划.md`）：40+ 游戏闭环，多数 0 失败收敛；每轮暴露的系统性问题均以模块级修复解决（fix-16 ~ fix-31），不按游戏打补丁。全部修复有回归测试锁定。

---

## 📥 已验证文本来源

| 来源 | 提取 | 写回 |
|---|---|---|
| 本地化文件（JSON/CSV/TSV/XML/TXT/INI） | ✅ | ✅ 保留编码与换行策略 |
| TextAsset（含老 Unity 4.x/5.x str 字段） | ✅ | ✅ 可变长重建 + 重开验证 |
| MonoBehaviour 序列化字符串 | ✅ | ✅ 对象级重开验证 + 逻辑键 revert 防线 |
| Addressables bundle（Unity Localization 表） | ✅ | ✅ 按 Entry ID 写回 + catalog CRC 同步 |
| Mono 程序集（C# #US 堆） | ✅ | ✅ 固定容量写回，超长截断报告 |
| IL2CPP global-metadata.dat | ✅ 原生 + Il2CppDumper 交叉验证 | ✅ 全池重开比对（v24~v39） |

AssetBundle/SerializedFile 重建写回；Mono #US 与 IL2CPP 池受原容量限制。未知 runtime/版本显示 blocked，不假报成功。

---

## ⚠️ 能力边界（诚实说明）

- **已验证样本**：`D:\游戏` 118 游戏识别审计 + 40+ 游戏全流程闭环（扫描→翻译→写回→重开验证）；样本覆盖不等于所有 Unity 游戏通用保证
- **IL2CPP**：metadata 写回覆盖 v24/27/29/31/39，cosl（v31）、minato（v39）端到端闭环
- **老 Unity（4.x/5.x）**：WebFile 容器、str 类型 TextAsset 已验证；`.fnt` 位图字体游戏被正确阻断而非假报成功
- **不可汉化**：运行时拼接/加密文本、服务器下发文本、贴图内文字（需 OCR，超范围）
- **字体覆盖**：Windows x64 Mono 自动注入思源黑体；IL2CPP/x86 即使能提取也不在 BepInEx 字体运行时范围内
- **语义错译边界**：形态完整但语义错的译文（如 PRESS→「媒体」）质量门形态上无法拦截——靠语义审核分级（规划中）与记忆门禁（坏译文不沉淀）

---

## 🧱 技术架构

```
hanhua/
├── core/                  # 解析/翻译/存储/写回（与 UI 解耦）
│   ├── unity/             # UnityPy / dnfile / IL2CPP 提取与写回
│   ├── tooling/           # Il2CppDumper / BMFont 隔离编排
│   ├── quality.py         # 质量门（20+ 硬规则 + 失败原因分类）
│   ├── batch_translator.py# 批量翻译（记忆直填/模型/质量门/重试链）
│   ├── memory.py          # AgentMemory 经验记忆（证据驱动）
│   └── knowledge.py       # 六库知识库
├── ui/                    # PySide6 深色设计系统
├── scripts/               # all_record_runner.py（命令行排查）
├── tools/                 # Il2CppDumper、BMFont（固定版本+SHA-256 隔离）
├── fonts/                 # 思源黑体与 TMP 图集载荷
├── font_plugin/           # 运行时字体回退插件（C#）
├── tests/                 # 1900+ 测试（质量门/提取/写回/记忆/规则交互）
└── docs/                  # 计划/指南/闭环记录/审计报告
```

## 💾 数据存储

- 全局设置 `~/.hanhua/settings.json`；项目库 `~/.hanhua/projects/<hash>/`
- 术语库 `glossary.db`；六库知识库 `~/.hanhua/knowledge.db`；经验记忆 `~/.hanhua/agent_memory.db`
- 翻译记忆随项目保留，重复翻译不重复扣费

## 🔧 开发

```powershell
# 全量测试（1900+）
python -m pytest -q

# 真实外部工具集成测试
$env:HANHUA_RUN_REAL_TOOLS='1'
python -m pytest tests/test_tooling_adapters.py -q
```

## 🗺️ 未来路线（翻译质量保障系统）

规划中的完整版架构：**Qwen3-Embedding-0.6B（检索）→ Hy-MT2-1.8B（翻译）→ 硬规则 → Qwen3-Reranker-0.6B（语境匹配）→ 风险分流 → Qwen3-4B（深度审核）→ 修正/重译 → 知识沉淀**，四大知识库（术语/语境/特殊文本/翻译记忆）+ 错误案例库 + 游戏专属知识 + 向量检索。

实施路线与现状差距分析见 **`docs/翻译质量保障系统实施计划.md`**。

---

## 📜 版本记录

- **0.25.x**：地毯式排查第九轮收官（fix-24~31：词库跳过/词表对象/键名通称/词对污染链/TMP 资产）——force-reboot ~ headache 6 游戏闭环；AgentMemory 记忆模块上线（跨游戏短语复用实证）
- **0.24.x**：框架全面升级（写回 C1-C10 闸门与验证闭环、识别 L1-L8 留档与证据分层、翻译 C 系列、失败原因分类体系）
- **0.22.x**：语义审核基础设施（强模型五维审核 + 术语词对沉淀）+ 实机测试计划
- **0.20.x**：六库知识库体系 + 地毯式排查双游戏并行（40+ 游戏闭环）
- **0.15.x**：识别治理框架（形态注册表 + 未知形态告警）
- **0.13.x**：翻译计数同源 + 提取器噪音剔除 + 开始游戏按钮
- **0.12.0**：引擎配置对象保护（morfosigame 输入失效根因修复）
- **0.11.0**：内置 Python 3.12 环境，解压即用
