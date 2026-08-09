# Unity 文本识别与提取资料大全

> 阶段 1（Web 文献研究）产出。按「文本位置类型」组织，每类给出
> 所在位置、存储格式、提取方法、工具、以及本工具（hanhua）覆盖状态。
> 「覆盖状态」是阶段 2 深度调查与阶段 3 升级的对照基准。

---

## 0. 总览：Unity 文本载体地图

```
游戏目录（_Data/）
├── 外部文本文件（直接可读）——最高优先级
│   ├── TextAsset 导出（.txt/.csv/.json）——含 Unity Localization 表
│   ├── StreamingAssets/ 下任意文件（含 Addressables aa/ 目录）
│   ├── Resources/ 下打包前的原始文本
│   └── 通用格式：csv / json / xml / yaml / po / resx / sqlite / ini
├── Unity 序列化容器（需 UnityPy/AssetStudio 解析）
│   ├── *.assets / sharedassetsN.assets —— 对象表 + TypeTree
│   │   ├── TextAsset 对象（m_Script 字段 = 文本内容）
│   │   ├── MonoBehaviour（序列化字节含字符串，UTF-16 为主）
│   │   ├── TextMeshPro 对象（m_text 字段 = 显示文本）
│   │   └── Localization 表（官方包 StringTable / I2 的 I2Languages）
│   ├── *.resS / *.resource —— 外部原始数据（需 .assets 的 offset/size）
│   ├── AssetBundle（.unity3d / .bundle / 无扩展名）——可嵌套 SerializedFile
│   └── 场景文件（level0/1…，无扩展名）
├── 代码字符串表（硬编码文本）
│   ├── Mono：Managed/*.dll 的 #US 堆（dnfile / Mono.Cecil 可读）
│   ├── IL2CPP：il2cpp_data/Metadata/global-metadata.dat 字符串表
│   └── GameAssembly.dll / libil2cpp.so 内嵌（与 metadata 关联）
└── 混淆/加密层（识别盲区）
    ├── UnityCN 加密 bundle（#$unity3dchina!@ 签名，AES-ECB+XOR）
    ├── 自定义 XOR / FakeHeader 垃圾头
    └── Base64 / PlayerPrefs 混淆字符串
```

---

## 1. 外部文本文件

### 1.1 通用本地化格式（最高命中率）

| 格式 | 说明 | 提取方法 | 工具覆盖 |
|---|---|---|---|
| CSV | 最常用（Unity Localization 表导出、I2、Localizer Easy） | 按表头/列解析；UTF-8 常见 | ✅ 已支持 csv_format |
| JSON | 广泛使用（含 JSONC 注释变体） | 递归 key-value | ✅ 已支持 json_format（JSONC） |
| XML | 含 .resx（.NET 资源）、XLIFF | 节点遍历 | ✅ 已支持 xml_format |
| YAML | 常见于对话/配置 | 键值解析 | ✅ 已支持 yaml_format |
| PO/POT | gettext 标准 | 条目 msgid/msgstr | ✅ 已支持 po_format |
| INI/CFG | 键值文本 | kv 解析 | ✅ 已支持 txt kv 分支 |
| SQLite | 部分游戏把文本放 db | sqlite3 读表 | ✅ 已支持 sqlite_format |
| 纯 txt | 行文本/键值/分隔符 | 行重建 | ✅ 已支持 txt_format |

### 1.2 对话/叙事专用格式

| 格式 | 来源 | 说明 |
|---|---|---|
| Ink (.ink) | inkle 对话系统 | 编译成 JSON 或运行时加载 |
| Yarn Spinner (.yarn) | Yarn Spinner 对话 | 文本行 |
| articy:draft | 叙事工具 | 导出 JSON/XML |
| Twine (HTML) | 交互小说 | 少见 |

本工具 `ink_yarn` 已覆盖前两种。

### 1.3 TextAsset 内嵌文本

- **位置**：`*.assets` 容器里的 TextAsset 对象，`m_Script`/`script` 字段
- **内容**：CSV（Localization 常用）、JSON、行文本，甚至二进制
- **提取**：UnityPy `obj.read()` → `.script`（新版本）或 `m_Script`（旧）
  - 新版本用 `.script`（bytes），因为部分游戏把二进制塞进 TextAsset
