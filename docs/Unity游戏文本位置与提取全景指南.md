# Unity 游戏文本位置与提取全景指南

> 研究日期：2026-08-08  
> 适用范围：已发布的 Unity 游戏（Windows、Linux、macOS、Android、iOS、WebGL，以及可取得文件系统镜像的主机平台）  
> 目标：尽可能完整地发现“玩家可能看见或听见、且具有本地化价值”的文本，并为每类位置给出可执行的提取路线。

## 1. 先说结论：不存在只靠一种扫描方式的“全识别”

Unity 文本不等于 `.txt` 文件，也不等于 `TextAsset`。玩家最终看到的文字可能来自：

1. 游戏目录中的普通文本、表格、数据库或自定义二进制文件；
2. 场景、Prefab、ScriptableObject、AssetBundle、Addressables 等 Unity 序列化对象；
3. Mono 程序集、IL2CPP metadata、原生插件或 WebAssembly 中的字符串字面量；
4. 启动后解密、解压、拼接或格式化出的运行时字符串；
5. HTTP、WebSocket、Remote Config、热更新包或平台 SDK 下发的远程文本；
6. Texture2D、Sprite、视频、网格等视觉资源中已经“烘焙”成像素或几何体的文字；
7. 语音中存在但没有字幕文件的对白；
8. 操作系统、Steam/主机平台、广告、支付、登录等外部界面生成的文字。

因此，接近完整覆盖的正确模型是五路结果取并集：

```text
文件扫描
  ∪ Unity 对象级扫描
  ∪ 托管/原生代码扫描
  ∪ 运行时捕获
  ∪ OCR/ASR 结果侧审计
```

只做前三路属于“静态可提取文本”；加入运行时捕获才能覆盖动态数据；加入 OCR/ASR 和人工走查，才能发现静态结构未知、服务器下发、图片/视频/音频内的最终呈现内容。

### 1.1 “文本”应分成四类，不能混在一起翻译

| 类别 | 示例 | 处理原则 |
|---|---|---|
| 显示值 | `New Game`、对白、物品说明、字幕 | 提取并翻译 |
| 本地化键 | `menu.new_game`、`ITEM_SWORD_NAME`、Entry ID | 保存定位关系，通常不翻译 |
| 格式模板 | `{player} found {count:plural:...}`、`HP: {0}` | 翻译字面部分，严格保护变量和语法 |
| 技术/噪音字符串 | 类名、Shader 属性、资源路径、日志格式、URL | 默认过滤，但保留可追溯的候选记录 |

“尽量全”不能通过降低字符串判断门槛简单实现。更安全的办法是：先无损发现，再用来源、字段名、调用点和运行时证据给候选分级，绝不在发现阶段永久丢弃低置信度内容。

## 2. 全景位置速查表

下表是扫描器应覆盖的主索引。后文逐项展开。

| 层级 | 文本位置/载体 | 常见路径或特征 | 推荐提取方式 | 静态可覆盖性 |
|---|---|---|---|---|
| 松散文件 | JSON、JSON5、NDJSON | 任意目录、`StreamingAssets`、Mods | 容错解析 + 递归字符串叶节点 | 高 |
| 松散文件 | CSV、TSV、PSV、Excel 导出表 | `Localization`、`Lang`、`Data` | 方言/编码探测，保留列与主键 | 高 |
| 松散文件 | XML、RESX、XLIFF、TMX | 配置、本地化、插件目录 | 命名空间感知 XML 解析 | 高 |
| 松散文件 | TXT、INI、CFG、LANG、properties | 任意目录 | 编码探测 + 行/键值解析 | 高 |
| 松散文件 | YAML、TOML、PO/MO、ARB | 插件或自研本地化系统 | 专用解析器 | 高 |
| 剧情脚本 | Ink、Yarn、Fungus 导出、RenJS 类脚本 | `.ink`、`.json`、`.yarn`、`.yarnc` | 语法解析或运行时 API | 中高 |
| 字幕 | SRT、VTT、ASS/SSA、TTML、LRC | 视频/剧情/StreamingAssets 附近 | 字幕解析器 | 高 |
| 数据库 | SQLite、SQLCipher、Realm、LevelDB | `.db`、`.sqlite`、无扩展名 | 魔数识别、表枚举、必要时运行时解密 | 中 |
| 自定义数据 | Protobuf、MessagePack、FlatBuffers、BSON | `.bytes`、`.dat`、`.bin`、无扩展名 | Schema/反序列化调用分析、运行时 hook | 中低 |
| 压缩/封装 | ZIP、7z、GZip、LZ4、Zstd、自定义包 | 魔数优先于扩展名 | 递归解包并记录容器链 | 中高 |
| Unity 容器 | SerializedFile | `globalgamemanagers`、`level0`、`sharedassets*.assets` | UnityPy/AssetRipper 类型树 | 高 |
| Unity 容器 | AssetBundle | `UnityFS`、`UnityRaw`、`UnityWeb` | 递归打开内部 SerializedFile | 高 |
| Unity 容器 | WebFile/WebData | `UnityWebData1.0`、WebGL `.data` | WebFile 解包 | 高 |
| Unity 对象 | TextAsset | `m_Script` 字节数组 | 编码/格式探测后递归解析 | 高 |
| Unity 对象 | MonoBehaviour/ScriptableObject | 任意自定义字符串字段 | 类型树全递归 + 脚本身份 | 高（有类型树时） |
| Unity UI | `UnityEngine.UI.Text`、`InputField` | `m_Text`、placeholder 引用 | 类型树字段 + 组件关系 | 高 |
| 3D 文本 | `UnityEngine.TextMesh` | `m_Text` | SerializedFile 类型树 | 高 |
| TextMesh Pro | `TMP_Text`、`TextMeshProUGUI`、`TMP_InputField` | 常见字段 `m_text`，实为 MonoBehaviour | 类型树 + MonoScript 识别 | 高 |
| UI Toolkit | UXML/VisualTreeAsset、USS 引用 | `text`、tooltip、自定义属性 | 原始 UXML 或 VisualTreeAsset 类型树 | 中高 |
| 本地化包 | Unity Localization StringTable | `m_TableData`、`m_Localized` | 按 locale/table/Entry ID 提取 | 高 |
| 本地化包 | SharedTableData | key 名、稳定 ID | 只作为映射，不翻译 key | 高 |
| 本地化包 | Smart String | `{}`、plural、gender、conditional | SmartFormat 语法树/占位符保护 | 高 |
| 第三方 UI/本地化 | I2 Localization、Lean Localization、NGUI、FairyGUI 等 | MonoBehaviour、TextAsset、自定义包 | 插件指纹 + 类型树/运行时适配器 | 中高 |
| 场景与 Prefab | 页面初始文字、tooltip、禁用对象文字 | `level*`、`data.unity3d`、bundle 内场景 | 扫描全部对象，包括 inactive 对象 | 高 |
| Timeline/剧情资产 | PlayableAsset、Signal、Marker、自定义 clip | MonoBehaviour/ScriptableObject 字段 | 类型树递归，不能只看已知类 | 中高 |
| 托管代码 | Mono C# 字符串 | `*_Data/Managed/*.dll` 的 `#US`、`ldstr` | 遍历游戏程序集 + IL 调用溯源 | 高 |
| 托管资源 | Manifest Resource、`.resources`、RESX 编译物 | 嵌入 DLL 或旁车 satellite assembly | ResourceReader/反编译器 | 高 |
| IL2CPP | 字符串字面量池 | `global-metadata.dat` + GameAssembly/libil2cpp | metadata 解析 + executable registration | 中高 |
| 原生代码 | EXE/DLL/SO/dylib/Framework | UTF-8/16/32、资源节、常量表 | strings + PE/ELF/Mach-O 资源/反汇编 xref | 中 |
| Android 原生层 | `resources.arsc`、`res/values/strings.xml`、DEX | APK/AAB/OBB/Asset Pack | apktool/aapt/DEX 分析 | 高 |
| iOS 原生层 | `.strings`、`.stringsdict`、plist、bundle | `.app`/Framework/PlugIns | plist/strings 解析 | 高 |
| WebGL | JS glue、WASM、`.data`、IndexedDB 缓存 | `.wasm`、`.framework.js`、`.data` | WebData + WASM/JS strings + 运行时 hook | 中 |
| 用户数据 | PlayerPrefs、存档、缓存、Mods | LocalLow、注册表、AppData、用户目录 | 安装后扫描 + 格式探测 | 中高 |
| 远程内容 | CDN Addressables、热更新、Remote Config | catalog URL、cache、HTTP 响应 | catalog 追踪 + 网络/缓存捕获 | 运行时为主 |
| 运行时 UI | 动态赋给 Text/TMP/UITK/IMGUI 的字符串 | 无稳定磁盘位置 | setter/API hook + 上下文采集 | 高（运行覆盖充分时） |
| 图片文字 | Texture2D、SpriteAtlas、RenderTexture | 图集、UI 图片、扫描件 | 导出、切图、OCR、人工复核 | OCR |
| 视频文字 | VideoClip、StreamingAssets 视频、远程流 | MP4/WebM/VP8 等 | 抽帧 OCR；另查外挂字幕 | OCR |
| 几何文字 | Mesh、SVG、矢量图、粒子/图标字体 | 字形已转路径/顶点 | 渲染截图 OCR，必要时资产重制 | OCR |
| 语音对白 | AudioClip、Wwise/FMOD bank、远程语音 | WAV/OGG/MP3/BNK/BANK | 解包 + ASR + 时间轴对齐 | ASR |
| 外部界面 | Steam、EOS、平台成就、OS 对话框、广告 SDK | 平台后台或 SDK 响应 | 平台 API/后台资源审计 | 不完全受游戏文件控制 |

