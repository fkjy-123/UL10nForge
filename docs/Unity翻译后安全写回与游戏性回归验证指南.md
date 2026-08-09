# Unity 翻译后安全写回与游戏性回归验证指南

> 研究日期：2026-08-08  
> 适用范围：Unity Mono、IL2CPP、AssetBundle、Addressables、本地化表、运行时注入和多平台发布物  
> 目标：让“译文写入成功”与“游戏仍然可启动、可操作、可存档、可继续游玩”同时成立。

## 1. 核心结论

汉化写回不是普通的字符串替换。对 Unity 游戏而言，一段字符串可能同时承担：

- 玩家显示文本；
- 本地化 key、Entry ID、InputAction 名、资源地址或脚本标识；
- 格式模板、占位符、富文本标签、Smart String 语法；
- SerializedFile 的变长字段；
- Mono `#US` 或 IL2CPP literal 池中的固定容量数据；
- Addressables catalog 使用的 bundle CRC、hash 或远程地址关联；
- UI 布局测量、自动换行、按钮命中区域和输入提示语义。

因此，安全写回必须同时验证五类不变量：

```text
结构不变量       文件/对象仍能被 Unity 解析
引用不变量       Path ID、PPtr、脚本、依赖和地址仍能解析
语义不变量       key、占位符、输入绑定、格式语法未被破坏
渲染不变量       字体、字形、材质、布局和文本框仍可显示
行为不变量       启动、按键、场景、存档、网络和游戏流程仍正常
```

只通过文本条目数量、文件存在或“UnityPy 可以重新打开”都不足以证明写回安全。

## 2. 写回风险速查表

| 写回对象 | 常见风险 | 默认策略 | 必须验证 |
|---|---|---|---|
| JSON/XML/CSV/TXT | 编码、换行、转义、键值错位 | 保留原格式与编码，原子写入 | 重新解析 + 键集合/行数/字段数一致 |
| SQLite/数据库 | schema、索引、事务、加密、BLOB 偏移 | 事务写回或运行时覆盖 | integrity_check + 查询回归 |
| TextAsset | `m_Script` 字节编码、嵌套格式 | 按原始字节重建 | 重新打开对象 + 格式解析 |
| MonoBehaviour/ScriptableObject | 类型树字段路径、数组、PPtr、ManagedReference | 按类型树路径写回 | 对象级重开 + 引用解析 |
| StringTable | Entry ID、locale、Smart String | 按稳定 ID 写回 value | 各 locale 表重开 + key/ID 集合不变 |
| SerializedFile | string 长度头、4 字节对齐、对象大小 | 让序列化器重建 | 全对象枚举 + 未修改对象字节/语义对比 |
| AssetBundle | 压缩方式、内部文件、依赖、CRC | 保留原压缩模式重建 | `LoadFromFile`、依赖加载、CRC/catalog |
| Addressables | catalog、hash、CRC、remote URL、缓存 | bundle 与 catalog 成组更新 | Addressables 运行时加载/缓存清空测试 |
| Mono `#US` | ECMA-335 heap 容量、token、元数据索引 | 优先运行时替换；固定容量才原地改 | CLR 装载 + 相关方法调用 |
| IL2CPP literal | metadata 版本、offset、native registration、保护 | 优先运行时 hook/补丁 | 启动、AOT 方法、崩溃和字符串引用 |
| Legacy Font | TTF、字体度量、动态字形 | 替换完整 Font 数据 | 中文字形显示 + 布局/输入 |
| TMP_FontAsset | glyph table、character table、atlas、material | 版本匹配的字体资产替换 | TMP 组件渲染、Fallback、材质 |
| 运行时注入 | hook 冲突、线程、GC、生命周期、Anti-cheat | 可禁用、可记录、只改显示层 | 启动/场景/退出/长时间运行 |
| APK/IPA/WebGL | 签名、压缩、资源清单、缓存 | 最后一步重新打包/签名 | 安装、启动、下载和平台 API |

## 3. 写回前的输入保护和发布模型