- **陷阱**：TextAsset 可能被塞二进制 → 必须二进制安全解析
- **覆盖状态**：✅ 已支持（unity extractor 的 TextAsset 分支）

### 1.4 Unity 官方 Localization 包（StringTable）

- **位置**：TextAsset 或 ScriptableObject（MonoBehaviour）形式的
  LocalizationTable / StringTable 资产
- **结构**：每个表 = key 列表 + 每语言一个值列；代码通过
  `LocalizedString.GetLocalizedString()` 取（占位符 `{0}`）
- **提取**：UnityPy 读 MonoBehaviour 序列化树；或 AssetRipper 导出后
  找 TextAsset/`*.asset`
- **覆盖状态**：✅ 序列化树通用遍历可覆盖（若表以 MonoBehaviour 存）

### 1.5 I2 Localization（第三方最流行）

- **位置**：`I2Languages.asset` / `I2Languages.prefab`（通常
  `Resources` 下，打包后进 `resources.assets`）
- **结构**：LanguageSource 对象：languages 头 + Terms 列表，每个
  Term 是 key + 每语言字段；记录间有 `\x00` padding
- **提取**：pyI2L（`./pyI2L.exe resources.assets` → CSV，rawCSV 最
  通用）；或 UnityPy 读 MonoBehaviour 二进制后按 I2 结构解析
- **覆盖状态**：⚠️ 序列化树通用遍历能取出 key/value 字符串（utf-16
  字节扫描兜底），但无专用解析器——调查后按需补充
- **参考**：https://github.com/KovacsGG/pyI2L

### 1.6 StreamingAssets 与 Addressables