## 3. 游戏安装目录中可能出现文本的具体位置

### 3.1 Unity Player 常规布局

Windows/Linux 桌面构建首先检查：

```text
Game.exe / Game.x86_64
Game_Data/
  globalgamemanagers
  globalgamemanagers.assets
  resources.assets
  sharedassets0.assets ... sharedassetsN.assets
  level0 ... levelN
  mainData                       # 某些旧版 Unity
  data.unity3d                   # 某些旧版或合并布局
  resources.resource / *.resS   # 大块外部流数据
  Managed/*.dll                 # Mono 后端
  il2cpp_data/Metadata/global-metadata.dat
  StreamingAssets/**
  Plugins/**
  RuntimeInitializeOnLoads.json
  ScriptingAssemblies.json
UnityPlayer.dll
GameAssembly.dll                # Windows IL2CPP
```

重要提醒：

- `globalgamemanagers` 通常主要是引擎/构建配置，但不能在“发现阶段”仅凭文件名永久排除；某些游戏或特殊版本可能包含开发者配置字符串。应以对象和字段证据过滤。
- `levelN`、`mainData`、`data.unity3d` 可能承载整场景 UI、对话触发器和禁用对象中的初始文本。
- `resources.assets`、`sharedassets*.assets` 不只存 TextAsset；任何 MonoBehaviour、ScriptableObject 或自定义 PlayableAsset 都可能有显示字符串。
- `.resS`、`.resource` 常是 Texture2D、AudioClip 等大块流数据的伴随文件。它们通常不独立保存普通字符串，但必须随父 SerializedFile 一起保留和解析，否则会漏掉图片/音频文字。

macOS 构建通常在：

```text
Game.app/Contents/Resources/Data/**
Game.app/Contents/Frameworks/**
Game.app/Contents/PlugIns/**
```

不要只扫描 `*_Data` 命名的目录；不同平台和 Unity 版本布局不同，应通过 `globalgamemanagers`、SerializedFile/Bundle 魔数和 Player 文件特征识别根目录。

### 3.2 StreamingAssets

Unity 官方说明：`Assets/StreamingAssets` 的内容会绕过标准序列化流程，基本按原样复制进 Player。这里经常出现：

- JSON/XML/CSV/TSV/INI/LANG/Properties 本地化文件；
- SQLite、二进制剧情库、关卡数据；
- AssetBundle 和 Addressables 本地内容；
- Ink/Yarn/自研剧情脚本；
- SRT/VTT/ASS 字幕、视频与音频；
- Wwise `StreamingAssets/Audio/GeneratedSoundBanks` 或 FMOD bank；
- JavaScript/Lua/HybridCLR/热更新代码及其数据；
- 加密包、补丁清单、远程 CDN 地址。

Android 上 StreamingAssets 位于 APK/JAR 内，不一定能用普通文件 API 直接访问；WebGL 上也通常是 URL。提取器必须理解 APK/ZIP/WebData，而不能只递归当前文件系统目录。

### 3.3 Addressables 与远程内容

常见本地位置包括：

```text
Game_Data/StreamingAssets/aa/**
Game_Data/StreamingAssets/aa/catalog.json
Game_Data/StreamingAssets/aa/catalog.bin
Game_Data/StreamingAssets/aa/settings.json
Game_Data/StreamingAssets/aa/*.bundle
```

但文件名、catalog 格式和路径受 Addressables 版本、构建脚本与平台影响，不能硬编码只识别 `localization-string-tables-...bundle`。应：

