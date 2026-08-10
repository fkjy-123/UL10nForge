"""六库种子数据入库脚本（2026-08-11，§0.4.4 第 3 步）。

从 docs 五份指南 + 识别形态清单提取的种子（94 条）写入知识库
（source=seed，按 pattern 幂等）。补充 BUILTIN_RULES 骨架种子之外
的详细知识：unity_structure 41 条（版本/资源类型/文本位置/检测方法/
提取方案/常见问题）、text 7 条（文本类型判定）、component_compat
13 条（组件兼容）、quality 17 条（质量规则/术语/评分）、writeback
17 条（写回案例/格式要点/测试流程）。

用法：python scripts/kb_seed_docs.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hanhua.core.knowledge import KnowledgeBase  # noqa: E402

DB = Path.home() / ".hanhua" / "knowledge.db"

# (domain, kind, pattern, action, map_to, note) —— 提取自 docs 五份指南
# + 识别形态清单（详见各 note 的 来源: 标注）
SEEDS = [
    # ═══ unity_structure：Unity 结构库（41 条） ═══
    # unity_version
    ("unity_structure", "unity_version",
     "旧版 Unity（约 2018-2019 及更早）构建布局含 mainData、data.unity3d、"
     "resources.resource；macOS 为 Game.app/Contents/Resources/Data",
     "info",
     "扫描根目录按 globalgamemanagers、SerializedFile/AssetBundle 魔数识别，"
     "不依赖固定目录名/扩展名；binary2text 需同版本 Unity 且带 TypeTree，"
     "用 UnityPy/AssetRipper 更稳",
     "来源:全景指南:3.1;资料大全:2.1"),
    ("unity_structure", "unity_version",
     "IL2CPP global-metadata.dat 的 magic/version 与字符串表结构随版本变化"
     "（无 magic 可能为加密），不能按单一版本硬编码",
     "info",
     "先验证 metadata magic/version，再从 native binary 定位 code/metadata "
     "registration，交叉验证 literal count/offset/length/UTF-8 边界",
     "来源:全景指南:6.2;资料大全:3.2"),
    ("unity_structure", "unity_version",
     "TMP 1.4.0 移除 SetCharArray，新 Unity/TMP 版本运行时 SetText 钩子点可能失效",
     "info",
     "运行时 hook 按 Unity/TMP/平台版本适配，必要时加 OnWillRenderCanvas/"
     "帧末 UI 树枚举兜底",
     "来源:资料大全:5;全景指南:7.2"),
    # resource_type
    ("unity_structure", "resource_type",
     "TextAsset 对象内容在 m_Script（新版 API 为 .script）字节数组，发布后"
     "原扩展名不可见；.bytes 可能是压缩/加密/数据库等任意二进制",
     "info",
     "先做 BOM/UTF-8/16/32/Shift-JIS/GBK/Windows-1252 编码探测，再按格式"
     "递归解析，必须二进制安全解析；UnityPy obj.read() 读取",
     "来源:全景指南:4.2;资料大全:1.3"),
    ("unity_structure", "resource_type",
     "MonoBehaviour/ScriptableObject 可把字符串存进任意自定义字段（text/"
     "m_Text/dialogue/title/description 等仅为启发式），含 List<string>/"
     "嵌套字典/[SerializeReference] 多态",
     "info",
     "类型树全递归收集所有 string 叶节点与可疑 byte[]，字段名只作置信度"
     "特征不作排除理由；缺类型树时走原始字节/脚本恢复/runtime hook",
     "来源:全景指南:4.1;4.3"),
    ("unity_structure", "resource_type",
     "内置 UI 组件 UnityEngine.UI.Text.m_Text、InputField 初始 text 与 "
     "placeholder 引用、UnityEngine.TextMesh.m_Text",
     "info",
     "按类型树字段+组件关系提取；初始序列化值可能只是占位文本，真实文字"
     "在 Awake/Start 或数据绑定后覆盖，需运行时记录最终赋值",
     "来源:全景指南:4.4;资料大全:2.1"),
    ("unity_structure", "resource_type",
     "TMP_Text/TextMeshPro/TextMeshProUGUI/TMP_InputField 常见字段 m_text，"
     "实为 MonoBehaviour 而非内置类，内容含富文本标签",
     "info",
     "用类型树+MonoScript 身份识别（不能只按内置 Class ID），富文本标签需保护",
     "来源:全景指南:4.4;资料大全:2.1"),
    ("unity_structure", "resource_type",
     "UI Toolkit：UXML/VisualTreeAsset 的 text/tooltip/自定义属性，运行时"
     "TextElement.text/Label/Button/TextField 数据绑定",
     "info",
     "解析原始 UXML 或 VisualTreeAsset 类型树；静态序列化值可能被数据绑定覆盖",
     "来源:全景指南:4.4"),
    ("unity_structure", "resource_type",
     "Unity Localization 包：StringTable（m_TableData/m_Localized，每 locale "
     "一个值列）+ SharedTableData（key 名/稳定 ID）+ Smart String",
     "info",
     "按 m_LocaleId.m_Code/m_TableData/m_Id 识别；SharedTableData 关联各 "
     "locale 表并选真实源语言；Smart String 语法解析并精确保护 format item",
     "来源:全景指南:4.6;资料大全:1.4"),
    ("unity_structure", "resource_type",
     "I2 Localization：I2Languages.asset（Resources 下，打包进 "
     "resources.assets），LanguageSource=languages 头+Terms 列表",
     "info",
     "用 pyI2L（rawCSV 最通用）或按 I2 结构解析 MonoBehaviour 序列化树/字节",
     "来源:资料大全:1.5"),
    ("unity_structure", "resource_type",
     "第三方剧情/本地化/UI 插件：Ink(.ink→JSON/TextAsset)、Yarn Spinner"
     "(.yarn+String Table/CSV+line ID)、Fungus、Pixel Crushers、NGUI/"
     "FairyGUI/Noesis、Lean Localization 等自定义对象图",
     "info",
     "建立指纹适配层（程序集名/MonoScript 全名/字段结构/资源路径/魔数），"
     "建立在通用类型树递归之上而非替代",
     "来源:全景指南:4.7;资料大全:1.2"),
    ("unity_structure", "resource_type",
     "SQLite 文件头 'SQLite format 3\\0'（可能无 .db 扩展名）；Protobuf/"
     "MessagePack/FlatBuffers 无通用提取器",
     "info",
     "SQLite 枚举表/列+主键定位，检查 FTS 虚表/JSON 列/压缩 BLOB；自定义"
     "二进制从反序列化调用恢复，禁止等长覆盖未知二进制",
     "来源:全景指南:5.3;5.4"),
    ("unity_structure", "resource_type",
     ".resS/.resource 是无头外部原始字节块，由配对 .assets 的 offset/size "
     "索引，多为 Texture2D/AudioClip 大块流数据",
     "info",
     "随父 SerializedFile 保留并解析；单独 strings 扫描低效（LZ4 压缩块"
     "需先解压）",
     "来源:资料大全:2.2;全景指南:3.1"),
    ("unity_structure", "resource_type",
     "AssetBundle 容器（UnityFS/UnityRaw/UnityWeb 魔数）可嵌套 SerializedFile"
     "甚至 bundle 套 bundle；UnityCN 加密头 #$unity3dchina!@ 为 LZ4+AES-ECB+XOR",
     "info",
     "UnityPy env.load() 递归打开并遍历 env.files；加密需 set_assetbundle_"
     "decrypt_key 或暴力探测 16 字符 key；回写用 UABEA patchcrc 清校验",
     "来源:资料大全:2.3;全景指南:4.1"),
    ("unity_structure", "resource_type",
     "代码字符串表：Mono Managed/*.dll 的 #US 堆（UTF-8 紧凑排列、1-2 字节"
     "长度前缀，仅 ldstr 常量）；IL2CPP global-metadata.dat 字符串表",
     "info",
     "dnfile/Mono.Cecil 读 #US + UI 调用溯源判定角色；metadata 用 "
     "Il2CppDumper 的 stringliteral.json 提取；原生 bin 仅作候选",
     "来源:资料大全:3.1;3.2;3.3;全景指南:6.1"),
    # text_location
    ("unity_structure", "text_location",
     "松散文本文件：JSON/CSV/XML/INI/YAML/TOML/PO/MO/ARB/字幕(SRT/VTT/ASS/"
     "TTML)/剧情脚本(ink/yarn/lua)等出现在任意目录、StreamingAssets、Mods",
     "info",
     "容错解析+递归字符串叶节点；保留换行/引号/转义/复数/时间码/msgctxt "
     "等格式细节；JSON 键可能是 ID 不能统一丢弃或统一翻译",
     "来源:全景指南:2;5.2;资料大全:1.1"),
    ("unity_structure", "text_location",
     "StreamingAssets 内容按原样复制进 Player（本地化表/bundle/剧情脚本/"
     "音频 bank/热更新代码）；Android 在 APK/JAR 内、WebGL 是 URL",
     "info",
     "提取器必须能解 APK/ZIP/WebData，不能只递归当前文件系统目录",
     "来源:全景指南:3.2"),
    ("unity_structure", "text_location",
     "Addressables 本地位置 aa/ 目录 + catalog.json + *.bundle；远程内容时"
     "安装包内可能只有 catalog 和 URL，文本首次运行才下载",
     "info",
     "解析 settings/catalog 的 internal ID/provider/dependency/hash/CRC/"
     "LoadPath，从 Unity Cache 收集依赖 bundle 后对象级扫描",
     "来源:全景指南:3.3;资料大全:1.6"),
    ("unity_structure", "text_location",
     "运行后生成文本：persistentDataPath（Windows AppData/LocalLow）、"
     "Unity AssetBundle Cache、PlayerPrefs、BepInEx/Mod 目录、Steam Workshop",
     "info",
     "安装后可选扫描；可能含玩家隐私数据，默认不上传不翻译玩家输入和"
     "身份信息，扫描前提示范围",
     "来源:全景指南:3.4"),
    ("unity_structure", "text_location",
     "场景/预制体/Timeline 资产文本：levelN/mainData 的 UI、inactive 对象、"
     "隐藏菜单、Prefab Variant 默认字段、Timeline/Playable 自定义 clip、"
     "StateMachineBehaviour、Visual Scripting 图节点",
     "info",
     "扫描全部对象包括未激活对象，不能只根据类名排除 Timeline/Playable/"
     "VisualScripting（自定义 clip 可能保存字幕）",
     "来源:全景指南:4.5"),
    ("unity_structure", "text_location",
     "平台包内文本：Android APK/AAB/OBB 的 assets、libil2cpp.so、"
     "resources.arsc/strings.xml；iOS .strings/.plist/.lproj；WebGL .wasm/"
     ".framework.js/.data",
     "info",
     "分层扫描 Unity 数据与原生层（apktool/aapt、plist/strings 解析、"
     "WASM/JS strings+运行时 hook）",
     "来源:全景指南:3.5"),
    ("unity_structure", "text_location",
     "运行时才出现的动态文本：字符串拼接/插值/StringBuilder、本地化 key "
     "查表最终值、复数/性别/随机台词、UI Toolkit 数据绑定",
     "info",
     "hook 或轮询 Text.text/TMP_Text.text/TextElement.text/GUIContent/"
     "本地化表 API；XUnity.AutoTranslator SetText 钩子可作覆盖率对照基准",
     "来源:全景指南:7.1;资料大全:5"),
    ("unity_structure", "text_location",
     "烘焙类文本：Texture2D/SpriteAtlas 图片文字、视频硬字幕、Mesh 顶点/"
     "粒子/图标字体几何文字、无字幕语音对白（Wwise/FMOD/CriWare）",
     "info",
     "Sprite 按 rect 切片放大+多尺度 OCR、视频按镜头变化抽帧 OCR、音频"
     "解包+ASR+时间轴对齐；无字符串可恢复时重制资产或运行时覆盖",
     "来源:全景指南:8.1;8.2;8.3;8.4"),
    # detect_method
    ("unity_structure", "detect_method",
     "真实游戏常把 UnityFS/WebFile/ZIP/SQLite/JSON/MessagePack/纯文本藏在 "
     ".dat/.bytes/.pak 或无扩展名文件中；FakeHeader 垃圾头在 magic 前有 "
     "≤128KB 前缀",
     "info",
     "对所有文件做魔数/熵/编码探测后路由，扩展名只作提示；FakeHeader 前 "
     "128KB 扫描 magic 后裁剪；魔数优先于扩展名",
     "来源:全景指南:5.1;资料大全:4"),
    ("unity_structure", "detect_method",
     "加密/混淆层特征：UnityCN 头 #$unity3dchina!@、自定义 XOR（统计高频"
     "字节 0x20 推导 key）、Base64 混淆串、无 magic 加密 metadata",
     "info",
     "逐层剥离并验证 magic（UnityFS/UnityWeb）；检测到即标记「疑似加密/"
     "混淆，需人工处理」并报告，不要求解密写回",
     "来源:资料大全:4;全景指南:5.5"),
    ("unity_structure", "detect_method",
     "提取形态显式注册表（mono_csharp/mono_unityscript/mono_boo/"
     "asset_unity/il2cpp_metadata），文本先验分 dense（UnityScript/Boo "
     "编译产物几乎全是显示文本）与 mixed",
     "info",
     "形态不登记→元测试失败；新形态先登记先验与实证锚点再启用；dense "
     "先验决定启发式边界",
     "来源:识别形态:1"),
    # extract_plan
    ("unity_structure", "extract_plan",
     "完整覆盖模型：文件扫描 ∪ Unity 对象级扫描 ∪ 托管/原生代码扫描 ∪ "
     "运行时捕获 ∪ OCR/ASR 结果侧审计",
     "info",
     "按五路分阶段实施：无损 inventory→递归解包格式路由→候选发现与证据"
     "分级→统一中间表示→运行时覆盖→OCR 差集闭环",
     "来源:全景指南:1;9;资料大全:7"),
    ("unity_structure", "extract_plan",
     "全对象扫描：遍历全部对象，类型树可用时递归 dict/list/array，收集"
     "每个 string 与有字符串迹象的 byte[]，保存容器链+PathID+ClassID+"
     "MonoScript+字段路径",
     "info",
     "稳定定位键 <容器路径>!<内部SerializedFile>#<PathID>:<字段路径>，"
     "不用字节偏移（重建 bundle/长度变化/版本差异会使偏移变化）",
     "来源:全景指南:4.1"),
    ("unity_structure", "extract_plan",
     "候选证据四档分级：A 运行时已显示、B 强显示（Localization 表 value/"
     "UI 组件 text）、C 可能显示（自定义对象自然语言）、D 低置信（对象名/"
     "资源名/原生 strings）",
     "info",
     "过滤不是删除，各档保留原始记录，默认翻译队列只开 A/B/C 中通过结构"
     "校验的条目；低置信进候选库不静默丢弃",
     "来源:全景指南:9.3"),
    ("unity_structure", "extract_plan",
     "加密/压缩/自定义包处理链：容器识别→解包→解密→解压→反序列化→"
     "字符串分类，每步记录算法/key 来源/输入 hash/父容器路径",
     "info",
     "静态找不到 key 时 hook File.ReadAllBytes/AssetBundle.LoadFromMemory "
     "输入缓冲区等返回点",
     "来源:全景指南:5.5"),
    ("unity_structure", "extract_plan",
     "Addressables 提取：识别 settings.json/catalog/hash 与 bundle provider "
     "信息，解析 catalog 的 internal ID/provider/dependency/hash/CRC",
     "info",
     "下载或从 Unity Cache 收集所有依赖 bundle→逐 SerializedFile 递归对象"
     "级扫描；回写同步处理 catalog/hash/CRC/签名或运行时覆盖",
     "来源:全景指南:3.3"),
    ("unity_structure", "extract_plan",
     "回写策略风险：IL2CPP 原地改 literal 必须处理长度/偏移/校验和与保护；"
     "Mono #US 堆回写有长度和 token 稳定性风险",
     "info",
     "优先运行时替换/资源覆盖/IL 重写；变长写回用「复用原空间+尾部追加」"
     "策略；UABEA patchcrc 清校验",
     "来源:全景指南:6.1;6.2;资料大全:3.2;6"),
    ("unity_structure", "extract_plan",
     "运行时捕获：hook 或轮询 uGUI Text.text、TMP Text.text/SetText、"
     "TextMesh.text、UI Toolkit TextElement.text、IMGUI GUIContent",
     "info",
     "每条记录含原文/组件类型/GameObject 层级/场景/调用栈/出现时间次数/"
     "屏幕区域/locale；静态与运行时记录按 locator 合并成翻译语境",
     "来源:全景指南:7.1;9.4"),
    ("unity_structure", "extract_plan",
     "用户实测遗漏 SOP：定位载体形态→证据分层审查→真实样本锚点断言"
     "「已知文本必须进池」→形态登记→全量回归",
     "info",
     "大文件无法进 git 的用双名 fixture/最小化构造并保留真实路径验证记录",
     "来源:识别形态:3"),
    # known_issue
    ("unity_structure", "known_issue",
     "TMP 文本漏而 uGUI 正常——只识别内置 Class ID，未用 MonoScript/类型树"
     "识别 TMP MonoBehaviour",
     "info",
     "识别 TMP 对象身份+运行时 setter，纳入组件级上下文",
     "来源:全景指南:10"),
    ("unity_structure", "known_issue",
     "扩展名白名单/目录黑名单/读取异常导致「文件存在但扫描器没报告」；"
     "最小长度/词法过滤过强导致漏短按钮",
     "info",
     "inventory 全量报告（unsupported/blocked/error 显式列出）不静默跳过；"
     "语言阈值不应用于 UI 字段",
     "来源:全景指南:9.1;10"),
    ("unity_structure", "known_issue",
     "仅按 source 文本去重导致同一英文在不同语境需不同译文却只保留一个；"
     "把本地化键/InputAction/资源路径当显示值翻译导致 key 失效",
     "info",
     "locator/callsite/scene 参与语境键；key 按字段角色和调用关系保护",
     "来源:全景指南:10"),
    ("unity_structure", "known_issue",
     "只读 global-metadata.dat 会漏掉运行时拼接结果、native 插件字符串、"
     "网络文本、嵌入资源、加密数据",
     "info",
     "扫描 runtime metadata 以外的 native string/嵌入资源；从内存 dump 或"
     "解密函数返回点获取；回写优先运行时替换",
     "来源:全景指南:6.2"),
    ("unity_structure", "known_issue",
     "外部平台文本（Steam/EOS overlay、成就、Android/iOS 权限框、广告 SDK）"
     "不由 Unity 游戏资源控制",
     "info",
     "标记为「外部来源」，引导检查平台后台/本机插件资源/网页",
     "来源:全景指南:7.4"),
    ("unity_structure", "known_issue",
     "运行时 hook 盲点：只 hook 属性 setter 漏掉直接写内部字段；对象池复用"
     "组件；文本一帧即逝；anti-cheat 禁止注入；IL2CPP 泛型/内联改变 hook 点",
     "info",
     "加帧末 UI 树枚举；定位键含层级模板+调用点；事件级捕获；代理/日志/"
     "截图 OCR/官方 Mod 接口兜底",
     "来源:全景指南:7.2"),
    ("unity_structure", "known_issue",
     "证据分层：确定性（typetree UI 字段）> 形态性（dense 先验）> 猜测性"
     "（uppercase/credit 反模式）；硬结构规则任何证据强度都生效，软猜测"
     "规则只在更低证据强度生效",
     "info",
     "案例：'A game by Kyuppin' 曾被 credit 软猜测降级跳过，0.14.1 分层后"
     "消除；修改提取规则先问硬结构还是软猜测、会推翻哪层证据",
     "来源:识别形态:2"),
    ("unity_structure", "known_issue",
     "跳过是哑信号：被跳过文本不报错不进池不出现在审计里，只有用户实测"
     "能感知；多轮「0 失败」审计只测已知样本不失败",
     "info",
     "形态级 skipped 率告警/产出对比门禁现阶段不做（小遗漏无感+误报高）；"
     "用户实测制度化是唯一可靠的小遗漏探测器",
     "来源:识别形态:4"),
    ("unity_structure", "known_issue",
     "Wwise/FMOD 音频事件名与 strings bank 只是资源标识，不等于对白原稿；"
     "ASR 结果证据等级低于正式字幕",
     "info",
     "解包音频+ASR+说话人/时间轴对齐，与剧情触发器或事件 ID 关联后再判定",
     "来源:全景指南:8.4"),
    # ═══ text：文本规则库（7 条） ═══
    ("text", "ui_text",
     "按钮/菜单/页面初始文本、tooltip、hint、InputField 占位文本（New "
     "Game、标题、按键提示）",
     "translate",
     "提取并翻译；初始序列化值可能只是占位，真实文字在 Awake/Start 或"
     "数据绑定后覆盖，需运行时记录最终赋值",
     "来源:全景指南:1.1;4.4"),
    ("text", "dialogue",
     "对白、对话选项、字幕、剧情文本（场景对话、Ink/Yarn/Fungus 剧情、"
     "对话框 Say/Menu）",
     "translate",
     "提取并翻译；保留说话人、选择分支、跳转变量与格式",
     "来源:全景指南:1.1;4.7;资料大全:1.2"),
    ("text", "skill",
     "技能/法术/天赋/能力名称与描述、升级说明",
     "translate",
     "提取并翻译，保留数值/占位符与条件分支",
     "来源:全景指南:1.1;4.3"),
    ("text", "equipment",
     "物品/装备/道具名称与说明（item description）、lore/设定文本",
     "translate",
     "提取并翻译；ID 与文本分表时 key 保存定位关系，只译文本列",
     "来源:全景指南:1.1;4.3"),
    ("text", "achievement",
     "成就/奖杯名称与描述、任务目标（objective）、任务说明",
     "translate",
     "提取并翻译；平台侧成就另走平台后台资源",
     "来源:全景指南:2;7.4"),
    ("text", "system_msg",
     "系统消息/错误提示/服务器公告/教程提示/提示框（error、message、"
     "prompt、通知）",
     "translate",
     "提取并翻译；区分官方静态文案与实时用户内容",
     "来源:全景指南:1.1;7.3"),
    ("text", "system_msg",
     "玩家输入与隐私数据：玩家昵称、聊天记录、存档内自定义内容",
     "skip",
     "不翻译不上传，扫描范围提示；存档可能含可复用下发文本但默认排除"
     "玩家身份信息",
     "来源:全景指南:3.4"),
    ("text", "debug",
     "UnityScript/Boo 编译产物的字符串字面量（语气词、含空格句子）——"
     "dense 先验下几乎全是显示文本",
     "translate",
     "按 dense 先验进池；「无空格不升级」等启发式边界不得违背 dense 先验"
     "（0.14.0 曾误杀 29 条语气词）",
     "来源:识别形态:1;3"),
    ("text", "param",
     "本地化键与 ID（menu.new_game、ITEM_SWORD_NAME、Entry ID、表 key、"
     "SharedTableData 稳定 ID）",
     "keep",
     "保存定位关系，不翻译；翻译 key 会导致回写失效",
     "来源:全景指南:1.1;4.6"),
    ("text", "param",
     "格式模板与占位符（{0}、{key}、{count:plural:...}、plural/gender/"
     "conditional 变量、富文本标签）",
     "keep",
     "翻译字面部分，严格保护变量、语法与格式项；Smart String 需语法解析",
     "来源:全景指南:1.1;4.6"),
    ("text", "code",
     "技术/噪音字符串：URL、文件路径、类名、Shader 属性、资源名、协议"
     "字符串、GUID",
     "skip",
     "默认过滤但保留可追溯候选记录；进显示 API 的调用链证据可升级",
     "来源:全景指南:1.1;6.1"),
    ("text", "code",
     "硬结构数据：JSON 键名、纯数字、GUID——翻译会破坏功能",
     "keep",
     "硬结构规则在任何证据强度下生效；JSON 键可能本身是显示文本，需按"
     "字段角色区分",
     "来源:全景指南:5.2;识别形态:2"),
    ("text", "code",
     "资源标识与元数据：FNT/BMFont 字体元数据、音频事件名/strings bank、"
     "base64 ZIP 载荷、nolog= 空键值行",
     "skip",
     "降权或跳过，不当作显示文案",
     "来源:全景指南:4.2;8.4;识别形态:3;资料大全:4"),
    # ═══ component_compat：组件兼容库（13 条） ═══
    ("component_compat", "text",
     "Text 组件中文乱码或方块",
     "replace_font",
     "主因是字体不含 CJK 字形而非编码问题；替换 legacy Font 为支持中文的 "
     "TTF 或用字体替换模块换源；方框先查字体链再查编码",
     "来源:写回资料大全:1.3 主题5"),
    ("component_compat", "textmeshpro",
     "TMP 静态图集缺中文字形渲染为豆腐块",
     "rebind_font_asset",
     "TMP 静态图集不含中文字形时全部渲染为方框；替换 bundle 内 "
     "TMP_FontAsset 对象并确保图集含中文字形，不要手改引用",
     "来源:写回资料大全:1.1 主题五"),
    ("component_compat", "textmeshpro",
     "TMP 字体缺省略号字符触发 Line breaking recursion 报错",
     "rebind_font_asset",
     "Overflow=Ellipsis 且字体无省略号字形会无限换行递归；截断补「…」前"
     "确认字体含该字形，否则改用 ASCII \"...\"",
     "来源:写回资料大全:1.1 主题五;调查报告:2 P1"),
    ("component_compat", "textmeshpro",
     "手改 TMP 字体 PathID/GUID 后启动红条警告并崩溃",
     "rebind_font_asset",
     "手动改 m_Script/m_Material/Texture2D 的 PathID/GUID 替换 TMP 字体后"
     "崩溃；用参数迁移工具或直接替换 bundle 内 TMP_FontAsset 对象",
     "来源:写回资料大全:1.1 主题五"),
    ("component_compat", "textmeshpro",
     "动态 TMP 字体 Multi Atlas 切换语言报 m_AtlasTexture has not been "
     "assigned",
     "rebind_font_asset",
     "动态字体多图集切换语言后抛 UnassignedReferenceException；改用含中文"
     "的静态 TMP 字体资产替换",
     "来源:写回资料大全:1.2 主题4"),
    ("component_compat", "textmeshpro",
     "动态 TMP 图集 4096 填满导致新增汉字缺失",
     "rebind_font_asset",
     "默认 4096 动态图集存不下中文（日志 Atlas population failed）；替换"
     "为预生成中文字形的静态 TMP_FontAsset",
     "来源:写回资料大全:1.2 主题4"),
    ("component_compat", "textmeshpro",
     "TMP 字体替换后 m_sharedMaterial 引用断裂",
     "rebind_font_asset",
     "替换字体导致材质引用断裂（MissingReferenceException）；字体、材质、"
     "图集与引用必须成组替换并验证 fallback 链完整",
     "来源:写回资料大全:1.2 主题4"),
    ("component_compat", "textmeshpro",
     "TMP 版本不匹配警告导致中文不显示",
     "rebind_font_asset",
     "Font asset version 与 TMP 版本不匹配中文不显示；用与游戏 TMP 版本"
     "匹配的字体资产替换；Unity 6000 大字符集兼容问题用旧版资产重新打包",
     "来源:写回资料大全:1.2 主题4"),
    ("component_compat", "text",
     "文本溢出或透明 Image 挡射线导致按钮点不到",
     "info",
     "Text 默认 Raycast Target 开启像隐形墙拦截射线；关闭 Raycast Target "
     "或修正布局溢出；汉化后做点击区域回归",
     "来源:写回资料大全:1.2 主题3"),
    ("component_compat", "text",
     "英文短句变中文长句导致排版溢出或点击位置偏移",
     "info",
     "德法译中约 1:1.8、俄西 1:2，超框风险接近 80%；译文做长度限制，"
     "截图对比最小/最大窗口与多分辨率",
     "来源:写回资料大全:1.2 主题3;安全写回指南:9.3"),
    ("component_compat", "input_system",
     "汉化后按键失灵（Input System/EventSystem/IME）",
     "info",
     "多为插件层问题：新旧 Input System 混用、Standalone Input Module 不"
     "匹配、场景缺 EventSystem、中文系统未启用 IME；按插件层修复并提示",
     "来源:写回资料大全:1.2 主题8"),
    ("component_compat", "others",
     "BepInEx 版本不匹配或游戏目录含中文导致汉化失效",
     "info",
     "BepInEx 5.x 对应 Mono、6.x 对应 IL2CPP，不匹配约 90% 启动崩溃；"
     "游戏目录避免中文；杀毒软件隔离 DLL；BepInExConfigManager 覆盖 "
     "EventSystem 时设 Disable_EventSystem_Override=true",
     "来源:写回资料大全:1.2 主题7"),
    ("component_compat", "font",
     "Legacy Font 或 TMP_FontAsset 替换后仍显示方框或布局错乱",
     "rebind_font_asset",
     "Legacy Font 需同步 ascent/descent/line spacing/size/fallback/材质 "
     "shader；TMP_FontAsset 需 character/glyph/atlas/face info/material/"
     "fallback 成组替换，不同 TMP/Unity 版本 TypeTree 布局不混用",
     "来源:安全写回与回归验证指南:9.1-9.2"),
    # ═══ quality：翻译质量库（17 条） ═══
    ("quality", "common_error",
     "缺上下文把 Charge 误译成收费",
     "context_judge",
     "一词多义（Charge=蓄力/冲锋、Back=返回、Light=光/轻）需注入角色/"
     "组件类型/场景上下文；上下文分层发送，按 token 预算分批防截断",
     "来源:本地模型翻译质量指南:5.1-5.3"),
    ("quality", "common_error",
     "任务文本丢失数量（Find three keys 翻成寻找钥匙）",
     "info",
     "数量/单位/目标/条件/时限是可玩条件必须保留；任务名可文艺化，但"
     "目标描述必须可执行",
     "来源:本地模型翻译质量指南:13.1"),
    ("quality", "common_error",
     "否定词丢失导致技能效果被反转",
     "info",
     "Do not attack the guard 不能省略「不」；质量门检查否定、条件、数量、"
     "时态、因果保留（技能数值/目标/状态不翻转）",
     "来源:本地模型翻译质量指南:13.1/12 Gate D"),
    ("quality", "common_error",
     "翻译破坏 {0} 占位符导致 string.Format 崩溃",
     "info",
     "占位符、Smart String 语法必须原样保留；质量门做多重集合+顺序比较，"
     "缺失/多出/顺序变化阻断",
     "来源:本地模型翻译质量指南:9.2;写回资料大全:1.2"),
    ("quality", "common_error",
     "翻译破坏富文本标签或换行语义",
     "info",
     "<color>、<b>、<sprite>、\\n 等必须原样保留，TMP 标签未闭合整段显示"
     "异常；区分字面量 \"\\n\" 与真实换行",
     "来源:写回资料大全:1.2 主题5"),
    ("quality", "common_error",
     "把 \"...\" 改成省略号 \"…\" 导致按钮文本比较失败",
     "info",
     "长得一样但字节不同的字符会让 == 比较间歇失败；译文保持显示层字节"
     "等价，避免字符规范化改动；隐藏 \\r 同样导致比较失败",
     "来源:写回资料大全:1.2 主题2"),
    ("quality", "common_error",
     "翻译对话内嵌指令或触发词导致对话卡死",
     "info",
     "引擎指令（*<@Goodbye>read*）、触发词被翻译后无法识别；只换显示层，"
     "保留逻辑键与引擎语法",
     "来源:写回资料大全:1.2 主题2"),
    ("quality", "common_error",
     "对话控制符误输全角或中英标点混用",
     "info",
     "控制符必须半角否则事件执行报错；中文标点/空格/数字/单位规范写入 "
     "style guide 并在质量门检查",
     "来源:写回资料大全:1.2 主题1;本地模型翻译质量指南:14.1"),
    ("quality", "common_error",
     "选择项 Yes/No 固定翻成是/否",
     "info",
     "按问题语义翻译并与后续分支反应兼容，不固定译法；分支 key、跳转"
     "标签、条件变量不翻译",
     "来源:本地模型翻译质量指南:13.4"),
    ("quality", "term_consistency",
     "同一技能在菜单和对白出现多个译名",
     "info",
     "术语表带 scope（全局/游戏/场景/角色）与优先级，不是全局硬替换；"
     "候选术语人工确认后才进 approved glossary 并反向修订已有译文",
     "来源:本地模型翻译质量指南:8.1-8.2"),
    ("quality", "term_consistency",
     "历史机器译文被无条件当作正确答案复用",
     "info",
     "记忆库区分 machine/reviewed/locked/rejected，只有 reviewed/locked "
     "才作高优先级记忆；缓存键含目标语言/角色/术语/结构保护版本",
     "来源:本地模型翻译质量指南:8.3/17"),
    ("quality", "term_consistency",
     "角色口吻漂移（小孩说成公告腔、反派说成客服）",
     "info",
     "用角色卡（身份/年龄感/阵营/称谓/敬语/口头禅/禁用词）按场景连续"
     "片段翻译，角色级记忆保持称谓",
     "来源:本地模型翻译质量指南:13.3/2.1"),
    ("quality", "quality_gate",
     "质量门硬拒绝规则（占位符/输入 token/回显/JSON ID）",
     "info",
     "input_token_mismatch、placeholder_mismatch、target_script_mismatch、"
     "原文回显、JSON ID 异常设为硬拒绝；空译文/解释性前缀/半翻译/非法"
     "标签不进入写回",
     "来源:本地模型翻译质量指南:18 P0/6.4/16.3"),
    ("quality", "quality_gate",
     "结构保护槽位先保护再翻译再还原",
     "info",
     "把占位符/标签/输入键/glyph/URL/GUID/命令替换为槽位再送模型；缺少/"
     "多出/顺序变化/槽位被改/标签不成对 → 阻断；不要保护所有英文",
     "来源:本地模型翻译质量指南:9.1-9.3"),
    ("quality", "quality_gate",
     "翻译错误严重度分级 S0-S6",
     "info",
     "S0 崩溃/安全立即阻断回滚；S1 游戏不可玩阻断发布；S2 语义严重错误"
     "必须人工修正；S3 结构/格式错误自动拒绝写回；S4 一致性批量修订；"
     "S5 风格问题排队审校；S6 偏好差异记录不阻断",
     "来源:本地模型翻译质量指南:11.3"),
    ("quality", "scoring_case",
     "用 BLEU/COMET 等自动指标评判翻译可用性",
     "info",
     "自动指标有局限（不覆盖角色声音/按钮宽度/任务语义），仅用于对比模型"
     "与检测退化；需同时统计结构/占位符/输入 token/术语命中率/回显率/"
     "人工严重错误率/UI 溢出率",
     "来源:本地模型翻译质量指南:11.1-11.2/6.1"),
    ("quality", "term_consistency",
     "同一英文词不同角色允许不同译法（术语表非全局硬替换）",
     "info",
     "上下文/角色先决；候选术语人工确认后才进 approved glossary",
     "来源:本地模型翻译质量指南:8.1-8.2"),
    # ═══ writeback：写回验证库（17 条） ═══
    ("writeback", "writeback_case",
     "固定容量池截短译文后字符串尾部带 NUL 导致逻辑判定失灵",
     "info",
     "_fit_bytes 填 \\x00 到 capacity 但 IL2CPP 记录 length/#US 压缩前缀不"
     "更新，运行时字符串=译文+NUL；修复：更新记录区 length 为译文实际"
     "字节数，v39 链式重建数据区+更新全部 dataIndex",
     "来源:写回资料大全:2.4 发现F1"),
    ("writeback", "writeback_case",
     "写回截断把 {0} 占位符切开导致 string.Format 崩溃",
     "info",
     "质量门只在翻译阶段校验，截断发生在写回内部管不到；截断后重验占位符"
     "完整性，被破坏则拒绝该条并报告 rejected",
     "来源:写回资料大全:2.4 发现F2;调查报告:2 P0"),
    ("writeback", "writeback_case",
     "TextAsset 非 UTF-8 内容被 decode-replace 污染",
     "info",
     "GBK/Latin-1 文本 errors=replace 解码重编码把非 UTF-8 字节替换成 "
     "U+FFFD 永久损坏；写回侧 strict decode（译文/原文必须 strict UTF-8）",
     "来源:写回资料大全:2.4 发现F3"),
    ("writeback", "writeback_case",
     "替换 prefab/资源后 UnityEvent 事件绑定断裂按钮无反应",
     "info",
     "UnityEvent 通过 Inspector 引用绑定，资源替换/重排后目标引用丢失；"
     "不重排对象布局、不改变引用类字段，事件绑定列入验收清单",
     "来源:写回资料大全:1.1 主题五"),
    ("writeback", "writeback_case",
     "代码把显示文本当逻辑键（按钮文字/物品名比较分发）",
     "info",
     "翻译显示文本后游戏按原文比较/分发逻辑全失效；保留逻辑键只换显示层，"
     "key/标识符字段保护；culture 敏感比较列入验收",
     "来源:写回资料大全:1.2 主题2;调查报告:1.3"),
    ("writeback", "format_note",
     "无类型树(typeless)文件上执行 save_typetree 写回",
     "info",
     "猜测 typetree 与真实 class 布局不符 → 数据错位/卡死（UnityPy #195）；"
     "typeless 文件优先 rawstr 字节级补丁；read 失败禁止继续 save",
     "来源:写回资料大全:2.4 发现F4"),
    ("writeback", "format_note",
     "SerializedFile 字符串写回必须遵守长度头与对齐规则",
     "info",
     "对象内字符串=4 字节小端长度前缀+UTF-8+补零 4 字节对齐；pathID 必须"
     "唯一；m_Script/fileID/guid/pathID/StreamingInfo 引用字段是最大雷区",
     "来源:写回资料大全:1.1 主题一/主题二"),
    ("writeback", "format_note",
     "AssetBundle 重建时破坏内部结构与头字段",
     "info",
     "cab-<32hex> 名必须原样保留；未压缩 bundle 需 16 字节对齐；保持原始"
     "压缩方式；UnityFS 头字段/flags 与原始一致；避免重排对象牵动全链",
     "来源:写回资料大全:1.1 主题三"),
    ("writeback", "format_note",
     "Addressables catalog CRC 与 bundle 不匹配导致资源不加载",
     "info",
     "改过 bundle 后 catalog.json/catalog.bin 的 CRC 必须同步；同一旧 CRC "
     "映射多个不同新 CRC 时阻断；bundle/catalog/hash 成组发布",
     "来源:写回资料大全:1.1 主题三;安全写回指南:7.2"),
    ("writeback", "format_note",
     "变长写回破坏文件大小守恒导致布局错位",
     "info",
     "等长替换成功、变长替换失败是铁律；只能改原长度内文本，变长数据必须"
     "重建全链并重算偏移；固定容量截断按 UTF-16 2 字节对齐防半代理",
     "来源:写回资料大全:1.1 主题五/1.3 主题7"),
    ("writeback", "format_note",
     "Mono #US 堆写回破坏 ECMA-335 结构",
     "info",
     "长度前缀 1/2/4 字节压缩整数且计字节；条目=长度前缀+UTF-16LE+1 字节"
     "标志尾，总字节恒为奇数；中文必须置 flag=1；截断三处联动",
     "来源:写回资料大全:1.3 主题1/主题2/主题7"),
    ("writeback", "format_note",
     "IL2CPP global-metadata.dat 写回破坏字符串字面量",
     "info",
     "magic 0xFAB11BAF 与 header 区绝不触碰；stringLiteral 条目={dataIndex,"
     "length} 小端、length 是字节数；变长必须重建数据区并更新全部 dataIndex；"
     "版本差异大，未知版本直接拒绝",
     "来源:写回资料大全:1.3 主题3/主题4"),
    ("writeback", "format_note",
     "TextAsset 写回编码/BOM 处理不当导致乱码",
     "info",
     "m_Script 用 surrogateescape 保字节；UTF-8 无 BOM 是最安全格式；GBK/"
     "ANSI 被当 UTF-8 读产生锟斤拷；写回后重读确认译文能以原编码解码",
     "来源:写回资料大全:1.4 主题A/B/E"),
    ("writeback", "format_note",
     "JSON/CSV/XML/INI 结构化文本写回破坏格式",
     "info",
     "CSV 按 RFC4180 引号包裹、保留原始 EOL；JSON 转义引号/控制字符；"
     "XML 控制字符非法；不要用正则替换结构化文件，写回后重解析验证",
     "来源:写回资料大全:1.4 主题C/D/F;调查报告:2 P1"),
    ("writeback", "format_note",
     "SQLite/数据库写回",
     "info",
     "复制数据库在副本上事务操作；只改确认是显示值的 TEXT 列；PRAGMA "
     "integrity_check+外键检查+查询回归；加密库用运行时覆盖",
     "来源:安全写回与回归验证指南:5.3"),
    ("writeback", "format_note",
     "Mono/IL2CPP 字符串写回优先级与 blocked 策略",
     "info",
     "优先级：运行时显示层替换 > IL 重写 > 固定容量 patch；IL2CPP 无对应"
     "版本解析/重建/回归证据时默认 blocked；原生二进制无结构证据只提取不写回",
     "来源:安全写回与回归验证指南:8.1-8.3"),
    ("writeback", "test_flow",
     "写回整体流水线与安全提交流程",
     "info",
     "预检→复制到 staging（同卷）→副本 hash 复验→写回→重开验证→冒烟"
     "启动→五态闸门→原子替换发布；任何必需阶段失败不得发布半成品",
     "来源:写回资料大全:2.1;安全写回指南:3.1-3.3"),
    ("writeback", "test_flow",
     "分层验证闸门 Gate0-6 与发布状态判定",
     "info",
     "Gate0 写回计划审计→Gate1 字节级→Gate2 容器重开→Gate3 对象语义→"
     "Gate4 启动冒烟→Gate5 游戏性回归→Gate6 OCR 录屏差集；BLOCKED 不得"
     "标记可发布",
     "来源:安全写回与回归验证指南:11/15"),
    ("writeback", "test_flow",
     "重开验证与独立读取器交叉验证防自证失效",
     "info",
     "写回后重读逐条比对；提取/验证与 parse 共用同一套解析会自证失效 → "
     "用第二套独立读取器硬读记录区，写回前交叉核对不一致拒绝补丁",
     "来源:写回调查报告:2 P0"),
    ("writeback", "format_note",
     "AssetBundle 写回三一致性面",
     "info",
     "内部 SerializedFile + bundle 容器（原压缩模式/块信息/目录）+ 外部"
     "索引（catalog/hash/CRC/manifest）三面一致；报告中分别记录 SHA-256、"
     "bundle content CRC、catalog hash",
     "来源:安全写回与回归验证指南:7.1/7.3"),
]


def main() -> int:
    kb = KnowledgeBase(DB)
    added = hit = 0
    for domain, kind, pattern, action, map_to, note in SEEDS:
        if kb.store.upsert(domain, kind, pattern, action=action,
                           map_to=map_to, note=note, source="seed"):
            added += 1
        else:
            hit += 1
    kb.close()
    print(f"种子入库：新增 {added} 条 · 已有命中 {hit} 条（幂等）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