### 3.1 永远写副本，不原地覆盖玩家原游戏

安全目录结构应类似：

```text
原游戏/                         # 只读输入
项目数据/                       # 扫描清单、译文、校验和、日志
工作区/.staging-<id>/           # 临时副本和写回中间产物
游戏_汉化/                      # 通过验证后才发布
备份/.游戏_汉化.backup-<id>/   # 原输出版本，可恢复
```

写回前保存：

- 游戏根目录相对路径清单；
- 每个输入文件 SHA-256、大小和 mtime；
- Unity 版本、平台、架构、Mono/IL2CPP 后端；
- 解析器版本、写回器版本、字体载荷版本；
- 译文数据库版本和写回计划 hash。

如果扫描后原游戏文件变化，必须拒绝写回，避免“扫描的是 A，写回的是 B”。

### 3.2 分阶段提交，不能半成品发布

推荐流水线：

```text
preflight
  → 复制原游戏到 staging
  → 静态文本写回
  → Unity 资源/程序集写回
  → 字体和运行时载荷部署
  → 结构/引用/格式重开验证
  → 生成验证报告
  → 原子替换发布目录
  → 启动冒烟与游戏性回归
```

任何必需阶段失败，删除 staging 或保留供诊断，但不得把它发布为“可玩汉化版”。

### 3.3 原子发布、备份和回滚

发布目录替换应满足：

1. 新目录完成全部写回和验证后才切换；
2. 同一父目录内用临时目录/原子 rename，减少跨卷失败；
3. 旧输出先移动到带随机 ID 的备份目录；
4. 发布失败时恢复旧输出；
5. 文件锁、杀毒软件或进程占用导致恢复失败时，保留备份并明确提示路径；
6. 清理备份只能针对工具自己生成且路径经过校验的目录。

不要用未解析的通配符、用户输入路径或工作区根目录执行递归删除。

## 4. 写回前的统一语义保护

### 4.1 显示值、key、标识符必须分离

下列内容通常不能翻译：

- JSON/XML/CSV 字典键、Localization Entry ID、SharedTableData key；
- Input System 的 Action Map/Action 名、Control Path、binding path；
- Addressables address、label、internal ID、provider、catalog 字段；
- 场景名、Prefab 路径、资源名、程序集全名、TypeTree 字段名；
- Shader property、材质名、Animator 参数、Timeline track 名；
- URL、正则、SQL、脚本函数、枚举、GUID、哈希、文件扩展名；
- Wwise/FMOD/CriWare event/bank 名；
- 程序错误码、日志级别和协议字段。

最危险的错误是“看起来像英文，所以全部翻译”。必须使用来源、字段路径和调用点分级，而不是只看语言特征。

### 4.2 占位符、格式模板和富文本标签

写回前对原文和译文做多重结构比较：

```text
{0}、{name}、{count:plural:...}
%1、%s、%d、printf/Format 参数
<b>、</b>、<color=#...>、<sprite=...>、<link=...>
[i]、[/i]、[br]、换行转义、回车换行转义
Unity SmartFormat plural/gender/selector
Ink/Yarn/Fungus 命令、标签、跳转、变量
```

至少验证：

- 占位符名称、类型和出现次数一致；
- 富文本标签成对、顺序和嵌套合法；
- TMP 标签未被翻译为普通文字；
- 字面量换行转义与真实换行不混淆；
- `{}` 中的格式语法没有被中文标点替换；
- 转义后的 JSON/XML/CSV 仍能解析；
- 翻译器没有加入解释性前缀、引号或 Markdown。

### 4.3 按键交互为何最容易坏

常见错误及原因：

