# 汉化助手 — Unity 游戏智能汉化工具

**版本 0.11.0** · 面向 Unity 游戏的本地化工具：扫描游戏（外部文本 + 二进制资源）→ 深度 AI 翻译 → 人工审校 → 原格式写回。

> 不是普通逐字翻译。通过游戏档案、术语表、上下文与翻译记忆，产出贴合游戏世界观与文风的简体中文。
> 支持在线 LLM API 与本地 Hy-MT2 双后端，**完全离线也能翻**。

---

## ✨ 特性一览

| 特性 | 说明 |
|---|---|
| **解压即用** | 内置 Python 3.12 与 llama.cpp 运行时，全部依赖预装完毕，零环境配置、零首次下载 |
| **已验证文本来源** | 本地化文件、TextAsset（含老 Unity 4.x/5.x str 字段）、MonoBehaviour 字符串、Addressables 本地化表、Mono 程序集、IL2CPP metadata |
| **深度翻译** | 游戏档案（世界观/文风）+ 全局术语表 + 翻译记忆 + 上下文注入，统一质量门过滤坏译文 |
| **安全写回** | 只写回「翻译通过 + 置信度合格」的条目；未知 runtime/版本一律 blocked，不假报成功 |
| **中文字体覆盖** | 自动为汉化副本注入思源黑体，解决运行时缺字方框 |
| **本地/在线双后端** | 在线 OpenAI/Anthropic 兼容 API，或离线本地 Hy-MT2（llama.cpp），GPU 自动加速、CPU 自动回退 |

---

## 🚀 快速开始（Windows）

### 方法一：一键启动（推荐）

1. 下载完整包并解压到任意位置
2. 双击根目录的 **`启动汉化助手.bat`** —— **解压即用，零环境依赖**（无需安装 Python、无需联网下载）

### 方法二：命令行（开发环境）

```bash
pip install -r requirements.txt
python main.py
```

启动后：

- 想用**在线 API** → 设置页填 Base URL / Key / 模型
- 想用**本地翻译** → 把 GGUF 模型放进 `models/`，设置页选择「本地 Hy-MT2」→ 启动并测试
- **拖入游戏文件夹** → 开始汉化

> 本地模式完全离线：llama.cpp 只监听 `127.0.0.1`，不需要联网。模型已随项目提供：`models/Hy-MT2-1.8B-Q6_K.gguf`。

---

## 🎯 能做什么

### 已验证文本来源

| 来源 | 提取 | 写回 |
|---|---|---|
| 本地化文本文件（JSON / CSV / TSV / XML / TXT / INI） | ✅ | ✅ 保留编码与换行策略 |
| `.assets` 中的 **TextAsset**（对话/本地化常见载体） | ✅ | ✅ 可变长重建 + 重开验证 |
| `.assets` / AssetBundle 中 **MonoBehaviour 序列化字符串** | ✅ | ✅ 可变长重建 + 对象级重开验证 |
| **Addressables bundle**（`StreamingAssets/aa/`）Unity Localization 表 | ✅ | ✅ 按稳定 Entry ID 写回 + 同步 catalog CRC |
| **Mono 程序集** `Assembly-CSharp.dll` 等（C# #US 堆） | ✅ | 固定容量写回，超长截断并报告 |
| **IL2CPP** `global-metadata.dat` 字符串字面量池 | ✅ 原生解析 + Il2CppDumper 交叉验证 | 固定容量写回，超长截断并报告 |

AssetBundle/SerializedFile 使用重建写回；Mono #US 与 IL2CPP 字符串池受原始容量限制。工具只对已验证的输入组合开放自动写回，未知 runtime 或 metadata 版本会显示 blocked，不会假报成功。

### 界面与使用流程

| 页面 | 作用 |
|---|---|
| **首页** | 拖入游戏文件夹 → 五阶段工作台：游戏检测、文本扫描、工具分析、翻译质量、写回验证 |
| **设置** | 三个平行标签：翻译后端（在线 API / 本地 Hy-MT2）、高级设置（并发槽位/上下文/每批，含显存与速度预估）、术语表 |
| **文本审校** | 按状态/置信度/角色/来源筛选；查看失败原因、行内编辑、锁定不翻译条目；每次汉化的失败内容自动导出为「fail record」文档 |
| **翻译** | 开始（可停止续传）→ 质量门 → 安全写回 `<游戏目录>_汉化` |

### 深度翻译