1. 识别 `settings.json`、catalog、hash 和 bundle provider 信息；
2. 解析 catalog 的 internal ID、provider、dependency、hash、CRC 和远程 LoadPath；
3. 下载或从 Unity Cache 收集所有依赖 bundle；
4. 对 bundle 内每个 SerializedFile 递归做对象级扫描；
5. 回写时同步处理 catalog/hash/CRC/签名或采用运行时覆盖，不能只替换 bundle 文件。

远程 Addressables、Unity Cloud Content Delivery 或自建 CDN 意味着安装包内可能只有 catalog 和 URL，真正文本首次运行才下载。仅扫描安装目录无法判定“0 文本”。

### 3.4 persistentDataPath、缓存、存档和 Mod

运行后生成的文本可能不在安装目录。Unity 官方列出的典型 `persistentDataPath` 包括：

- Windows：`%USERPROFILE%\AppData\LocalLow\<Company>\<Product>`；
- Linux：`$XDG_CONFIG_HOME/unity3d/<Company>/<Product>`，默认在 `~/.config`；
- macOS：常见于 `~/Library/Application Support/<Company>/<Product>`；
- Android：通常为 `/storage/emulated/<userid>/Android/data/<package>/files`；
- iOS：应用容器的 `Documents`。

还应检查：

- `Application.temporaryCachePath`、Unity AssetBundle Cache；
- BepInEx/MelonLoader/UnityModManager 的配置和翻译目录；
- Steam Workshop、游戏自己的 Mods/Plugins/CustomData 目录；
- 存档、聊天记录、玩家命名、任务缓存；
- Windows 注册表或平台对应存储中的 PlayerPrefs；
- WebGL 的 IndexedDB 浏览器缓存。

这些位置可能含“可复用的下发文本”，也可能只含玩家隐私数据。扫描前必须提示范围，默认不上传、不翻译玩家输入和身份信息。

### 3.5 移动端与 WebGL 包

Android APK/AAB/OBB/Play Asset Delivery 需要额外扫描：

- `assets/bin/Data/**`：Unity Player 数据；
- `assets/**`：StreamingAssets；
- `lib/<abi>/libil2cpp.so`、`libunity.so`、其他原生库；
- `resources.arsc`、`res/values*/strings.xml`：Android 插件界面文本；
- `classes*.dex`：Java/Kotlin 插件硬编码文本；
- OBB、Asset Pack、动态功能模块中的 UnityFS/自定义包。

iOS 包还应扫描：

- `Data/**`、Frameworks、PlugIns；
- `Info.plist`、`.strings`、`.stringsdict`、`.lproj`；
- Objective-C/Swift/原生库中的字面量；
- On-Demand Resources 或下载缓存。

WebGL 还应扫描：

- `.data`/WebData 内的 Unity 资源；
- `.wasm` 中的 UTF-8/UTF-16 字符串和 IL2CPP 数据；
- `.framework.js`、loader/config JavaScript；
- Service Worker、浏览器 Cache Storage、IndexedDB 中后下载内容。

## 4. Unity 序列化对象中的文本

### 4.1 最重要的原则：扫描所有对象的所有字符串叶节点

仅对白名单对象类型做扫描一定会漏。Unity 可以把开发者自定义的可序列化字符串存入几乎任何 MonoBehaviour/ScriptableObject 派生类型，包括第三方插件组件和 Timeline clip。

推荐算法：

1. 打开 SerializedFile/AssetBundle/WebFile/APK；
2. 遍历全部内部文件与全部对象；
3. 若类型树可用，递归遍历 `dict/list/array/managed reference`；
4. 收集每个 `string`，以及有字符串迹象的 `byte[]`；
5. 保存完整定位：容器链、SerializedFile 名、Path ID、Class ID、MonoScript、字段路径、数组索引；
6. 根据组件类型、字段名、相邻字段、对象名、locale 和引用关系打分；
7. 未达显示阈值的条目进入“低置信度候选库”，不能静默丢弃；
8. 类型树不可用时，再走原始字节、脚本恢复或运行时 hook 兜底。

建议的稳定定位键：

```text
<容器相对路径>!<内部SerializedFile>#<PathID>:<字段路径>
```

仅用字节偏移不稳定：重建 bundle、改变字符串长度或 Unity 版本差异都会让偏移变化。

### 4.2 TextAsset

Unity 官方列出的 TextAsset 导入扩展名包括 `.bytes`、`.csv`、`.fnt`、`.htm`、`.html`、`.json`、`.md`、`.txt`、`.xml`、`.yaml`。发布后的原扩展名可能不可见，内容位于 `TextAsset.m_Script`。

提取不能只“按行”：

- 先识别 BOM、UTF-8/16/32、Shift-JIS、GBK/GB18030、Windows-1252 等编码；
- 再按 JSON/XML/CSV/YAML/PO/字幕/剧情语言/键值格式递归解析；
- `.bytes` 可能是任意二进制、压缩、加密、数据库或序列化消息，不能默认当 UTF-8；
- HTML/Markdown 需保护标签、链接、代码块和变量；
- FNT/BMFont 多数是字体元数据，不是显示文案，应默认降权。

### 4.3 MonoBehaviour、ScriptableObject 与自定义序列化对象

常见显示字段名只是启发式，不是完整清单：

```text
text, m_Text, m_text, label, title, name, displayName, description,
dialogue, line, subtitle, tooltip, hint, prompt, message, content,
caption, question, answer, choice, objective, lore, bio, error,
format, template, prefix, suffix, singular, plural
```

还要处理：

- `List<string>`、嵌套结构、字典、数组；
- `[SerializeReference]` 管理引用和多态对象；
- 字符串被拆为 `char[]`、字节数组或整数码点；
- key 与 value 分列、ID 与文本分表；
- 文本片段、条件分支、复数和性别变体；
- 文本只存在于 inactive GameObject、未引用 Prefab 或备用语言表中；
- 被 strip 后缺 MonoScript 类型信息，导致标准类型树无法读取。

对未知对象，不要用“字段名不像 text”作为永久排除理由。字段名只是置信度特征，运行时是否进入显示 API才是更强证据。

### 4.4 Unity 内置与主流 UI 组件

应显式识别并建立组件级上下文：

- Legacy GUI：`GUIContent.text`、`GUI.Label/Button/Box/Window`，通常来自代码字面量；
- uGUI：`UnityEngine.UI.Text.m_Text`；
- uGUI InputField：初始 `text`，以及其 `placeholder` 引用的 Text/TMP 组件；
- 3D TextMesh：`UnityEngine.TextMesh.m_Text`；
- TextMesh Pro：`TMP_Text`、`TextMeshPro`、`TextMeshProUGUI`、`TMP_InputField`，常见序列化字段 `m_text`；
- UI Toolkit：UXML 的 `text`、`tooltip`、自定义属性，运行时 `TextElement.text`、`Label`、`Button`、`TextField`；
- 自定义 UI：NGUI `UILabel`、FairyGUI、NoesisGUI、Coherent/HTML UI 等。