| 错误 | 结果 |
|---|---|
| 把 `menu.new_game`、`Submit`、`Player/Move` 当显示值翻译 | 查表、输入绑定或状态机找不到 key |
| 把 `[E]`、`<sprite name="button_a">`、`Enter` 翻译 | 玩家看到的键名与实际绑定不一致，或提示解析失败 |
| 翻译 `{key}`、`{0}`、`%s` | 格式化异常、空白、崩溃或字符串回退 |
| 改写 Input System control path，如 `<Keyboard>/e` | 绑定失效，按键完全无反应 |
| 破坏 `Press {0} to ...` 中 token 顺序 | 交互提示与实际输入错位 |
| 把 `open/close` 等动作词误当作代码标识符 | 质量门误放行或错误跳过真实提示 |
| 删除 TMP `<link>`、`<sprite>`、`<mark>` | 点击区域、图标或文本事件失效 |

建议把输入 token 拆成结构化事件保存：`kind=literal_glyph/semantic_input`、原始 token、显示形式、动作语义。翻译只修改自然语言片段。

## 5. 普通文本文件安全写回

### 5.1 编码和换行

- 从原始字节探测 BOM，不要依赖系统默认编码；
- 保留 UTF-8 BOM、UTF-16 LE/BE 和原始 EOL；
- 写回后重新读取，确认译文能以原编码解码；
- 无法编码的中文必须阻断写回，不能静默替换成 `?`；
- 保留文件末尾换行和最终空行数量；
- 不使用可能注入 BOM 或改变换行的管道式 PowerShell 写法处理源代码/资源。

### 5.2 JSON/XML/CSV

写回前后比较：

- 键集合完全一致；
- 数组顺序、对象数量和字段类型一致；
- 数字、布尔值、null、URL、GUID 未改变；
- XML namespace、属性和 CDATA 结构一致；
- CSV 列数、引号、分隔符、换行单元格一致；
- JSON 字符串只改变目标 value，不改变 key/path。

不要用正则表达式替换 JSON/XML。应解析为结构，再用保留格式的 writer 或最小范围 token patch。

### 5.3 SQLite 与自定义数据库

安全顺序：

1. 复制数据库并在副本上事务操作；
2. 记录 schema、user_version、表/列/索引/触发器；
3. 只改确认是显示值的 TEXT 列；
4. 对加密数据库使用游戏真实连接路径或运行时覆盖；
5. `PRAGMA integrity_check`、外键检查和应用查询回归；
6. 验证 WAL/SHM、journal 和文件权限；
7. 发现数据库由服务器重新同步时，改用运行时翻译层。

## 6. Unity SerializedFile、Scene、Prefab 和 AssetBundle 写回

### 6.1 变长字符串与对齐

Unity 序列化字符串通常包含长度头和 UTF-8 payload，后续字段按 4 字节边界对齐。错误地只覆盖旧字符串长度，或把新长度写成字符数而非字节数，会导致后续字段错位，表现为：

- 场景无法加载；
- 某个对象之后全部字段乱码；
- 按钮引用、Collider、Animator 或输入组件损坏；
- 只有特定平台/特定场景崩溃。

安全做法：

- 优先使用类型树/序列化器重建对象；
- 低层 patch 必须重算字节长度、对齐和对象边界；
- 保留外部 `.resS/.resource` 流的 offset/size 关系；
- 写回后重新打开 SerializedFile，枚举全部对象并检查未修改对象；
- 不把“字符串截断后能打开”当成功，截断可能改变任务/提示的语义。

### 6.2 Path ID、PPtr 和 MonoScript 引用

不要因为对象大小变化而重新分配 Path ID 或重排对象表。必须验证：

- 所有 `PPtr` 的 fileID/pathID 仍指向正确对象；
- MonoBehaviour 的 `m_Script` 仍指向原 MonoScript；
- Prefab、场景、AssetBundle container 和依赖表未丢失；
- ManagedReference 类型名、assembly name 和引用 GUID 未被翻译；
- SpriteAtlas、字体材质、Texture2D、AudioClip 的引用未断。

### 6.3 TextAsset 与自定义对象

TextAsset 的 `m_Script` 是可变长内容，适合重建，但必须保留原编码和内部格式。MonoBehaviour/ScriptableObject 应按完整字段路径写入，不能把未知对象序列化成只含已识别字段的新对象。