- **StreamingAssets/**：原始文件直接放这里（含 `aa/` Addressables
  bundle 目录、`Text/` 子目录常见）
- **catalog.json**（Addressables 索引）：`StreamingAssets/aa/XXX/
  catalog.json`，映射 key → bundle；有 JSON（v1/v2/v3）与二进制
  （Binv1/Binv2）两种
- **提取**：catalog 用于定位（AddressablesTools 的 searchasset），
  文本实际在对应 bundle 里；UnityPy `env.load()` 直接递归
- **覆盖状态**：✅ bundle 递归加载已支持；⚠️ catalog 追踪未做
  （catalog 本身无文本，仅定位用——低优先级）
- **参考**：https://github.com/nesrak1/AddressablesTools

---

## 2. Unity 序列化容器

### 2.1 *.assets / sharedassetsN.assets

- 对象表 + TypeTree；`binary2text`（Unity 官方工具）可转文本，但要求
  同版本 Unity 且有 TypeTree（Player 构建默认无 → 用 UnityPy 更稳）
- 关键对象类型与文本字段：

| 对象类型 | 文本字段 | 说明 |
|---|---|---|
| TextAsset | `m_Script` | 整文件文本 |
| MonoBehaviour | 序列化字节 | 字段值多为 UTF-16 字符串，需树解析或字节扫描 |
| TextMeshPro | `m_text` | 组件显示文本（+ TMP_Text 富文本） |
| UGUI Text | `m_Text` | 旧版 UI |
| LocalizationTable | 表数据 | 官方 Localization 包 |
| Material/Shader | 内嵌字符串 | 少见可译文本 |
| Sprite/Texture | — | 无文本（排除） |

- **覆盖状态**：✅ typetree 遍历 + raw 字节 UTF-16/UTF-8 兜底

### 2.2 .resS / .resource 外部数据

- **本质**：无头的原始字节块，须由配对 `.assets` 的 offset/size 索引
- **文本价值**：通常装音频/贴图（无文本）；极少数把字符串塞这里
- **提取**：先解析 .assets 拿引用再取字节范围；直接 strings 扫描
  低效（压缩块 LZ4 需先解压）
- **覆盖状态**：⚠️ 字节盲扫会扫到，但无结构化解析——调查确认后按需

### 2.3 AssetBundle（.unity3d/.bundle/无扩展名）

- 容器可嵌套（bundle 内含 SerializedFile，甚至 bundle 套 bundle）
- UnityPy `env.load()` 自动递归；`env.files` 遍历
- UnityCN 加密 bundle 需 key（`set_assetbundle_decrypt_key`）；
  可 `brute_force_key` 暴力探测 16 字符 key
- **覆盖状态**：✅ 已支持递归；⚠️ UnityCN 解密未做（D:\游戏 调查
  后再定）

### 2.4 场景文件（levelN，无扩展名）

- 同样是 SerializedFile，含场景内 TextMeshPro/Text 组件实例的文本
- **覆盖状态**：✅ 已覆盖（9 游戏闭环实证）

---

## 3. 代码字符串表

### 3.1 Mono DLL（Managed/*.dll）

- **#US 堆**：`dnfile` / `Mono.Cecil` / `AssetStudio` 的
  MonoBehaviour 解析均可读；字符串表紧凑排列，UTF-8 编码（1-2 字节
  前缀长度）
- 文本角色：仅 `ldstr` 常量（UI 文案、提示、硬编码消息）
- **覆盖状态**：✅ mono_dll.extract_dll_user_strings 已实现

### 3.2 IL2CPP global-metadata.dat

- **位置**：`GameName_Data/il2cpp_data/Metadata/global-metadata.dat`
- **结构**：字符串表区域（无分隔符紧凑排列）；class/method 名区域
  以 `\0` 结尾；header 有每串 length+offset
- **提取工具**：Il2CppDumper（stringliteral.json）、
  il2cpp-stringliteral-patcher（extract.py/patch.py，支持变长替换）、
  r2unity（radare2 插件，v24-v39）、MetaDataStringEditor（GUI）
- **可变长写回**：patcher 用「复用原空间 + 尾部追加」策略
- **覆盖状态**：✅ il2cpp.py 已实现（Il2CppDumper 交叉验证 + 容量
  限制写回）；加密 metadata（无 magic）为已知盲区
- **参考**：
  - https://github.com/jozsefsallai/il2cpp-stringliteral-patcher
  - https://github.com/radareorg/r2unity
  - https://github.com/nevermoe/unity_metadata_loader

### 3.3 原生二进制内嵌字符串（GameAssembly.dll / libil2cpp.so）

- `strings` 可扫；但要关联 metadata 才知道字符串语义；实际文本池在
  metadata，bin 内多为 URL/类名等
- **覆盖状态**：✅ 依赖 IL2CPP 路径已覆盖；纯 bin 扫描不做（噪声高）

---

## 4. 混淆与加密层（识别盲区）

| 类型 | 特征 | 对策 |
|---|---|---|
| UnityCN 加密 bundle | 头部 `#$unity3dchina!@` 签名；LZ4；AES-ECB+XOR 双层 | 需要 key（暴力 16 字符 \w 探测）；AssetStudio_Tuanjie / UnityPy 支持 |
| 自定义 XOR | 非 Unity magic 头；统计高频字节（0x20）推导 key | XOR 盲试 + magic 校验（UnityFS/UnityWeb） |
| FakeHeader 垃圾头 | magic 前有垃圾前缀（≤128KB） | 前 128KB 扫 magic 后裁剪 |
| Base64 混淆 | 可见 base64 字符串 | 解码后仍需业务 key，标记不可译 |
| 加密 global-metadata | 无 magic / 乱码 | 内存 dump 找 key；标记 blocked |
| 多层组合 | 加密+自定义 LZ4+垃圾头 | 逐层剥离 |

- **覆盖状态**：❌ 全部未实现——作为「识别」应至少做到**检测并标记**
  （报告「此文件疑似加密/混淆，需人工处理」），不要求解密写回
- **参考**：
  - https://blog.axix.top/index.php/2024/03/12/72/（UnityCN 加解密原理）
  - https://github.com/K0lb3/UnityPy（ArchiveStorageManager 解密实现）

---

## 5. 运行时捕获（对照参考，非本工具范围）

XUnity.AutoTranslator 用 Harmony 钩子拦截 TextMeshProUGUI.SetText()
等渲染入口，能捕获「运行时由代码动态生成」的文本——静态分析永远
扫不到的文本。本工具定位是静态批处理，但运行时捕获的**文本清单**可
作为覆盖率对照基准（用户可另跑，输出 CSV 对比）：

- 文本框架：UGUI / TextMeshPro / NGUI / IMGUI
- 捕获机制：SetText 钩子 + OnRectTransformDimensionsChange 重绘钩子
- 新 Unity/TMP 版本钩子可能失效（TMP 1.4.0 移除 SetCharArray）
- 参考：https://github.com/LavaGang/XUnity.AutoTranslator

---

## 6. 工具矩阵

| 工具 | 定位 | 覆盖 | 备注 |
|---|---|---|---|
| UnityPy (k0lb3) | Python 库 | 全部容器 + 写回 | 本工具核心，活跃维护 |
| AssetStudio.NET | GUI | 容器浏览/导出 | Razmoth fork 支持 UnityCN |
| AssetRipper | CLI/GUI | 整项目导出 | 文本导出用 Plain Text 模式 |
| UABEA | GUI/CLI | 逐资产 dump/导入 | 编辑/重打包；patchcrc 清校验 |
| Il2CppDumper | CLI | IL2CPP metadata 全解 | stringliteral.json |
| il2cpp-stringliteral-patcher | CLI | metadata 字符串提取/写回 | 支持变长 |
| dnfile | Python 库 | Mono DLL #US | 本工具 mono 路径依赖 |
| AddressablesTools | C# 库 | catalog 读写 | searchasset/patchcrc |
| pyI2L | CLI | I2 术语表 | 专用格式 |
| binary2text / UnityDataTools | 官方 CLI | SerializedFile 转文本 | 要求 TypeTree + 同版本 |
| r2unity | radare2 插件 | metadata 字符串恢复 | 只读分析 |

---

## 7. 提取流水线推荐（本工具实现原则）

1. **文件系统普查**（零成本）：扩展名/命名模式/大小分类，直接可读
   文件优先解析
2. **容器解析**（UnityPy）：所有文件试 load → 对象树 + raw 兜底
3. **字节级盲扫**（兜底）：非容器文件做 UTF-8/UTF-16-LE/GBK 解码 +
   英文串统计，过滤噪声（对照源树滤假证据）
4. **代码字符串表**：mono #US / IL2CPP metadata（display 角色判定）
5. **检测未覆盖**：加密/混淆 → 标记 + 报告，不硬解
6. **覆盖率核算**：已发现文本位置 ÷ 全部可能位置（三路交叉估计）

---

## 8. 参考文献

- UnityPy: https://pypi.org/project/UnityPy/ · https://github.com/k0lb3/UnityPy
- AssetStudio.NET: https://github.com/Perfare/AssetStudio（Razmoth fork 支持 UnityCN）
- AssetRipper: https://github.com/AssetRipper/AssetRipper
- UABEA: https://github.com/nesrak1/UABEA
- Il2CppDumper: https://github.com/Perfare/Il2CppDumper
- il2cpp-stringliteral-patcher: https://github.com/jozsefsallai/il2cpp-stringliteral-patcher
- r2unity: https://github.com/radareorg/r2unity
- unity_metadata_loader: https://github.com/nevermoe/unity_metadata_loader
- AddressablesTools: https://github.com/nesrak1/AddressablesTools
- pyI2L: https://github.com/KovacsGG/pyI2L
- XUnity.AutoTranslator: https://github.com/LavaGang/XUnity.AutoTranslator
- UnityCN 加解密: https://blog.axix.top/index.php/2024/03/12/72/
- Unity 官方二进制分析工具（binary2text/UnityDataTools）:
  https://github.com/Unity-Technologies/UnityDataTools
- Unity 汉化工作流（CSDN）: https://blog.csdn.net/weixin_32390647/article/details/161280065
- B 站 IL2CPP 汉化教程: https://www.bilibili.com/opus/1041221869238222855