初始序列化值可能只是占位文本，真实文字在 `Awake/Start/OnEnable` 或数据绑定后覆盖。因此既要提取静态字段，也要运行时记录最终赋值。

### 4.5 场景、Prefab、Timeline、Playable 与动画相关资产

文本可能位于：

- 场景内 UI 组件；
- 未激活对象、隐藏菜单、失败结局和辅助功能页面；
- Prefab 与 Prefab Variant 的默认字段；
- ScriptableObject 数据库；
- Timeline 的自定义 Track/Clip/Marker/Signal payload；
- Cinemachine/教程/任务插件的配置对象；
- Animator StateMachineBehaviour 的序列化字段；
- Visual Scripting/Bolt 图节点参数；
- Shader/材质属性中的极少数调试标签或自定义 UI 值。

应遍历对象内容，不应只根据类名排除 `Timeline`、`Playable` 或 `VisualScripting`。类名是噪音判定特征，但自定义 clip 完全可能保存字幕。

`GameObject.m_Name`、资源名和场景名通常不是玩家显示文本，但部分游戏会直接把对象名当 UI/物品名使用。建议默认作为低置信度候选，若运行时调用链或重复关系证明被显示，再升级。

### 4.6 Unity Localization 包

Unity Localization 的核心关系为：

- String Table：某个 Locale 的所有显示值；
- Shared Table Data：所有语言共享的 key 名和稳定 ID；
- String Table Collection：编辑器侧集合，发布包里重点是各表和共享数据对象；
- `LocalizedString`：以 table/entry 引用文本；
- Smart String：包含变量、复数、性别、列表和条件语法的模板。

正确提取方式：

1. 识别 `m_LocaleId.m_Code`、`m_TableData`、`m_Id`、`m_Localized`，不要依赖对象名；
2. 用 SharedTableData 的 key/ID 与各 locale 表关联；
3. 优先选择真实源语言，而不是假设英语永远是源语言；
4. 若只有目标语言或回退语言，也要保留而不是整组跳过；
5. Smart String 必须做语法解析或至少精确保护所有 format item；
6. 保留 Entry Metadata、Shared Metadata、注释、字符限制与变量说明；
7. 回写按稳定 Entry ID，不按行号或数组位置；
8. Addressables 表回写后同步校验 bundle、catalog/hash/CRC。

### 4.7 第三方本地化与剧情系统

不可能靠固定类型清单覆盖所有插件，但可建立指纹适配层：

- **I2 Localization**：LanguageSource/TermData、CSV 导入导出、复数和参数；
- **Lean Localization**：Phrase/Translation 等 ScriptableObject/组件；
- **Fungus**：Flowchart、Block、Say/Menu 等命令常序列化在 MonoBehaviour 中；
- **Ink**：源 `.ink`，发布时常见编译后的 JSON/TextAsset；
- **Yarn Spinner**：`.yarn`、编译产物、String Table/CSV、line ID；
- **Pixel Crushers Dialogue System**：数据库 ScriptableObject、CSV、Lua 条件和本地化字段；
- **Adventure Creator、NodeCanvas、Behavior Designer、Dialogue System 类插件**：自定义对象图；
- **NGUI/FairyGUI/Noesis/HTML UI**：自定义 bundle、XML、包文件或运行时 setter。

识别插件的线索包括程序集名、MonoScript 全名、字段结构、资源路径和已知魔数。插件适配器应建立在“通用类型树递归”之上，而不是替代通用扫描。

## 5. 普通文件、数据库和自定义二进制

### 5.1 扩展名必须扩充，但魔数比扩展名更可靠

建议至少识别：

```text
.json .json5 .jsonl .ndjson .csv .tsv .psv
.xml .resx .xlf .xliff .tmx .html .htm .md
.txt .ini .cfg .conf .config .lang .loc .properties
.yaml .yml .toml .po .mo .arb
.srt .vtt .ass .ssa .ttml .lrc
.ink .yarn .yarnc .lua .js
.db .sqlite .sqlite3 .bytes .dat .bin
```

同时对所有文件做轻量魔数/熵/编码探测：真实游戏常把 UnityFS、ZIP、SQLite、JSON、MessagePack 或纯文本藏在 `.dat`、`.bytes`、`.pak` 甚至无扩展名文件中。

### 5.2 文本文件解析注意事项

- 编码：UTF-8 BOM/无 BOM、UTF-16 LE/BE、UTF-32、Shift-JIS、EUC-JP、GBK/GB18030、Big5、Windows-125x；
- 换行：CRLF/LF/CR，写回必须保留；
- CSV：分隔符、引号、转义、换行单元格、重复表头和注释；
- JSON：键可能是显示文本，也可能是 ID；不能统一丢弃或统一翻译；
- XML/HTML：属性、CDATA、tail text、实体、命名空间；
- INI/properties：值、节名、注释和转义；
- PO/MO：`msgctxt`、复数、模糊标记和编译后的 MO；
- XLIFF/TMX：源/目标语言、segment ID、inline code；
- 字幕：时间码、样式标签、说话人、换行和定位标签；
- 剧情脚本：命令、跳转、变量与自然语言必须由语法解析器区分。

### 5.3 SQLite 与数据库

SQLite 文件头为 `SQLite format 3\0`，可能没有 `.db` 扩展名。建议：

1. 只读打开并枚举所有表、视图和列；
2. 对 TEXT/BLOB 列抽样做语言和编码分析；
3. 用主键 + 表名 + 列名定位，不能用物理页偏移；
4. 检查 FTS 虚表、JSON 列和压缩 BLOB；
5. 若是 SQLCipher/自定义加密，从代码中的连接初始化、PRAGMA/key 调用或运行时已解密连接提取；
6. 回写用事务和完整性检查，并保留 schema、索引、触发器。

Realm、LevelDB、RocksDB、LiteDB 等需要对应读取库；也可以优先从游戏反序列化后的业务对象或运行时 UI 捕获，避免盲改数据库内部格式。

### 5.4 Protobuf、MessagePack、FlatBuffers 与自定义格式

此类文件没有通用的“所有字符串安全提取器”。完整路线是：

- 在 Mono DLL/IL2CPP dummy assembly 中找生成类型、字段编号和反序列化调用；
- 搜索 `.proto`、MessagePack key、FlatBuffers schema、magic/version；
- hook 文件读取之后、解密/解压之后、UI 格式化之前的对象；
- 保存 schema 字段路径和对象主键；
- 对未知 BLOB 做压缩签名、熵、重复块、UTF-8/16 串探测，但只作为候选；
- 禁止直接等长覆盖未知二进制字符串，除非格式已验证。

