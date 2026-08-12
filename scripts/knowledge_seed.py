"""知识库失败案例沉淀脚本：把已闭环游戏的真实修复经验写入知识库
（fail_case 域，FAIL 标准格式）。幂等（upsert 按 UNIQUE 去重），
可重复执行；后续每款游戏闭环后的新案例追加到 CASES 列表即可。

用法：python scripts/knowledge_seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hanhua.core.knowledge import KnowledgeBase  # noqa: E402

# (game, fail_type, problem, root_cause, fix, symptom, impact, version)
CASES = [
    # ── baldis-fun-new-school-remastered（12 项，628/0 闭环） ──
    ("baldis-fun-new-school-remastered", "翻译",
     "多词短语末位版本词被 UI 词典拒绝（UCLA Gold 回显失败）",
     "Gold 是版本后缀词，UI 词典判定把专名回显当漏翻",
     "_ui_check_words：多词跳过末位版本词，单词语义仍保留",
     "UCLA Gold 译文=原文被判 untranslated", "多词专名短语", "0.24.6"),
    ("baldis-fun-new-school-remastered", "翻译",
     "属格 's 碎片被判独立小写词（Playtime's 失败）",
     "has_independent_lower_word 把 's 的 s 当小写普通词",
     "先剥离 rich-text + 跳过撇号前单字母",
     "含属格专名的句子回显/半翻失败", "所有属格专名文本", "0.24.6"),
    ("baldis-fun-new-school-remastered", "翻译",
     "译文引号内 TitleCase 短语被判英文残留",
     "交互动作词检查把引号包裹的专名（按钮 \"Jump During Playtime\"）当动作词残留",
     "quoted_proper_terms 公共函数：引号内词必须都在原文出现才豁免",
     "按钮 \"Jump During Playtime\" 判失败", "交互提示+专名短语", "0.24.6"),
    ("baldis-fun-new-school-remastered", "识别",
     "星号前缀词表条目回显恒败（*shit / *beaner）",
     "TextAsset 脚本里的词表/列表条目，模型把 * 当强调标记回显",
     "_STAR_PREFIXED_WORD（^\\*[a-z]{3,}$）→ 结构跳过",
     "*shit 翻译回显恒败", "星号词表条目", "0.24.6"),
    ("baldis-fun-new-school-remastered", "识别",
     "混合符号 token 回显恒败（xChDC-Gs%OmaMl+g）",
     "含 %#&^$@|\\ 强符号的随机会话 token/编码串被当文本翻译",
     "_MIXED_SYMBOL_TOKEN（≥8 字符+字母，先剥 rich-text，!~ 不拒）→ 结构跳过",
     "token 串翻译失败", "随机 token/编码数据", "0.24.6"),
    ("baldis-fun-new-school-remastered", "识别",
     "// 注释行被当文本翻译成乱语",
     "TextAsset 脚本里的 C# 风格注释行是代码非游戏文本",
     "// 后跟空白 → comment 结构跳过（//host URL 仍走协议相对 URL）",
     "注释行翻译失败", "所有脚本注释行", "0.24.6"),
    ("baldis-fun-new-school-remastered", "翻译",
     "多行文本被模型合并为单行中文（Error...and check log. 恒败）",
     "1.8B 稳定把多行合并单行；multiline repair 逐行重译时首行被回显英文",
     "换行合并兜底：仅换行原因失败+译文含中文+无空段（\\n\\n=漏译证据）→ 放行首译",
     "多行错误提示翻译恒败", "多行短文本", "0.24.6"),
    ("baldis-fun-new-school-remastered", "翻译",
     "模型把专名联想补词（Shirt Decal→T-shirt Decal）",
     "has_translatable_tail 拦截导致专名引用重译不触发",
     "专名引用重译触发扩展到 target_script_mismatch；移除 has_translatable_tail",
     "专名被补成变体", "纯专名短语", "0.24.6"),
    ("baldis-fun-new-school-remastered", "翻译",
     "模型小写化专名被判英文残留（Bossfight→bossfight）",
     "原文 TitleCase 词在译文以小写出现被当漏翻；英语功能词（the）被误豁免",
     "小写化专名豁免（原文 TitleCase→译文小写放行）；_ENGLISH_FUNCTION_WORDS 排除冠词",
     "bossfight 残留判失败", "TitleCase 专名小写化", "0.24.6"),
    ("baldis-fun-new-school-remastered", "翻译",
     "彩色强调标签整对丢失（<color=green>Paused</color>→\"暂停\"）",
     "1.8B 对彩色强调的稳定行为是引号替代，完整标签对丢失被当占位符缺失",
     "完整标签对（<x></x> 同名成对）整体丢失+译文含中文 → 放行；单标签/{0} 仍失败",
     "彩色标签文本判失败", "彩色强调词", "0.24.6"),
    ("baldis-fun-new-school-remastered", "翻译",
     "repair 复查污染 quality_reasons 导致兜底判定失准",
     "multiline repair 失败后复查把原因覆盖成 target_script_mismatch，换行兜底失效",
     "首译失败状态快照：protected/multiline repair 失败后恢复翻译/状态/原因/meta",
     "换行兜底对 repair 后条目不生效", "所有 repair 降级链", "0.24.6"),
    ("baldis-fun-new-school-remastered", "翻译",
     "纯小写普通词整句回显恒败（outstanding citizen）",
     "降级链无分支覆盖：专名重译需 TitleCase、词级补译需译文含中文",
     "词级补译触发扩展到『译文无中文+untranslated_text』；裸回显也逐词引用两跳",
     "纯小写短句回显恒败", "小写普通词回显", "0.24.6"),
    # ── butterflies-episode-1（9 类，2561/114→修复中） ──
    ("butterflies-episode-1", "识别",
     "§ 前缀语言键码回显恒败（§m_quit ### 97 条）",
     "localization 键值模板的键（§ 前缀+_snake 键名+### 空值分隔符），值缺失无译义；"
     "且 en 后缀被罗曼功能词误判 multilingual_source 反向送译",
     "_SECTION_KEY（^§[a-zA-Z0-9_]+ ###$）→ 结构跳过；learn 入口过滤结构键",
     "§ 键码翻译回显恒败", "所有 § 键码语言文件", "0.25.0"),
    ("butterflies-episode-1", "识别",
     "语言代码目录标记回显恒败（EN/）",
     "双语 TextAsset 的语种分隔行无译义，键风格判定不覆盖带斜杠形态",
     "_LANG_CODE_WITH_SLASH（^[a-zA-Z]{2}/$）→ 结构跳过",
     "EN/ 回显判 target_script_mismatch", "双语文本语种行", "0.25.0"),
    ("butterflies-episode-1", "识别",
     "多行单字符键位映射回显恒败（k\\nm\\n/\\nh）",
     "键盘快捷键组合提示无译义，多行单字符形态未覆盖",
     "_SINGLE_CHAR_KEYMAP_LINES（每行恰好 1 字符，≥2 行）→ 结构跳过",
     "键位提示判 target_script_mismatch", "快捷键提示文本", "0.25.0"),
    ("butterflies-episode-1", "识别",
     "XXXX 占位名回显失败（XXXX t'a）",
     "游戏内未命名角色/玩家的标准占位名，翻译无意义",
     "_XXXX_PLACEHOLDER_NAME（^XXXX(?: [A-Za-z]+(?:'[a-z]+)?)?$）→ 结构跳过",
     "XXXX t'a 回显判 untranslated_text", "占位名文本", "0.25.0"),
    ("butterflies-episode-1", "识别",
     "credit 名单两列对齐行回显失败（kangaroovindaloo    qubodup 8 条）",
     "制作人名单用多空格对齐两列，无句子虚词，credit 判定未覆盖对齐形态",
     "_CREDIT_ALIGNED（双 token 多空格分隔+无虚词）→ is_credit_like 跳过",
     "名单行回显判 untranslated_text", "credit 对齐名单", "0.25.0"),
    ("butterflies-episode-1", "识别",
     "音乐合作名单回显失败（Highraiser ft. inkoutlines, MC Cruel Addict）",
     "ft.（featuring）合作标签的署名行，credit 判定未覆盖",
     "_FT_CREDIT（\\bft\\.）+无虚词 → is_credit_like 跳过",
     "音乐人名单回显判 untranslated_text", "ft. 合作名单", "0.25.0"),
    ("butterflies-episode-1", "翻译",
     "VSync 回显被判 target_script_mismatch",
     "VSync 是驼峰技术缩写+UI 词典词：camel 豁免过 quality 门，proper_name_echo 的 UI 词检查仍拦截",
     "proper_name_echo UI 词检查跳过驼峰技术缩写（全大写 SFX 仍拦截）",
     "VSync 回显判失败", "驼峰缩写 UI 术语", "0.25.0"),
    ("butterflies-episode-1", "翻译",
     "译文引号内黑话词+中文解释被判失败（\"funk\"）",
     "模型保留原文俚语词加引号+中文解释是本地化惯例，quoted_proper_terms 只豁免 TitleCase",
     "quoted_proper_terms 放宽：引号内全 TitleCase 或全非 UI 词典词（funk）→ 豁免；UI 词典词 \"play\" 仍失败",
     "（……她刚才说的\"funk\"是什么意思？）判失败", "引号强调黑话词", "0.25.0"),
    ("containment-breach-hd-edition", "识别",
     "Language/EN/subtitles.jsonc 被逐行提取（639 条 JSON 行落 plain 全失败）",
     ".jsonc 后缀不在 extractor JSON 列表（.json/.json5/.jsonl/.ndjson/.arb），"
     "JSON 文件按文本逐行提取，行含键:值结构",
     "extractor JSON 后缀列表加 .jsonc（extract_json 内部 _mask_jsonc 已支持注释剥离）",
     "JSON 行回显/半翻判失败", "jsonc 后缀漏识别", "0.25.0"),
    ("containment-breach-hd-edition", "识别",
     "三段程序集名回显判失败（DeferredFog, ScpGame, Version=…）",
     "_ASSEMBLY_REF 两段 pattern（Namespace.Type, Version=）停在第一个逗号，"
     "不匹配命名空间类型后还有组名的三段全名",
     "_ASSEMBLY_REF 扩展 ^[^,]+(?:,[^,]+)*,\\s*Version= 支持任意前缀段",
     "程序集全名回显判 untranslated_text", "三段程序集引用", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "游戏自带中文语言包条目被回译成英文判 target_script_mismatch（警卫→guard）",
     "Language/CH/*.subs 原文即中文，模型按 zh-CN 处理反回译英文",
     "首译前拦截：原文含 CJK 且无假名 → 原样保留 + meta language_source_kept",
     "中文原文被模型回译判失败", "中文语言包回译", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "西语/俄语源 37 条全降级链失败（Aleación→日文假名乱入、Mierda→解释性垃圾、клипборд→音译）",
     "西语/俄语→中文是 1.8B 模型能力边界；双跳/词级补译/同对象译例全部失败；"
     "且 Language/ES|RS 玩家不可见（游戏用 CH 语言包）",
     "多语言源（非日文）降级链终点保留原文放行 + meta language_source_kept；"
     "entry 含 CJK 的日文源仍可译（双跳）不兜底",
     "西语/俄语回显或乱译判失败", "多语言源能力边界", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "Interact hold 批量首译回显 + 专名重译注入 (Interact, Interact) 后整条当术语回显判 glossary_mismatch",
     "TitleCase 动作词（Interact）被误当专名：词级补译跳过 TitleCase，"
     "专名保留引用让模型回显整条短语",
     "BUILTIN_UI_REFERENCES 加 (Interact hold, 交互（长按）) (Interact, 交互)；"
     "_ACTION_VERB_ZH 加 interact/hold 并排除专名引用与小写化豁免（动作词不是专名）",
     "操作提示回显判失败", "动作词专名陷阱", "0.25.0"),
    # ── containment 第二轮（90 失败 → 0，6 项通用机制） ──
    ("containment-breach-hd-edition", "翻译",
     "俄语源 21 条降级链全失败（клипборд→Klipboard 音译、Привет→Hello 英语译文）",
     "西里尔字母完全不在 multilingual 源检测中（只查假名/重音拉丁/罗曼功能词）"
     "→ 无双跳无 D 兜底，模型音译/英语输出判 target_script_mismatch 恒败",
     "_is_multilingual_source 加 _CYRILLIC_RE（[А-Яа-яЁё]）硬特征",
     "俄语文本翻译失败恒败", "西里尔字母源检测缺失", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "西语无重音短句（No me veas→Don't look at me）未被识别 multilingual",
     "西语短句无重音字母无旧表功能词，_is_multilingual_source 漏判",
     "_ROMANCE_FUNCTION_WORDS 补西语高频词（no/me/te/se/el/los/las/que/es/son/"
     "eres/como/cuando/donde…）；no/me 是英语高频词，单命中不判（'No matter' "
     "仍英语），需 ≥2 命中（_ENGLISH_SHARED_ROMANCE_WORDS）",
     "西语真文本判失败", "西语功能词表缺失", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "版本号后缀词残留判失败（0.4.0beta 的 beta：译文为 0.4.0beta和0.4.0版本"
     "的Savefiles是兼容的，判 target_script_mismatch）",
     "SAFE_KEEPERS 把版本号（0.4.0beta）整段剥掉 → digit_adjacent 与 source_terms "
     "在剥后串上计算，beta 数字邻接丢失 → 豁免失效",
     "digit_adjacent_words 与 source_terms_cf 改用原文（不剥 SAFE_KEEPERS）计算",
     "版本后缀词恒败", "版本号剥除破坏豁免", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "Changelog 行首星号规范化判 placeholder_mismatch（' *Added bonus'→'* 加空格'）",
     "模型把 *Added（星号紧接词）规范成 '* ' markdown 列表标记 → extra bullet "
     "占位符，validate 判失败",
     "quality：extra 全为 bullet 且无 missing → 放行（样式规范化无结构风险）",
     "变更日志 bullet 行恒败", "行首星号规范化", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "原文非词典小写词保留判失败 10 条（sdfsdfsdfsdfsdfsdf 开发者乱串/playsub "
     "命令/readme 文件名/contact@邮箱前缀/gugu 组名）",
     "模型正确保留原文词（命令名/乱串/文件名），检查器把它们当普通词漏翻",
     "_kept_word_plausible 形态豁免：键盘噪音（≥8 字符+重复 3-gram）/命令参数"
     "语法（词紧跟 [ 或词在方括号内）/文件引用词（readme/changelog/license/"
     "credits）；email 地址整体进 SAFE_KEEPERS 剥除；普通词（ram）仍判失败",
     "术语保留式翻译判失败", "原文词保留误判", "0.25.0"),
    ("containment-breach-hd-edition", "识别",
     "JSON 数组残留行判失败 42 条（\"chara_guard\",→'chara Guardian'、null,→NULL，）",
     "kv 语言文件逐行提取出 JSON 数组元素/字面量行（结构数据无译义），"
     "模型音译/大写化恒败",
     "is_hard_structural 加 _JSON_IDENTIFIER_STRING_LINE（^\"标识符\",$）与 "
     "_JSON_LITERAL_LINE（null/true/false/nil/none,）→ 结构跳过",
     "JSON 残留行翻译失败", "JSON 数组行结构判定", "0.25.0"),
    ("containment-breach-hd-edition", "识别",
     "credit 名单/署名行判失败 3 类（Turtle Sandwich/Catnipbuddy 回显判 "
     "glossary_mismatch、Russian - Nattakara 译者名被音译成俄语、Chinese "
     "Localization by: gugu 组名残留）",
     "作者/团队名单与本地化署名行形态未覆盖：斜杠名单（含虚词判定）、"
     "语言名+连字符+人名、Localization by: 组名",
     "is_credit_like 加 _SLASH_NAME_LIST（斜杠任一侧 ≥2 词，UI 双选项 Click/Tap "
     "不误伤）与 _LANG_CREDIT_LINE（语言名词表开头）；_CREDIT_ATTRIBUTION 加 "
     "localization/translation by 分支",
     "credit 行翻译失败", "credit 名单形态缺失", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "语言名回显判失败 6 条（Español→Español 判 target_script_mismatch）",
     "Español 含独立小写词 → proper_name_echo 的 has_independent_lower_word "
     "分支拒绝；语言名保留原名是业界惯例",
     "proper_name_echo 加 _is_language_name 豁免（知识库语言名词表，跨游戏通用）",
     "语言选择器语言名恒败", "语言名回显误判", "0.25.0"),
    ("containment-breach-hd-edition", "识别",
     "音效/情绪标注判失败 6 条（*SIGH*→* sigh * 模型规范化小写回显）",
     "星号包裹全大写标注是 SFX 字幕无译义内容，模型回显小写变体被判 "
     "placeholder_mismatch+小写残留",
     "_ASTERISK_CAPS_LABEL（^\\*[A-Z]{2,}\\*(?:\\s+.*)?$）→ 结构跳过；"
     "星号强调真实词（*Attention* 驼峰形态）不受影响",
     "音效标注恒败", "星号标注结构判定", "0.25.0"),
    ("containment-breach-hd-edition", "识别",
     "次要语言包文本判失败 2 条（Language/ES/drinks.subs 的 Expreso→Expresso "
     "近似回显、Mierda→解释式垃圾）",
     "游戏自带多语言包（ES/DE/RS/CH…）：汉化版玩家不会以西语/德语游玩，"
     "翻译无意义；西语无重音单词（Expreso）无法判 multilingual，模型近似"
     "回显/输出解释段落恒败；中文包（CH）翻译反而破坏游戏自带中文",
     "extractor：路径含 Language/Languages/Lang/Langs 目录且语种目录非英文"
     "（2-3 字母代码或语言全名）→ 全部条目跳过（保留写回完整性）；"
     "仅 EN/English 语言包保留翻译",
     "语言包文本恒败", "次要语言包误提取", "0.25.0"),
    ("containment-breach-hd-edition", "识别",
     "markdown 加粗段落行判失败 4 条（Changelog/ReadMe 的 "
     "\\t**All languages are loaded from the \"languages.langs\" json file…）",
     "README/Changelog 文档说明行（行首 [ \\t]** 无闭合标记）是开发者文档"
     "非游戏文本；模型对 ** 段内词稳定保留/半翻 → target_script_mismatch 恒败",
     "is_hard_structural 加 _MD_BOLD_LEAD（^[ \\t]*\\*\\*[^*]*$：行首 ** 且"
     "行内无其他星号）；含闭合 ** 的对话强调（**Bold** text）不受影响",
     "文档说明行恒败", "markdown 加粗行结构判定", "0.25.0"),
    ("containment-breach-hd-edition", "识别",
     "人名+昵称署名判失败 2 条（Sam Lynch (\"InnocentSam\") 括号引号昵称，"
     "sharedassets7 TextAsset credits 块）",
     "作者名+昵称署名行无句子结构，模型保留人名合理但被判 glossary_mismatch",
     "is_credit_like 加 _PERSON_WITH_NICKNAME（TitleCase 名 + 括号引号昵称，"
     "剥昵称后主体纯名字无虚词）；对话行（He said (\"What?\") wait for me）"
     "含小写词不匹配",
     "署名行恒败", "人名昵称 credit 形态缺失", "0.25.0"),
    ("containment-breach-hd-edition", "识别",
     "资源副本实例名判失败 1 条（CreditsVolume (1) Profile：MonoBehaviour "
     "rawstr，模型输出解释式垃圾）",
     "Unity 场景对象命名惯例「名 (编号) 名」全 TitleCase，无译义；"
     "模型对资源名输出 '参考以下翻译：' 解释段落",
     "is_hard_structural 加 _CLONE_NUMBERED（全 TitleCase 词 + 数字括号）；"
     "交互提示（Press (1) to start 含小写词）不匹配",
     "资源名恒败", "资源副本名结构判定", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "解释式垃圾输出判失败 2 条（Mierda→'该文本看起来像是随机组合的文字…"
     "以下是可能的解释：'；CreditsVolume (1) Profile→'参考以下翻译：'）",
     "模型把翻译不了的词当成提问，输出解释段落而非译文——解释句式出现在"
     "目标语言内容里即垃圾",
     "quality 解释垃圾检测：_EXPLANATORY_PREFIX（译文：前缀，任何长度）"
     "+ _EXPLANATORY_PATTERN（以下是可能的解释/参考以下翻译/该文本看起来"
     "像是/没有明确的含义，≥20 字符）→ 判 explanatory_prefix；"
     "「以下是重要信息」不在模式内不误伤",
     "解释垃圾输出", "解释式输出检测", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "语言名回显同 obj 场景复发 5 条（level1-6 assets 多语言数组：English "
     "先译成功 → Español 回显被判 target_script_mismatch）",
     "proper_name_echo 的 _obj_reference_pairs 分支（同 obj 已有成功译文 → "
     "多语言源须翻译）在语言名上错误生效——语言名保留原名是业界惯例，"
     "与上下文无关",
     "proper_name_echo 多语言源条件改为 (_is_language_name 或非多语言源) "
     "或 proper_name 或无同 obj 译例——语言名恒豁免",
     "语言名同 obj 恒败", "语言名豁免优先级", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "hipster ipsum 占位文本回显判失败 5 条（level3-6 assets：'XOXO keytar "
     "glossier mumblecore. Tote bag listicle normcore kinfolk kogi hoodie…'）",
     "hipster 风格 lorem ipsum 生成器文本（与 Lorem ipsum 同性质占位），"
     "无真实语义；is_lorem_ipsum_placeholder 只覆盖古典 lorem 词表",
     "is_lorem_ipsum_placeholder 加 _HIPSTER_IPSUM_WORDS（keytar/mumblecore/"
     "kinfolk/kogi…37 词，子串匹配 ≥4 词命中即占位）；真实文本不会同句堆 "
     "4 个 hipster 词",
     "hipster 占位回显恒败", "hipster ipsum 占位检测", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "译文混入韩文单字判失败 1 条（EN 语言包：'该基金会의官方口号' 的 의——"
     "Hy-MT2 多语言模型中英翻译偶发输出韩文）",
     "模型输出目标脚本外的单字符（韩文助词 의），target_script_mismatch 正确"
     "捕获但重试稳定复发（模型稳定瑕疵）",
     "_apply_quality 外语单字自愈：原文纯 ASCII + 混入字符 ≤2 个不在原文 + "
     "每个混入字符夹在中文中间（左右邻都是汉字）→ 确定性删除后重新判定；"
     "独立成词的外语内容（爱丽丝 설정）与假名词尾（設定です）不清洗仍判失败",
     "外语单字混入恒败", "外语单字自愈", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "hipster 占位文本翻译而非回显判失败 4 条（level3-6 assets：模型输出"
     " 'XOXO：Keytar风格，更精致、更柔和。' 中文翻译）",
     "模型对占位文本行为随机：回显→is_lorem_ipsum_placeholder 豁免路径、"
     "翻译成中文→多行内容比对 newline/line_content_mismatch 恒败——"
     "回显豁免只覆盖随机行为的一半",
     "hipster 检测下沉 placeholders.py（quality 已导入 placeholders，"
     "反向导入成环），is_hard_structural 直接跳过——占位文本根本不进"
     "翻译，回显/翻译两条路径都不再发生",
     "hipster 翻译恒败", "hipster 结构跳过", "0.25.0"),
    ("containment-breach-hd-edition", "翻译",
     "译文混入独立韩文实义词判失败 2 条（EN 语言包与 sceneStrings：'最致命"
     "的 상황；同时' 的 상황=情况——带空格隔开、邻中文标点）",
     "外语混入形态升级：从单字助词（의）到独立实义词（상황），左右邻是"
     "空格/分号而非汉字——原 _cjk_surrounded（左右邻汉字）判 False 不清洗",
     "清洗判据升级为块扫描：连续非中文非 ASCII 字母段（混入块）≤4 字符"
     "+ 块前 8 字符与块后 8 字符内都有汉字（句中夹带才删，容忍空格/中文"
     "标点邻居）→ 删除并吞掉块前空白；句尾独立词（爱丽丝 설정）仍不清洗",
     "韩文词混入恒败", "外语混入块自愈", "0.25.0"),
    ("count-my-coins-coin-counter", "识别",
     "YarnSpinner 字符串表键判失败 229 条（sharedassets0.assets obj=1354："
     "line:hash 键 214 个 + DLL #US 2 个；对话文本在邻近字符串，已正确提取）",
     "YarnSpinner 对话以 line:+FNV hash 键引用文本，键不是玩家可见文本——"
     "模型回显恒败（untranslated 216 / target_script 15 双形态）",
     "placeholders 加 _LINE_HASH_IDENTIFIER（^line:[0-9a-fA-F]{6,}$）→ "
     "is_hard_structural 跳过；与 _GUID_IDENTIFIER 同家族（内部键标识）",
     "字符串表键恒败", "line:hash 键结构跳过", "0.25.0"),
    ("count-my-coins-coin-counter", "翻译",
     "UI 词典缩写词回显判失败 1 条（SFX：全大写 3 字母，模型重试耗尽仍回显）",
     "SFX 在 BUILTIN_UI_TERMS（→音效）→ proper_name_echo 的 UI 词检查不豁免"
     "→ target_script_mismatch 恒败；1.8B 模型对单 token 缩写稳定回显"
     "（非驼峰缩写，VSync 式驼峰豁免不覆盖）",
     "proper_name_echo UI 词检查加豁免：len(word)<=3 且 isupper（SFX/BGM/UI"
     "是界面标准术语，保留原文惯例）；词典内其余词（QUIT/Volume）照常要求"
     "翻译",
     "缩写词回显恒败", "全大写缩写豁免", "0.25.0"),
    ("count-my-coins-coin-counter", "识别",
     "插件内部串判失败 3 条（YarnSpinner.dll 'ACTION edge' 节点边标签、"
     "'Can't save variables to JSON: {nameof(variableStorage)}' C# 插值"
     "模板、'(Debug): 1000' 调试 HUD 行）",
     "插件编辑器/调试字符串被当游戏文本：C# nameof 插值未展开=日志模板；"
     "(Debug): 前缀=调试面板输出；全大写节点类型+edge=对话图编辑器标签——"
     "均运行时不可见，模型回显/翻译都失败",
     "placeholders 加三个形态：_C_SHARP_INTERPOLATION（{nameof(/typeof(）"
     "、_DEBUG_PREFIX_LINE（^([Dd]ebug):）、_UPPERCASE_EDGE_LABEL"
     "（^[A-Z]{2,} edge$）→ is_hard_structural 跳过",
     "插件内部串恒败", "C#插值/调试/节点标签跳过", "0.25.0"),
    ("count-my-coins-coin-counter", "翻译",
     "专名保留映射大小写变体误判 1 条（第二轮：Krapos 回显被判 "
     "glossary_mismatch——术语库 KRAPOS→KRAPOS 全大写，译文 TitleCase）",
     "learn_proper_names 保留检测用 casefold（Krapos 变体也学），quality "
     "的 glossary_mismatch 检查 target in normalized 却大小写敏感——"
     "全大写 target 不在 TitleCase 译文里，自相矛盾",
     "glossary_mismatch 检查改 target.casefold() in normalized.casefold()"
     "——专名保留映射与模型回显是形态变体；人工术语（中文 target）不受"
     "影响，模型回显英文仍判失败",
     "专名变体回显恒败", "术语大小写不敏感", "0.25.0"),
    # ── crash-back-in-time（fix-21 家族 7 项，83 失败清零） ──
    ("crash-back-in-time", "识别",
     "InControl 输入插件设备匹配正则被判自然语言（.*x[-]*box[ ]*360.* 等 40 条）",
     "手柄设备数据库的匹配正则含 ^ .* [] () ? $ 元字符，模型回显恒败",
     r"_INPUT_DEVICE_REGEX：^\.\* 开头或 ^+元字符（^ 分支要求首段无空格）→ 结构跳过",
     "正则串翻译恒败", "所有输入插件设备正则", "0.25.0"),
    ("crash-back-in-time", "识别",
     "InControl 设备名/设备说明被判自然语言（ipega/idroid/Joy-Con 等 38 条）",
     "设备名是品牌+型号专名（idroid:con、Joy-Con (R)、ipega media gamepad controller），"
     "模型回显/音译不稳定，翻译破坏运行时按名匹配",
     "_is_input_device_name：冒号品牌 ID/品牌词+设备语境词/括号型号标识/纯品牌专名 四形态 → 结构跳过",
     "设备名翻译恒败", "所有输入插件设备名", "0.25.0"),
    ("crash-back-in-time", "识别",
     "版本占位模板被判自然语言（v?.??）",
     "固件版本正则截断/版本格式模板，含 ? 占位符，模型回显恒败",
     "_INPUT_VERSION_TEMPLATE：含 ? 的版本形态（真实版本号 v2.5 走 _QUALIFIED）→ 结构跳过",
     "版本占位翻译失败", "版本占位模板", "0.25.0"),
    ("crash-back-in-time", "识别",
     "C# 日志拼接模板尾部被判自然语言（CustomController device instance GUID: sourceId = ）",
     "Rewired 设备实例日志前缀，'=' 是拼接点，无显示价值",
     "_GUID_LOG_TEMPLATE（GUID: 词 + = 结尾）→ 结构跳过",
     "日志模板翻译失败", "GUID 日志模板", "0.25.0"),
    ("crash-back-in-time", "识别",
     "首尾空白片段串被判自然语言（' to JSON. '）→ 写回容量截断 object 闸门 WARN",
     "YarnSpinner 错误模板 'Can't save variables to JSON.' 的字符串表拆分碎片，"
     "无完整语义；译文更长时写回按容量截断 → WARN",
     "_WHITESPACE_PADDED_FRAGMENT（首尾空白+非 CJK+≤48 字符，strip 前检测）→ 结构跳过",
     "片段翻译→截断→WARN", "字符串表拆分碎片", "0.25.0"),
    ("crash-back-in-time", "翻译",
     "连字符拼写变体被判英文残留（hihat cymbal→Hi-hat 钹 的 hat）",
     "模型把连写词按标准写法拆分（hihat→Hi-hat 踩镲名），hat 是原文 hihat 的拆分碎片",
     "dehyphenated_variants：译文连字符词去连字符=原文词 → 分词豁免",
     "正确译文误判恒败", "连写-拆写拼写变体", "0.25.0"),
    ("crash-back-in-time", "翻译",
     "单残留词术语半保留重试耗尽（warp 房间：模型稳定输出 warp 残留）",
     "词级补译只处理英文短语（_ENGLISH_PHRASE），单残留词（warp）无补译路径，"
     "quality 判失败重试死循环",
     "词级补译扩展单残留词：补译回显+词在原文 → word_residue_exempt 豁免放行",
     "高质量译文仅一词残留恒败", "游戏术语半保留", "0.25.0"),
]


def main() -> int:
    kb = KnowledgeBase(Path.home() / ".hanhua" / "knowledge.db")
    added = hits = 0
    for game, fail_type, problem, root_cause, fix, symptom, impact, version in CASES:
        new = kb.record_case(
            game=game, fail_type=fail_type, problem=problem,
            root_cause=root_cause, fix=fix,
            symptom=symptom, impact=impact, version=version)
        if new:
            added += 1
        else:
            hits += 1
    cases = kb.search_cases()
    print(f"fail_case 入库 {added} 条（已有命中 {hits} 条），"
          f"库内共 {len(cases)} 条")
    for row in cases:
        print(f"  [{row['kind']}] {row['pattern'][:48]}")
    kb.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