对于没有 TypeTree 的对象：

- 优先恢复 TypeTree 或使用能理解该 Unity 版本的工具；
- 仅有原始字节候选时，默认只读提取，不自动写回；
- 运行时 hook 通常比猜测字段偏移更安全。

## 7. AssetBundle 和 Addressables 的成组写回

### 7.1 AssetBundle 的三个一致性面

写回一个 bundle 后必须同时检查：

1. **内部 SerializedFile**：对象和类型树能重开；
2. **bundle 容器**：原压缩模式、块信息、目录和依赖仍有效；
3. **外部索引**：catalog、hash、CRC、远程 manifest 和依赖关系匹配。

Unity AssetBundle 依赖关系不是可选信息。只替换一个 bundle 而忘记依赖或压缩模式，可能出现材质丢失、字体缺失、场景加载卡住或 `CRC Mismatch`。

### 7.2 Addressables

Addressables 运行时可能使用：

- `catalog.json`/`catalog.bin`；
- `.hash` 文件；
- bundle CRC；
- internal ID、remote URL 和 provider；
- dependency bundle；
- Unity Cache 中旧版本内容。

安全策略：

- bundle 变化后重新计算 Unity 使用的 CRC；
- 只在确认 catalog 字段语义后更新对应 CRC，不做全文件盲替换；
- 同一旧 CRC 映射到多个不同新 CRC 时阻断；
- catalog、hash、bundle 必须成组发布；
- 清空旧 cache 后测试一次，保留已有 cache 再测试一次；
- 测试离线、本地、远程和 CDN 失败回退；
- 远程资源若无法重新签名/上传，采用运行时翻译或本地覆盖 provider。

### 7.3 AssetBundle CRC 与哈希的区别

- CRC 是加载校验的一种数值，不等于文件 SHA-256；
- catalog 中的 CRC 可能是 bundle 内容 CRC，而不是整个压缩文件字节 CRC；
- hash 用于缓存版本选择，改 bundle 但不改 hash 可能继续命中旧缓存；
- 服务器/CDN 可能还有 ETag、签名和 manifest 校验。

报告中必须分别记录 source/target 的 SHA-256、bundle content CRC、catalog hash 和最终加载结果。

## 8. Mono、IL2CPP 和原生字符串的写回风险

### 8.1 Mono `#US` heap

`.NET` 用户字符串由 metadata token 指向 `#US` heap。原地替换面临：

- 原始容量不足；
- UTF-16 字节长度与字符数不等；
- token/offset 被其他方法共享；
- ECMA-335 终止标记和特殊字符 flag；
- strong-name、签名或加载器校验；
- 翻译过长导致截断和语义损失。

优先级：

1. 运行时显示层替换；
2. IL 重写生成新字符串并更新 metadata；
3. 只有明确验证容量和格式时才固定容量 patch；
4. 每个修改后的程序集必须由 CLR/dnlib/Mono 重新加载并执行相关方法。

### 8.2 IL2CPP

IL2CPP 写回还涉及 metadata 版本、native registration、代码保护、内存解密、AOT 和平台签名。静态替换 literal 可能：

- 破坏 offset 或 metadata 表；
- 遇到固定容量不足；
- 只改 metadata 而 native 代码仍引用旧数据；
- 被启动器或完整性检查拒绝；
- 触发未对齐访问或特定平台崩溃。

除非有对应版本的解析、重建和回归证据，否则默认把 IL2CPP 文字写回标为 blocked，使用运行时 hook 或外部翻译映射。

### 8.3 原生二进制

PE/ELF/Mach-O 里的字符串通常不能仅靠长度覆盖。需要确认：

- 是否是资源节、只读常量还是指针表；
- 访问是否按 UTF-8/UTF-16/长度前缀；
- 是否有压缩、签名、校验和、ASLR/relocation 影响；
- 是否被多个调用点共享；
- 平台是否要求重新签名。

没有结构和调用点证据时只提取、不写回。