### 5.5 加密、压缩和自定义包

常见失败模式是“扫描器发现文件但认为全是二进制”。应把处理链建模为：

```text
容器识别 → 解包 → 解密 → 解压 → 反序列化 → 字符串分类
```

每一步都记录算法、key 来源、输入 hash 和父容器路径。若静态找不到 key，可 hook：

- `File.ReadAllBytes`/Stream.Read；
- AES/XOR/自定义 decrypt 返回点；
- GZip/Deflate/LZ4/Zstd 解压返回点；
- JSON/Protobuf/MessagePack 反序列化入口；
- `AssetBundle.LoadFromMemory` 和 `UnityWebRequestAssetBundle` 的输入缓冲区。

## 6. 代码中的文本

### 6.1 Mono 后端：不只扫描 Assembly-CSharp.dll

所有游戏自有程序集都可能含显示文本：

```text
*_Data/Managed/Assembly-CSharp.dll
*_Data/Managed/Assembly-CSharp-firstpass.dll
*_Data/Managed/Assembly-UnityScript.dll
自定义 asmdef 输出 DLL
第三方剧情/UI/本地化 DLL
热更新 DLL、Mods DLL、satellite resource assembly
```

应结合 `ScriptingAssemblies.json`、程序集引用图和引擎/框架黑名单识别游戏程序集，而不是只认固定文件名。

提取范围包括：

- IL `ldstr` 对应的 `#US` user string heap；
- 字段初始值、属性默认值和编译器生成状态机中的字面量；
- 字符串数组、格式模板、插值字符串片段；
- `switch`、错误消息、教程文本、GUIContent；
- 嵌入的 Manifest Resource、`.resources`、JSON/XML/TextAsset；
- satellite assembly 的本地化资源；
- 反射加载、Base64、压缩/加密常量。

最大的误报来源是日志、异常、网络协议、SQL、路径和开发调试字符串。最强的显示证据是调用溯源，例如字面量或字段最终流入：

- `Text.text`、`TMP_Text.text`、`TextMesh.text`；
- `GUIContent`、`GUI.Label/Button/Box/Window`；
- `TextElement.text`；
- 本地化表 API 或第三方 UI setter；
- 对话/字幕/任务管理器的公开方法。

回写 `#US` 堆常有长度和 token 稳定性风险。更稳妥的方法通常是 IL 重写、资源覆盖或运行时替换，而不是原地固定容量覆盖。

### 6.2 IL2CPP 后端

常见文件：

- Windows：`GameAssembly.dll` + `*_Data/il2cpp_data/Metadata/global-metadata.dat`；
- Android：`libil2cpp.so` + APK 内 metadata；
- Linux/macOS/iOS：相应 ELF/Mach-O/native binary + metadata；
- WebGL：WASM + metadata/打包数据，布局随版本变化。

字符串字面量通常由 metadata 中的 literal 表和数据区定位，但不能假设所有版本都用同一结构。完整流程应：

1. 验证 metadata magic/version，不按单一版本硬编码；
2. 从 native binary 找 code/metadata registration；
3. 交叉验证 literal count、offset、length、UTF-8 边界；
4. 用 Il2CppDumper/Il2CppInspector/Cpp2IL 类工具恢复 dummy assemblies 和类型信息；
5. 将字符串与方法/类型/调用点关联，提升显示文本置信度；
6. 扫描 runtime metadata 以外的 native string、嵌入资源和自定义数据；
7. 遇到 metadata 加密、壳、重排或运行时解密时，从内存 dump 或解密函数返回点获取；
8. 回写优先用运行时替换；原地改 literal 必须处理长度、偏移、校验和与保护。

只读 `global-metadata.dat` 会漏掉：运行时拼接结果、native plugin 字符串、网络文本、嵌入资源、加密数据以及不走字面量池的字符数组。

### 6.3 原生插件和可执行文件

扫描 `Game.exe`、`UnityPlayer`、`GameAssembly`、`Plugins/*.dll/*.so/*.dylib`、Framework 和平台插件：

- PE string table、version/resource section、dialog/menu/string resources；
- ELF/Mach-O 只读数据段；
- UTF-8、UTF-16 LE/BE、UTF-32 字符串；
- Objective-C selector/NSString、JNI/Java bridge 文本；
- 第三方 SDK 登录、支付、隐私和错误提示；
- 嵌入 HTML/JS/JSON/证书旁的资源包。

普通 `strings` 输出只能作为候选。需要 xref/反汇编、导出函数、资源节类型和运行时调用来判断是否会显示。不要自动改引擎 DLL 中的普通字符串。

### 6.4 Lua、JavaScript、HybridCLR 与热更新脚本

脚本可能是明文，也可能字节码、加密或封装在 AssetBundle/TextAsset 中：

- Lua：源文件、LuaJIT bytecode、自定义加密脚本；
- JavaScript/TypeScript 产物、Puerts/XLua/ILRuntime；
- HybridCLR/ILRuntime 热更新 DLL；
- 自研虚拟机脚本和剧情 DSL。

应从加载器入手：追踪脚本文件清单、解密器、`Load`/`DoString`/assembly load，以及脚本层 UI setter。单独增加 `.lua` 扩展名远远不够。

## 7. 运行时才出现的文本

### 7.1 动态赋值和数据绑定

以下内容静态扫描可能只能看到片段或 key：

- `"HP: " + hp`、插值字符串和 StringBuilder；
- 本地化 key 在运行时查表后的最终值；
- 复数、性别、条件、随机台词；
- 玩家名、物品属性和服务器数据拼成的句子；
- UI Toolkit 数据绑定、MVVM/响应式框架；
- 程序生成的字母/单词/谜题文本；
- 反射、表达式树、Lua/JS 运行结果。

运行时采集器应 hook 或轮询：

- uGUI `Text.text`；
- TMP `TMP_Text.text`、`SetText`；
- `TextMesh.text`；
- UI Toolkit `TextElement.text`；
- IMGUI `GUIContent` 和 GUI 绘制入口；
- 第三方 UI 的 label/text setter；
- Unity Localization 和第三方本地化 API 返回值；
- 对话、字幕、通知、任务系统的中间层。

每条采集记录至少包括：原文、组件类型、GameObject 层级、场景、组件实例、调用栈或调用点、首次/最后出现时间、出现次数、屏幕区域、当前 locale。

### 7.2 运行时 hook 的盲点和补救

