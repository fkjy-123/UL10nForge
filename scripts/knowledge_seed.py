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