## 9. 字体、字形和布局：最常见的“文本已写回但不可玩”来源

### 9.1 Legacy Font

替换 TTF/Font 数据时要同步考虑：

- ascent、descent、line spacing、size；
- dynamic/static font 设置；
- fallback 字体；
- 粗体/斜体变体；
- 输入框光标、选区和 IME；
- 字体材质和 shader。

只替换字体文件，不验证中文字形，会出现方框、空白、光标错位或 UI 高度变化。

### 9.2 TMP_FontAsset

TMP 字体资产至少包含：

- character table；
- glyph table；
- atlas Texture2D；
- face info；
- material/shader；
- fallback font asset；
- atlas population mode 和 source font。

只把 character table 改成“有中文”，但 atlas 没有中文字形，结果仍是方框。不同 TMP/Unity 版本的 TypeTree 布局不能混用；字体 bundle、图集像素、材质和引用必须成组替换。

### 9.3 中文变长后的 UI 行为

翻译后常见行为问题：

- Button 文本超出边界，点击区域和视觉区域不一致；
- ContentSizeFitter/LayoutGroup 产生递归重建或布局抖动；
- CanvasScaler、不同分辨率和宽高比下截断；
- ScrollRect 内容高度未更新；
- TMP 自动缩放变得过小；
- 文本换行改变了按钮/触发器的布局；
- RTL、阿拉伯文、日文全角字符与中文混排造成测量异常。

必须在最小/最大窗口、16:9/21:9、720p/1080p/4K、UI 缩放和字体 fallback 组合下截图对比。

## 10. 写回后游戏性 Bug 的分类和定位

### 10.1 输入与按键

检查：

- Input System Action/Binding/Control Path 未被翻译；
- Prompt 中显示 token 与实际绑定一致；
- `Enter`、`Space`、`Return` 等既可能是动作词也可能是键名；
- 手柄 glyph、键盘 glyph、鼠标按钮和平台变体引用未断；
- 输入框 placeholder 与实际文本组件引用仍在；
- 暂停菜单、确认/取消、Back、Submit、Navigate 全路径可用。

### 10.2 场景和资源加载

- 场景名、Addressables address、label 未变；
- Build Settings 场景索引未变；
- bundle dependency、catalog、hash、CRC 一致；
- `Resources.Load` 路径、`AssetBundle.LoadAsset` 名称、Sprite 名未变；
- `m_Script`、GUID、Path ID 和 MonoScript 引用未变；
- 外部 `.resS/.resource` 流 offset/size 未错位。

### 10.3 任务、存档和数据

- 任务 ID、状态枚举、条件表达式未被翻译；
- 存档 schema、版本号、校验和、压缩和加密未改变；
- PlayerPrefs key 未改变；
- JSON/XML 数据键和数据库列名未改变；
- 运行时缓存没有继续使用旧 catalog/bundle；
- 新旧版本存档都能读取，失败时有安全回退。

### 10.4 脚本和事件

- 事件名、Animator 参数、Timeline Signal 名未改变；
- Lua/JS/热更新脚本命令和变量未改变；
- 正则、SQL、URL、资源地址未改变；
- 富文本 link ID、sprite name、material preset 未改变；
- 只翻译显示字段，不翻译反射查找的类型/成员名。

## 11. 分层验证闸门

### Gate 0：写回计划审计

每个条目在进入写回队列前必须有：

- 唯一 locator；
- 原文 hash；
- 译文 hash；
- 来源类型和置信度；
- 占位符/标签/input token 比较结果；
- 写回器能力等级：safe、bounded、runtime-only、blocked；
- 目标文件备份和预期输出路径。

### Gate 1：字节级验证

- 输出文件存在且大小合理；
- 目录结构和文件数没有意外变化；
- 原子写入无临时文件残留；
- 编码/EOL/BOM 符合源文件策略；
- 文件 hash 变化只出现在预期目标集合；
- 未修改文件 hash 与源一致。

### Gate 2：格式/容器重开