- 只 hook 属性 setter 会漏掉直接写内部字段或 native 更新；可加 `OnWillRenderCanvas`/帧末 UI 树枚举。
- 对象池会重复使用组件；定位键要包含层级模板和调用点，不能只用 instance ID。
- 同一句英文在不同语境可能需不同译文；必须保留调用点和场景上下文。
- 文本可能一帧即逝；需事件级捕获，不能只定时截图。
- Anti-cheat/DRM 可能禁止注入；此时采用代理、日志、截图 OCR 或官方 Mod 接口。
- IL2CPP 泛型、内联和 AOT 会让 hook 点不同；需要按 Unity/TMP/平台版本适配。

### 7.3 网络、Remote Config 和热更新

运行时可能从以下渠道取得文字：

- UnityWebRequest/HttpClient/WebSocket；
- Addressables remote catalog/bundle；
- Unity Remote Config、Cloud Content Delivery；
- Firebase/PlayFab/自研后端；
- 新闻、活动、公告、每日任务、客服、聊天；
- Steam/EOS/主机平台成就、Rich Presence、商品和用户生成内容。

推荐优先从应用层捕获已解密响应，而不是破坏 TLS：

1. hook UnityWebRequest 完成回调、DownloadHandler 数据；
2. hook JSON/Protobuf 反序列化返回对象；
3. 记录 URL 模板、内容类型、locale、ETag/hash 和缓存路径；
4. 对远程 bundle 进入正常 Unity 资源扫描链；
5. 区分官方静态文案、实时用户内容和隐私数据；
6. 离线回放响应验证提取覆盖。

### 7.4 系统和平台生成文本

下列文字可能根本不由 Unity 游戏资源控制：

- Steam/EOS/主机平台 overlay、成就、商店和邀请；
- Android/iOS 权限框、推送、原生登录/支付 SDK；
- Windows/macOS 文件选择器、错误对话框；
- 广告 SDK、网页支付、内嵌浏览器；
- 外部启动器和更新器。

提取器应把它们标记为“外部来源”，引导检查平台后台、本机插件资源或网页，而不是错误报告成 Unity 资源漏扫。

## 8. 像素、视频、几何体和音频中的文本

### 8.1 Texture2D、Sprite 和 SpriteAtlas

常见位置：标题 Logo、主菜单按钮、地图、海报、书信、教程图、漫画、扫描件、键位图、载入画面、成就图标。

流程：

1. 从 SerializedFile/AssetBundle 连同 `.resS` 导出 Texture2D；
2. 重建 SpriteAtlas 切片、旋转、裁边和 alpha；
3. OCR 多尺度、多旋转、多语种识别；
4. 感知哈希去重，但保留所有资源引用位置；
5. 把 OCR 框、置信度、图片路径、Sprite 名和引用场景写入候选库；
6. 人工确认后做图片重制或运行时覆盖。

OCR 不能只跑整张纹理：图集内小字必须按 Sprite rect 切出并放大。压缩伪影、描边、弯曲文字和艺术字体需要图像预处理与人工复核。

### 8.2 视频与 RenderTexture

- 先查同名 `.srt/.vtt/.ass/.ttml` 或独立字幕 TextAsset；
- 对本地/远程视频按镜头变化和字幕区域抽帧 OCR；
- 检测硬字幕的出现/消失时间，合并连续相同 OCR；
- 若文字由游戏实时绘制到 RenderTexture，UI hook 或帧捕获更合适；
- 远程视频需记录 URL、清晰度和 locale 变体。

### 8.3 Mesh、SVG、矢量路径和自定义 Shader

文字可能已转为：

- 3D Mesh 顶点；
- SVG/矢量路径；
- 粒子系统或逐字 Sprite；
- Shader 程序生成的数码管/点阵字；
- 图标字体的 glyph 组合。

这类资源里不一定存在可恢复字符串。可靠办法是渲染结果 OCR + 资源引用追踪；若需汉化，通常要重制资产或在其上覆盖动态文本。

### 8.4 音频对白与中间件

没有字幕的语音也属于“玩家接收的语言内容”：

- Unity AudioClip；
- StreamingAssets 中 WAV/OGG/MP3；
- Wwise `.bnk/.wem`、SoundBanksInfo XML/JSON；
- FMOD `.bank`/`.strings.bank`；
- CriWare/ADX/HCA 等中间件；
- 远程语音流。

音频事件名和 strings bank 通常只是资源标识，并不等于对白原稿。需解包音频、ASR、说话人/时间轴对齐，并与剧情触发器或事件 ID 关联。ASR 结果应标为低于正式字幕的证据等级。

## 9. 推荐的“近全覆盖”提取架构

### 9.1 阶段 A：无损文件清单

对游戏根目录、平台包、可选用户数据目录建立 inventory：

- 相对路径、大小、mtime、SHA-256；
- 扩展名、魔数、MIME 猜测、熵、编码猜测；
- 压缩/容器父链；
- Unity 版本、脚本后端、平台和架构；
- 只读失败、权限、损坏或超限原因。

任何未读取文件都必须出现在 coverage report 中，状态为 `unsupported/blocked/error`，不能静默跳过。

### 9.2 阶段 B：递归解包与格式路由

```text
ZIP/APK/OBB/Asset Pack/自定义包
  ├─ 普通文本/表格/字幕/剧情格式
  ├─ SQLite/结构化二进制
  ├─ UnityFS/SerializedFile/WebFile
  ├─ Managed assemblies/resources
  ├─ IL2CPP/native/WASM
  └─ Texture/Video/Audio → OCR/ASR 队列
```

设置递归深度、总展开大小和压缩炸弹保护，但达到限制时要记录未扫范围。

### 9.3 阶段 C：候选发现与证据分级

建议分四档：

| 置信度 | 证据 |
|---|---|
| A：已显示 | 运行时进入 UI/字幕 API，或 OCR 确认屏幕出现 |
| B：强显示 | Localization StringTable value、UI 组件 text、明确 dialogue/title/description 字段 |
| C：可能显示 | 自定义对象自然语言、代码字面量流入可疑业务方法、TextAsset 内容 |
| D：低置信候选 | 对象名、资源名、原生 strings、未知 BLOB 中可打印串 |

过滤不是删除：所有档位都保留原始记录，默认翻译队列只开放 A/B/C 中通过结构校验的条目。

### 9.4 阶段 D：统一中间表示

每条文本建议保存：

```json
{
  "source_text": "Press {key} to open",
  "source_language": "en",
  "role": "interaction_prompt",
  "confidence": "A",
  "source_kind": "runtime_tmp",
  "locator": {
    "file": "Game_Data/sharedassets0.assets",
    "container_chain": [],
    "serialized_file": "sharedassets0.assets",
    "path_id": 12345,
    "script_type": "TMPro.TextMeshProUGUI",
    "field_path": "m_text"
  },
  "context": {
    "scene": "House",
    "hierarchy": "Canvas/HUD/Prompt",
    "callsite": "DoorPrompt.Show",
    "neighbors": []
  },
  "syntax": {
    "placeholders": ["{key}"],
    "rich_text": []
  }
}
```