- **游戏档案属于每个项目**：世界观、文风、源语言逐游戏独立填写，注入提示词
- **术语表**（全局）：人名/地名/专名固定译法，翻译时强制遵守
- 批量翻译携带来源文件、定位键、文本角色、识别置信度、相邻上下文与字符预算
- 统一质量门：检查空译文、非法控制字符、解释性前缀、占位符、富文本顺序、实际/字面换行、残留纯英文、术语与同角色一致性
- 模型输出和翻译记忆都经过同一质量门；坏记忆会被淘汰并在同次运行回退模型
- 只有 `translated + quality_passed` 且置信度合格的条目能写回；人工审校会留下显式提升证据

### 智能噪音治理（不乱扫）

三层过滤，全游戏目录只保留"可能是游戏文本"的内容：

1. **文件黑名单**：MonoBleedingEdge / il2cpp_data / ScriptingAssemblies.json 等 Unity 运行时噪音（`StreamingAssets/aa/` 是 Addressables 游戏内容所在地，**不**跳过）
2. **文件级判定**：整文件无可译条目、或条目大部分为无空格标识符（≥10 字符）→ 整文件剔除
3. **字符串级过滤**：路径/程序集名/哈希/着色器属性/Input System 绑定/URP 后处理/字体名等引擎字符串黑名单 + 频次过滤；`Press E to open`、`Hold [F] to interact` 等交互提示强显示证据提升，并保护按键 token
4. **键名保护（Localization 表键绝不翻译）**：`ui_newGame` / `MENU_PLAY` / `phone_call_01` 等键风格标识符、语言代码、JSON 键字段一律剔除；单词式写法（`Settings` / `V-SYNC`）是任意语言的 UI 标签，正常翻译。写回期二次防护：历史误译的键条目也不会写回
5. **增量收敛**：规则升级后重扫自动清理旧库中已淘汰的噪音条目

### 翻译后端

**在线 API**：OpenAI 兼容（`/v1/chat/completions`）与 Anthropic 原生（`/v1/messages`），Base URL / Key / 模型 / 并发 / 批量 / 温度全可配，URL 自动补全，含测试连接。

**本地 Hy-MT2（llama.cpp）**：

- 不需要 URL、API Key 或联网；应用自动发现 `models/*.gguf` 与 `runtime/llama/llama-server.exe`
- 只监听 `127.0.0.1`，使用临时访问 token；一键启动、健康检查、测试和停止
- 默认优先将模型层卸载到 GPU；GPU 启动失败自动回退 CPU 一次，不会无限重启
- 使用官方建议的 `temperature=0.7`、`top_p=0.6`、`top_k=20`、`repeat_penalty=1.05`，遵循模型"无默认 system prompt"的单 user 消息格式

**高级设置**（翻译后端旁独立标签）：

- **并发槽位**：同时开几条翻译线路；显存充足时可提高吞吐
- **上下文长度 / 每批条数**：控制单次请求的输入规模
- 实时给出**显存估算**（模型 + KV cache + 计算缓冲，读取 GGUF 元数据）与**速度估算**，配置前心里有数

### 中文字体覆盖

- 写回受支持的游戏后，运行时载荷位于 `<游戏目录>_汉化/BepInEx/`；插件、字体副本和家族配置位于 `BepInEx/plugins/HanhuaFont/`
- 内置 **思源黑体（Source Han Sans SC）**，覆盖简体中文字形缺失
- TTF 通过 `FR_PRIVATE` 只注册到启动后的**当前游戏进程**，不安装到 Windows，不永久修改系统字体
- 当前自动字体载荷只支持 **Windows x64 + Mono 后端**；x86、IL2CPP、结构不完整的游戏会被明确拒绝
- 第一次启动汉化副本后查看 `<游戏目录>_汉化/BepInEx/LogOutput.log`：记录字体家族加载、TMP/Legacy 文本处理计数与插件异常
- 覆盖解决的是运行时字体缺字，不提取或翻译贴图文字，也不能解决加密文本、服务器下发文本或自定义渲染管线完全绕过 Unity UI/TMP 的情况

### 失败记录

每次汉化结束，文本审校中所有失败条目自动导出到 **`docs/fail record/`**，以游戏名命名（如 `游戏名 fail record 2026-08-08 17-25-59.txt`），包含来源、原文、译文、失败原因与错误详情，方便复盘与补翻。

---

## ⚠️ 能力边界（诚实说明）