- JSON/XML/CSV/SQLite 可重新解析；
- AssetBundle/SerializedFile/WebData 可重新打开；
- 全对象枚举数量、Class ID、Path ID 和引用集合符合预期；
- Mono 程序集可由 CLR/反编译器加载；
- IL2CPP metadata/native 交叉解析通过；
- catalog/hash/CRC 能被解析。

### Gate 3：对象语义验证

- 目标字段等于预期译文；
- key、GUID、Path ID、PPtr、脚本、类型和地址未变；
- 非目标对象的字段/字节未意外变化；
- StringTable Entry ID、locale 和 metadata 保持；
- 字体 character/glyph/atlas/material 引用完整；
- 译文中所有变量、标签、输入 token 通过质量门。

### Gate 4：启动冒烟

至少执行：

1. 冷启动；
2. 到主菜单；
3. 切换语言/重启；
4. 进入首个场景；
5. 打开设置和键位界面；
6. 新建存档、保存、读档、退出；
7. 检查 Player/BepInEx/Unity 日志中的异常、资源加载错误和 CRC mismatch。

### Gate 5：游戏性回归

覆盖以下路径：

- 键盘、鼠标、手柄、触屏输入；
- 确认/取消/返回/暂停/导航/拖拽/滚动；
- 交互、拾取、对话、选择、任务更新；
- 战斗、技能、装备、制作、商店、地图；
- 场景切换、过场、死亡、重试、结局；
- 多分辨率、窗口化、全屏、DPI/UI 缩放；
- 断网、远程内容失败、缓存命中和缓存清空；
- 旧存档和新存档兼容性。

### Gate 6：结果侧屏幕审计

用录屏/截图 OCR 做差集：

- 原语言仍出现：写回未命中、运行时覆盖或回退；
- 中文出现但乱码/方框：字体链问题；
- 文本消失：标签、占位符、布局或对象重建问题；
- 按钮可见但无法点击：布局、透明遮挡、事件引用或输入状态问题；
- 只在特定分辨率失败：布局和字体度量问题。

## 12. 自动化回归测试设计

### 12.1 单元测试

至少覆盖：

- UTF-8/UTF-16/BOM/EOL round-trip；
- JSON/XML/CSV 转义、键集合和字段类型；
- 占位符重复次数、顺序、类型；
- TMP/HTML/Rich Text 标签嵌套；
- 输入 token 子序列和语义动作；
- Unity string length header、UTF-8 字节长度和 4 字节对齐；
- Path ID/PPtr/MonoScript 保持；
- StringTable 按 Entry ID 写回；
- AssetBundle 重开、依赖和 CRC 更新；
- 固定容量 Mono/IL2CPP 超长拒绝而不是危险截断；
- 字体 atlas/glyph/character 一致性。

### 12.2 属性测试/模糊测试

对任意译文随机生成：

- 中文、emoji、组合字符、全角符号、换行；
- 长度为 0、1、边界长度、超长；
- 占位符重复、标签嵌套、转义和非法 Unicode；
- 混合编码和异常字节。

目标不是要求每条都能写回，而是要求：

- 解析器不崩溃；
- 不安全输入被拒绝并记录；
- 源文件和 staging 不被破坏；
- 失败可重试、可回滚。

### 12.3 集成测试

为每个 Unity 版本/后端/平台准备最小样本：

```text
Mono + Unity UI Text
Mono + TMP 1.x/2.x/3.x
IL2CPP metadata vXX
普通 SerializedFile
UnityFS LZMA/LZ4/未压缩 bundle
Addressables 本地/远程 catalog
Localization StringTable + Smart String
TextAsset JSON/CSV/剧情脚本
字体 atlas + fallback
```

每个样本都必须执行“提取 → 翻译占位 → 写回 → 重开 → 运行时冒烟 → 回滚”。

## 13. 失败报告必须记录什么

失败报告不能只写“写回失败”。至少记录：