文件静态记录和运行时记录应能合并：同一 source 的 locator、callsite、UI hierarchy 和截图共同构成翻译语境。

### 9.5 阶段 E：运行时覆盖采集

自动遍历至少应覆盖：

- 首次启动、语言选择、主菜单、设置、键位、辅助功能；
- 新游戏教程、HUD、暂停、背包、地图、任务、对话与选择；
- 成功/失败/死亡/结局；
- 存档/读档、多人、商店、成就、制作人员；
- 不同分辨率、输入设备、角色性别/数量、难度；
- 断网、服务器错误、无权限、存档损坏等异常路径；
- 所有场景、可选任务、隐藏菜单和 DLC。

每次测试结束计算“新文本发现曲线”。连续多轮完整走查没有新增，只能说明动态覆盖趋稳，不能数学证明服务器未来不会下发新文案。

### 9.6 阶段 F：结果侧 OCR 审计

对关键页面和自动探索录屏抽帧，OCR 后与已知文本库比对：

- OCR 命中已知 source/translation：已覆盖；
- OCR 发现新自然语言：创建遗漏候选；
- 屏幕显示原语言但数据库有译文：写回/字体/运行时替换失败；
- OCR 无法识别但人工看到文字：进入人工资产队列。

这一步能发现“提取成功但实际没替换”和“位置未知但屏幕确实出现”两种问题。

## 10. 漏检根因诊断表

| 现象 | 最可能根因 | 下一步 |
|---|---|---|
| 某场景所有 UI 都漏 | `levelN/mainData/data.unity3d` 未被发现 | 按魔数扫描无扩展名 SerializedFile/Bundle |
| TMP 文本漏、uGUI 正常 | 只识别内置 Class ID，没用 MonoScript/类型树 | 识别 TMP MonoBehaviour + 运行时 setter |
| TextAsset 只有部分行 | 编码/格式/多行单元格判断错误 | 编码探测 + 专用格式解析 |
| Addressables 表漏 | 只扫固定文件名或只扫本地 bundle | 解析 catalog、依赖和远程缓存 |
| 原始表只有 key 没显示值 | 值在另一 locale 表/远程表/运行时 API | 关联 SharedTableData 和全部 locale |
| Mono 游戏菜单漏 | DLL 白名单太窄或过滤短词 | 扫全部游戏程序集并做 UI 调用溯源 |
| IL2CPP 结果很少 | metadata 版本/加密/注册定位失败 | native 交叉定位、内存 dump、运行时 hook |
| 首次进入页面才出现 | 动态生成/网络/解密 | UI setter + 文件/网络/反序列化 hook |
| 图片按钮仍是英文 | 文字烘焙进 SpriteAtlas | 切片 OCR + 图片重制 |
| 过场动画仍是英文 | 硬字幕或远程视频 | 字幕文件检查 + 抽帧 OCR |
| 语音有内容但无条目 | 无字幕资源 | AudioClip/bank 解包 + ASR |
| 只漏两三个短按钮 | 最小长度/词法过滤过强 | 用 UI 字段和运行时证据覆盖语言阈值 |
| 翻译后 key 失效 | 把本地化键/InputAction/资源路径当显示值 | 按字段角色和调用关系保护 key |
| 文件存在但扫描器没报告 | 扩展名白名单、目录黑名单或读取异常 | inventory 全量报告，不允许静默跳过 |
| 同一英文需要多个译法 | 仅按 source 文本去重 | locator/callsite/scene 参与语境键 |

## 11. 对当前项目实现的直接差距分析

根据 2026-08-08 仓库代码，当前工具已经具备这些重要基础：

- 松散 JSON/CSV/TSV/XML/TXT/INI/CFG/LANG/properties；
- `.assets`、常见 AssetBundle 和部分无扩展名 Unity bundle；
- TextAsset、MonoBehaviour、ScriptableObject、类型树字符串；
- Unity Localization StringTable 和 Addressables 写回校验；
- Mono DLL `#US`/UI 调用相关识别；
- IL2CPP `global-metadata.dat` 字符串字面量；
- 现有字体与写回验证链。

最可能造成“大量文本仍无法识别”的缺口按优先级如下。

### P0：会造成整类文本完全缺失

1. **文件发现仍主要依赖扩展名**：缺 YAML/PO/MO/XLIFF/字幕/Ink/Yarn/SQLite 等，也会漏掉伪装在 `.dat/.bin/.bytes/无扩展名` 的内容。
2. **Unity 资源后缀和布局仍是有限集合**：需要对所有文件先做魔数识别，并递归处理 APK/WebFile/嵌套 bundle，而不是只看 `.assets/.ab/.unity3d/.bundle/.pak`。
3. **运行时捕获缺失**：动态 UI、拼接、解密、服务器下发、Remote Addressables 无法靠现有静态扫描完整得到。
4. **图片/视频/音频内容没有 OCR/ASR 管线**。
5. **用户数据与 Unity Cache 未进入可选扫描范围**。

### P1：会造成常见 UI/剧情漏检

1. 对所有类型树字符串叶节点建立统一、无损的候选库，并保留低置信度内容；
2. 显式识别 UI Toolkit、TextMesh、TMP、InputField placeholder、NGUI 等组件关系；
3. 支持 SQLite 和 TextAsset 内的嵌套格式/编码探测；
4. 解析 Addressables catalog 和远程依赖，不依赖 Localization bundle 文件名；
5. 扫描所有游戏自有 Managed assemblies、嵌入资源和 satellite assemblies；
6. 扫描 Timeline/Playable/Visual Scripting/第三方剧情插件对象。

### P2：提高复杂游戏覆盖率

1. IL2CPP 多 metadata 版本、保护和运行时 dump；
2. 原生 PE/ELF/Mach-O/WASM 文本及调用点；
3. Protobuf/MessagePack/FlatBuffers/Lua/热更新脚本适配；
4. Wwise/FMOD/CriWare 音频与事件关联；
5. Android/iOS 原生插件本地化资源。

### P3：用结果证明覆盖，而不是只证明扫描过文件

1. 运行时 UI 文本日志；
2. 自动化页面/场景走查；
3. 截图/录屏 OCR 与静态语料差集；
4. 每文件、每容器、每对象和每运行路径的 coverage report；
5. “读取失败/格式未知/达到限制/远程未下载”必须成为显式阻塞项。

## 12. 完整性验收标准

不能把“扫描到 N 条”当完成。建议同时满足：

### 静态覆盖

