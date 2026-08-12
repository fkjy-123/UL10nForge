# 汉化助手 — Unity 游戏本地化工具

本地小模型（Hy-MT2-1.8B，llama.cpp）驱动的 Unity 游戏汉化工具，完全离线运行。
`扫描识别 → 批量翻译 → 质量检查 → 安全写回 → 经验积累` 全流程闭环，重点在**翻译质量保障**——不是「原文丢给模型」，而是规则、记忆、知识库层层把关。

---

## 快速开始（用户）

**发行包**：解压后双击根目录「启动汉化助手.bat」→ 设置页选翻译后端（本地 Hy-MT2 / 在线 API）→ 拖入游戏文件夹 → 五步工作台（检测 → 扫描 → 分析 → 翻译 → 写回）→ 写回成功后点「开始游戏」。

**开发环境**：

```bash
pip install -r requirements.txt
python main.py
```

**命令行排查**（免界面全流程 + 全环节记录）：

```bash
python scripts/all_record_runner.py "D:\游戏\<游戏目录>" --no-review
# 输出：docs/all record/<游戏>/（summary.md + text/ + writeback/）
```

## 质量保障（核心特色）

每条译文过**三道关**：

1. **记忆关** —— 以前翻过的一模一样文本直接复用，前后一致
2. **规则关** —— 20+ 确定性检查：占位符（`{player}`/`%s`）不丢、富文本标签不坏、数字不误改、按键名保护（RMB→「右键」可以，译没了玩家找不到键）、半翻译拦截（"TOSS TRASH"→「TOSS 垃圾」重译）
3. **经验关** —— AgentMemory 跨游戏自动沉淀：只收好译文、证据驱动晋升、被拒降级退休；术语库/六库知识库（106+ 种子案例）注入翻译

> **诚实边界**：译文「长得对」但「意思错」（如 PRESS→「媒体」）规则拦不住——语义审核四级分级（PASS/MINOR/MAJOR/CRITICAL）在规划中，见[实施计划](docs/翻译质量保障系统实施计划.md)。

## 支持范围

| 文本来源 | 提取 | 写回 |
|---|---|---|
| 本地化文件（JSON/CSV/TSV/XML/TXT/INI） | ✅ | ✅ 保留编码与换行 |
| TextAsset（含老 Unity 4.x/5.x） | ✅ | ✅ 可变长重建 + 重开验证 |
| MonoBehaviour 序列化字符串 | ✅ | ✅ 对象级重开验证 |
| Addressables（Unity Localization 表） | ✅ | ✅ Entry ID 写回 + CRC 同步 |
| Mono 程序集（C# #US 堆） | ✅ | ✅ 固定容量写回 |
| IL2CPP metadata（v24~v39） | ✅ | ✅ 全池重开比对 |

识别审计覆盖 `D:\游戏` 118 款、全流程闭环 40+ 款；不可汉化的（运行时拼接/加密/贴图文字）明确阻断不假报。**样本范围不等于所有 Unity 游戏通用**——IL2CPP 写回仅验证过 v24/27/29/31/39；IL2CPP/x86 游戏不保证字体显示；闭环验证到「写回 + 重开比对」为止，不做实机测试。

## 架构与开发（开发者）

```
扫描/提取（UnityPy·dnfile·IL2CPP）→ 翻译（BatchTranslator：记忆直填→模型→质量门→重试链）→ 写回（四态闸门+重开验证）
         ↑ 术语库/六库知识库/AgentMemory
```

```
hanhua/
├── core/                  # 与界面解耦：解析/翻译/质量/存储/写回
│   ├── unity/ tooling/    # 提取与写回（UnityPy / Il2CppDumper / BMFont）
│   ├── quality.py         # 质量门：20+ 硬规则 + 失败原因分类
│   ├── batch_translator.py# 批量翻译主流程
│   ├── reviewer.py        # 语义审核（强模型五维，默认关闭，规划接入生产）
│   ├── agent_memory.py    # 经验记忆（证据驱动晋升/退休）
│   ├── memory.py          # 项目存储 + 会话级翻译记忆
│   ├── knowledge.py       # 六库知识库
│   └── glossary.py        # 术语库
├── ui/  scripts/  tools/  fonts/  font_plugin/
└── tests/                 # 1900+ 测试
```

```powershell
python -m pytest -q                          # 全量测试
$env:HANHUA_RUN_REAL_TOOLS='1'               # 真实外部工具集成测试
python -m pytest tests/test_tooling_adapters.py -q
```

## 文档导航

| 文档 | 内容 |
|---|---|
| [翻译质量保障系统实施计划](docs/翻译质量保障系统实施计划.md) | 未来架构（四级审核/语境库/向量检索/自动学习）与分阶段路线 |
| [地毯式排查升级计划](docs/地毯式排查升级计划.md) | 排查流程与 40+ 游戏闭环记录 |
| [知识库体系](docs/知识库体系.md) · [记录模板规范](docs/记录模板规范.md) | 知识沉淀与记录标准 |
| `docs/all record/<游戏>/` | 每款游戏的闭环记录（summary / fix record / final report） |

## 版本

**0.25.x**（2026-08）：第九轮排查收官（fix-24~31）+ AgentMemory 上线 · 0.24.x：写回校验闸门与识别证据分层 · 0.22.x：语义审核基础设施 · 0.20.x：六库知识库与双游戏并行排查 · 0.11.0：发行包内置 Python 3.12，免安装