```text
游戏/平台/Unity版本/后端/架构
源文件相对路径和 source SHA-256
输出文件相对路径和 target SHA-256
容器链、SerializedFile、Class ID、Path ID、字段路径
原文/译文（必要时脱敏）
编码、EOL、字符串原/目标字节长度
占位符、富文本、输入 token 比较结果
写回器、解析器、字体载荷版本
失败阶段：preflight/patch/reopen/catalog/runtime/gameplay
异常类型、完整错误和日志路径
是否可回滚、备份路径和建议动作
```

按根因分类：`parse_failed`、`reference_broken`、`key_changed`、`placeholder_mismatch`、`input_token_mismatch`、`capacity_exceeded`、`crc_mismatch`、`font_missing_glyph`、`layout_overflow`、`runtime_hook_failed`、`remote_content_unavailable`、`signature_invalid`。

## 14. 当前项目写回链路的重点改进建议

从现有代码和测试可以确认项目已经有：

- 文本文件写回的编码/EOL 保留；
- key 与结构化字段保护；
- Unity 容器重建和重开校验；
- Addressables catalog CRC 更新与冲突阻断；
- Mono/IL2CPP 固定容量限制和截断报告；
- 字体替换和部分运行时字体回退；
- staging、输入 hash、备份目录、原子发布和失败恢复。

下一步最值得补齐的是：

### P0：写回安全闸门

1. 把“写回成功”拆成文件、容器、对象、运行时、游戏性五种状态，禁止单一 succeeded 掩盖后续失败；
2. 所有 rejected/truncated/blocked 条目必须进入报告，并阻断默认发布；
3. 每次写回生成 source/target manifest，列出未修改文件 hash；
4. 增加 key、InputAction、Control Path、资源地址和脚本字段的不可变集合校验；
5. 增加 staging 启动冒烟和日志扫描，而不仅是 UnityPy 重开。

### P1：最常见游戏性回归

1. 输入 token 结构化保护和按键提示截图回归；
2. TMP/Legacy Font/Fallback/atlas 的渲染验证；
3. 多分辨率 UI 截图差集、布局溢出和点击区域检查；
4. Addressables 清 cache/保留 cache/离线/远程失败四种测试；
5. 旧存档、新存档、语言切换、重启后状态回归。

### P2：复杂游戏

1. 运行时 setter 捕获与 source locator 合并；
2. 网络/解密/热更新内容进入可回放证据链；
3. OCR/录屏差集发现“写回没命中”的屏幕原文；
4. IL2CPP 只读/运行时替换优先，未知版本默认 blocked；
5. APK/IPA 重打包签名和平台安装验证。

## 15. 推荐的发布报告模板

```text
汉化发布报告
游戏：
平台/架构：
Unity 版本/后端：
源版本 hash：
输出版本 hash：

静态写回：        PASS / WARN / BLOCKED
Unity 容器重开：   PASS / WARN / BLOCKED
引用完整性：       PASS / WARN / BLOCKED
占位符/标签/key：  PASS / WARN / BLOCKED
字体与布局：       PASS / WARN / BLOCKED
Addressables：     PASS / WARN / BLOCKED / N/A
Mono/IL2CPP：       PASS / WARN / BLOCKED / N/A
启动冒烟：          PASS / WARN / BLOCKED
输入回归：          PASS / WARN / BLOCKED
场景/任务回归：     PASS / WARN / BLOCKED
存档回归：          PASS / WARN / BLOCKED
OCR/录屏差集：      PASS / WARN / BLOCKED / N/A

写回条目：
拒绝条目：
截断条目：
未覆盖文件：
已知风险：
备份路径：
回滚命令/步骤：
```

发布状态建议遵循：

- `PASS`：所有必需闸门通过；
- `WARN`：只存在明确记录且不影响核心游戏性的风险；
- `BLOCKED`：存在结构、引用、输入、启动、存档或远程内容风险，不得标记为可发布。

## 16. 参考资料

以下资料用于核对 Unity 容器、Addressables、Localization、字体、程序集和运行时注入行为。链接访问核对日期为 2026-08-08。

### Unity 官方文档