- inventory 中 100% 文件有明确状态；
- 所有归档/Unity 容器有递归展开记录；
- 所有 SerializedFile 对象都有“已解析/无类型树/失败”状态；
- 所有游戏程序集和嵌入资源都有扫描状态；
- 所有未知高熵/高可打印率文件进入人工或动态分析队列；
- 不存在静默忽略的目录黑名单。

### 动态覆盖

- 所有 UI 框架的 setter 或帧末 UI 树被覆盖；
- 关键场景和异常路径都有运行记录；
- 远程 catalog/bundle/配置已下载或明确标注未覆盖；
- 多轮探索的新文本增长趋近于零；
- 运行时文本能回连静态 locator 或明确标为 dynamic-only。

### 结果覆盖

- OCR 差集无未解释原语言文本；
- 视频/图像/几何文字有处理结论；
- 无字幕语音有“无需翻译/已有字幕/ASR 待处理”结论；
- 平台/系统外部文本与游戏内文本分开列出；
- 翻译后重新走查，未出现原文回退、字体方框、截断或模板损坏。

## 13. 推荐实施顺序

若目标是最快显著提升识别率，建议按以下顺序迭代：

1. **全文件 inventory + 魔数路由 + 未扫描原因报告**；
2. **Unity 容器递归与全对象类型树候选库**；
3. **扩充普通格式、字幕、SQLite、Ink/Yarn**；
4. **全 Managed assembly + embedded resources + UI 调用溯源**；
5. **运行时 uGUI/TMP/TextMesh/UI Toolkit/IMGUI 捕获**；
6. **Addressables catalog/远程缓存/网络响应捕获**；
7. **IL2CPP 多版本、内存解密与原生层**；
8. **Texture/Sprite/Video OCR 与 Audio ASR**；
9. **自动走查 + coverage report + OCR 差集闭环**。

前三步解决“文件和对象根本没被发现”；第四至第七步解决“文本不以普通资源存在”；最后两步解决“屏幕/声音中有内容但没有可恢复字符串”的终极盲区。

## 14. 研究资料与工具参考

以下资料用于交叉核对本指南中的 Unity 资源布局、Localization/Addressables、代码后端和提取方案。链接访问核对日期为 2026-08-08。

### Unity 官方

1. [Unity Manual — Text assets](https://docs.unity3d.com/Manual/class-TextAsset.html)
2. [Unity Scripting API — TextAsset](https://docs.unity3d.com/ScriptReference/TextAsset.html)
3. [Unity Manual — Include additional files in a build (StreamingAssets)](https://docs.unity3d.com/Manual/StreamingAssets.html)
4. [Unity Scripting API — Application.streamingAssetsPath](https://docs.unity3d.com/ScriptReference/Application-streamingAssetsPath.html)
5. [Unity Scripting API — Application.persistentDataPath](https://docs.unity3d.com/ScriptReference/Application-persistentDataPath.html)
6. [Unity Manual — Introduction to the Resources system](https://docs.unity3d.com/Manual/LoadingResourcesatRuntime.html)
7. [Unity Manual — Introduction to AssetBundles](https://docs.unity3d.com/Manual/AssetBundlesIntro.html)
8. [Unity Manual — Loading assets from AssetBundles](https://docs.unity3d.com/Manual/AssetBundles-Native.html)
9. [Unity Manual — Asset metadata](https://docs.unity3d.com/Manual/AssetMetadata.html)
10. [Unity Manual — UnityYAML](https://docs.unity3d.com/Manual/UnityYAML.html)
11. [Unity Localization 1.5 — String Tables](https://docs.unity3d.com/Packages/com.unity.localization@1.5/manual/StringTables.html)
12. [Unity Localization 1.5 — Smart Strings](https://docs.unity3d.com/Packages/com.unity.localization@1.5/manual/Smart/SmartStrings.html)
13. [Unity Localization 1.5 — LocalizedString API](https://docs.unity3d.com/Packages/com.unity.localization@1.5/api/UnityEngine.Localization.LocalizedString.html)
14. [Unity Manual — IL2CPP scripting backend](https://docs.unity3d.com/Manual/IL2CPP.html)
15. [Unity Manual — Managed code stripping](https://docs.unity3d.com/Manual/ManagedCodeStripping.html)
16. [Unity TextMesh Pro package manual](https://docs.unity3d.com/Packages/com.unity.textmeshpro@3.0/manual/index.html)
17. [Unity Manual — UXML](https://docs.unity3d.com/Manual/UIE-UXML.html)

### 资源分析与逆向工具

18. [UnityPy — Unity asset extractor/editor with typetree support](https://github.com/K0lb3/UnityPy)
19. [AssetRipper — Unity game file analysis and export](https://github.com/AssetRipper/AssetRipper)
20. [AssetRipper Documentation](https://assetripper.github.io/AssetRipper/)
21. [UABEA — Unity Assets Bundle Extractor Avalonia](https://github.com/nesrak1/UABEA)
22. [AssetRipper TypeTreeDumps](https://github.com/AssetRipper/TypeTreeDumps)
23. [Il2CppDumper](https://github.com/Perfare/Il2CppDumper)
24. [dnSpy](https://github.com/dnSpy/dnSpy)
25. [Microsoft Learn — IL `ldstr`](https://learn.microsoft.com/en-us/dotnet/api/system.reflection.emit.opcodes.ldstr)
26. [XUnity.AutoTranslator](https://github.com/bbepis/XUnity.AutoTranslator)

### 剧情、本地化与音频中间件

27. [Ink](https://github.com/inkle/ink)
28. [Yarn Spinner Documentation](https://docs.yarnspinner.dev/)
29. [Pixel Crushers Dialogue System — Localization](https://www.pixelcrushers.com/dialogue_system/manual2x/html/localization.html)
30. [Audiokinetic Wwise — Localizing your project](https://www.audiokinetic.com/library/edge/?source=Help&id=localizing_project)
31. [FMOD Studio — Dialogue and localization](https://www.fmod.com/docs/2.02/studio/dialogue-and-localization.html)

## 15. 最终边界声明

“所有文本都不要遗漏”可以作为工程目标，但不能被单次静态扫描绝对证明。只要游戏允许服务器在未来下发新内容、允许用户输入，或把文字烘焙在未知视觉/音频输出中，文本集合就是开放的。

可验证、可交付的定义应是：

> 对当前游戏版本、当前已取得的本地与远程资源、指定平台和已执行的运行路径，所有文件与对象都有扫描状态；所有实际出现的文字都被 UI hook 或 OCR/ASR 观察到；所有未覆盖来源都在报告中明确列出，不存在静默遗漏。

这比“宣称支持若干扩展名或对象类型”更接近真正的完整识别。