- **已验证样本**：`D:\游戏` 93 个 Unity 游戏全量识别回归（93/93 通过）+ 118 游戏审计 0 失败；外部下载 5 个 Unity 游戏全流程闭环（扫描 → 翻译 → 写回 → 重开验证 → 重扫），其中 MarioVsLuigi（Unity 5.x 老架构 WebFile 合并场景）与 BlocksBeyondTheStars（379MB 完整游戏）闭环通过，覆盖老 Unity TextAsset `m_Script` 为 str 字段的写回路径。样本覆盖不等于所有 Unity 游戏通用保证
- **老 Unity（4.x/5.x）**：WebFile（data.unity3d 合并场景）容器、str 类型 TextAsset 写回已验证；`.fnt` 位图字体游戏（如 Daggerfall Unity）写回会因无字体注入器被正确阻断，而不是假报成功
- **IL2CPP 游戏**：metadata 写回覆盖 v24/27/29/31/39 全版本（17 个真实 metadata 全量验证通过）；cosl（v31）、minato（v39）真实游戏端到端闭环通过（写回 → UnityPy 重开解析 0 错误 → 译文可寻回）
- **不可汉化**：运行时拼接/加密文本、服务器下发文本、贴图内文字（需 OCR，超出当前范围）
- **字体覆盖边界**：仅支持 Windows x64 Mono；IL2CPP/x86 即使文本能够提取，也不在 BepInEx 字体运行时的支持范围内
- 无文本的游戏会判定为 0 条可译内容，不浪费 API

---

## 🧱 技术架构

`hanhua/core`（解析/翻译/存储/写回，与 UI 解耦）+ `hanhua/core/unity`（UnityPy / dnfile / IL2CPP 提取与写回）+ `hanhua/core/tooling`（Il2CppDumper / BMFont 隔离编排）+ `hanhua/ui`（PySide6 深色设计系统）。

自动化流程只依赖两个工具，均固定版本与 SHA-256、隔离运行、超时清理、结果进内容寻址缓存：

- **Il2CppDumper 6.7.46**：仅用于 IL2CPP 字符串集合交叉验证。原生 metadata locator 始终是写回权威。
- **BMFont 1.14a**：仅在检测到 `.fnt` 证据时生成并验证位图字体 atlas。

## 📁 目录结构

```
├── 启动汉化助手.bat        # Windows 一键启动（优先内置 Python）
├── main.py                 # 程序入口
├── hanhua/
│   ├── core/               # 解析/翻译/存储/写回（与 UI 解耦）
│   ├── ui/                 # PySide6 界面
│   └── ...
├── models/                 # 本地 GGUF 模型（Hy-MT2-1.8B-Q6_K.gguf）
├── runtime/
│   ├── python/             # 内置 Python 3.12 环境（解压即用的关键）
│   └── llama/              # llama.cpp 运行时（本地翻译，含 CUDA/CPU 双后端）
├── tools/                  # 自动编排依赖：Il2CppDumper、BMFont
├── fonts/                  # 思源黑体与 TMP 图集载荷
├── font_plugin/            # 运行时字体回退插件（C# 源码 + 构建脚本）
├── scripts/                # 维护与审计脚本
└── docs/fail record/       # 每次汉化的失败条目导出
```

## 💾 数据存储

- 全局设置 `~/.hanhua/settings.json`
- 项目库与游戏档案在 `~/.hanhua/projects/<hash>/`（每游戏独立）
- 翻译记忆与断点状态随项目保留，重复翻译不重复扣费

## 🔧 开发

```powershell
# 全量测试（UI 测试需离屏平台）
$env:QT_QPA_PLATFORM='offscreen'
$env:HANHUA_GAMES_DIR='C:\Users\mingming\Downloads\games'
python -m pytest -q

# 真实外部工具集成测试
$env:HANHUA_RUN_REAL_TOOLS='1'
python -m pytest tests/test_tooling_adapters.py -q

# 本地模型冒烟测试
python -X utf8 .\scripts\smoke_test_local_model.py
```

## 📜 版本记录

- **0.11.0**：内置 Python 3.12 环境，解压即用、零环境依赖
- **0.10.0**：外部 Unity 游戏外测闭环 + 老 Unity str 写回修复 + 验证性能优化
- **0.9.0**：识别模块大升级（覆盖率 ≥95%）
- **0.8.0**：写回安全闸门 + 三模块加固