1. [AssetBundles — Introduction](https://docs.unity3d.com/Manual/AssetBundlesIntro.html)
2. [AssetBundles — Building](https://docs.unity3d.com/Manual/AssetBundles-Building.html)
3. [AssetBundles — Dependencies](https://docs.unity3d.com/Manual/AssetBundles-Dependencies.html)
4. [AssetBundles — Loading assets](https://docs.unity3d.com/Manual/AssetBundles-Native.html)
5. [AssetBundle.LoadFromFile](https://docs.unity3d.com/ScriptReference/AssetBundle.LoadFromFile.html)
6. [AssetBundle.LoadFromFileAsync](https://docs.unity3d.com/ScriptReference/AssetBundle.LoadFromFileAsync.html)
7. [Addressables — Loading AssetBundles](https://docs.unity3d.com/Packages/com.unity.addressables@1.21/manual/LoadingAssetBundles.html)
8. [Addressables — Build artifacts](https://docs.unity3d.com/Packages/com.unity.addressables@1.21/manual/BuildArtifacts.html)
9. [Addressables — Remote content distribution](https://docs.unity3d.com/Packages/com.unity.addressables@1.21/manual/RemoteContentDistribution.html)
10. [Localization — String Tables](https://docs.unity3d.com/Packages/com.unity.localization@1.5/manual/StringTables.html)
11. [Localization — LocalizedString API](https://docs.unity3d.com/Packages/com.unity.localization@1.5/api/UnityEngine.Localization.LocalizedString.html)
12. [TextMesh Pro package manual](https://docs.unity3d.com/Packages/com.unity.textmeshpro@3.0/manual/index.html)
13. [UnityYAML](https://docs.unity3d.com/Manual/UnityYAML.html)
14. [StreamingAssets](https://docs.unity3d.com/Manual/StreamingAssets.html)
15. [Application.persistentDataPath](https://docs.unity3d.com/ScriptReference/Application-persistentDataPath.html)

### 写回与分析工具

16. [UnityPy — extraction and typetree editing](https://github.com/K0lb3/UnityPy)
17. [AssetRipper](https://github.com/AssetRipper/AssetRipper)
18. [AssetRipper documentation](https://assetripper.github.io/AssetRipper/)
19. [UABEA](https://github.com/nesrak1/UABEA)
20. [AssetRipper TypeTreeDumps](https://github.com/AssetRipper/TypeTreeDumps)
21. [Il2CppDumper](https://github.com/Perfare/Il2CppDumper)
22. [XUnity.AutoTranslator](https://github.com/bbepis/XUnity.AutoTranslator)
23. [BepInEx plugin development](https://docs.bepinex.dev/articles/dev_guide/plugin_tutorial/index.html)
24. [Microsoft Learn — ECMA-335 `ldstr` opcode](https://learn.microsoft.com/en-us/dotnet/api/system.reflection.emit.opcodes.ldstr)
25. [Microsoft Learn — Regular expression language reference](https://learn.microsoft.com/en-us/dotnet/standard/base-types/regular-expression-language-quick-reference)

### 安全与发布

26. [Unity Manual — Include additional files in a build](https://docs.unity3d.com/Manual/StreamingAssets.html)
27. [Unity Manual — Managed code stripping](https://docs.unity3d.com/Manual/ManagedCodeStripping.html)
28. [Microsoft Learn — BinaryFormatter security guide](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide)

## 17. 最终边界

“写回完成”不能定义为“译文数据库里有译文”或“工具没有抛异常”。可交付的定义是：

> 对当前游戏版本、平台和已取得资源，写回后的文件与 Unity 对象能够重开，所有引用/key/占位符/输入 token/字体资源保持有效，Addressables 和程序集校验链通过，游戏能够启动、切换场景、响应输入、保存读取并完成核心流程；所有未验证路径都在报告中明确列出，并且可以一键回滚。

任何无法证明这一点的输出，都应该被标记为 `WARN` 或 `BLOCKED`，而不是假报“汉化成功”。
