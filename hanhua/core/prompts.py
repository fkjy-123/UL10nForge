from __future__ import annotations
import json
import re
from collections import Counter
from hanhua.core.models import GameProfile


# 游戏叙事/UI 常见词（全大写形态下仍是普通词而非专名）。
# wordfreq top5000 之外、但游戏文本高频的词：UI 控件词、警示词、叙事场景词。
_GAME_COMMON_WORDS = frozenset("""
cavern vacuum caution addict await orbital dungeon portal quest boss enemy monster
labyrinth thrive blight bloom blossom renown fame legend myth saga epic
drown colony haunt ambient anomaly godsend nautical tributary lightyear sober
adrift detect bacteria phenomenon phenomena bacterial bacteriology prolonged
rapturous maelstrom hyperlife hyperspace dumbfuck lifeless crawling
weapon armour armor shield potion spell magic sword dagger bow arrow ammo health
stamina mana inventory equipment treasure chest loot coin goldsilver iron steel
copper bronze crystal gem stone wood leather cloth silk wool cotton rope chain
gate door window wall floor stair room hall chamber corridor tunnel mine shaft
cliff peak ridge valley plain field meadow swamp marsh bog jungle desert oasis
glacier volcano canyon ravine gorge waterfall stream pond beach shore tide wave
vessel craft hull deck stern bow anchor compass lantern torch candle flame smoke
ashes ember spark frost blizzard thunder lightning tempest gale breeze draft
chasm abyss void realm dimension plane nexus portal rift warp gate bridge
merchant vendor trader blacksmith alchemist apothecary priest paladin cleric
warrior mage wizard warlock rogue ranger druid shaman barbarian knight squire
captain admiral general soldier scout sentinel guard warden jailer executioner
king queen prince princess duke duchess lord lady baron baroness count countess
emperor empress regent heir throne crown scepter banner crest sigil emblem seal
prophecy omen vision dream nightmare horror terror dread fear dreadnought siege
invasion assault ambush raid skirmish battle warfare conquest dominion empire
kingdom realm faction guild clan tribe settlement outpost fort fortress citadel
castle keep tower spire cathedral abbey monastery chapel temple sanctuary altar
shrine relic artifact treasure fortune riches wealth poverty famine plague
disease sickness illness wound injury scar bruise poison venom toxin antidote
cure remedy potion elixir tonic salve balm ointment herb root leaf petal thorn
moss fungus spore mold mildew rot decay blight wither wilt bloom blossom sprout
seedling harvest sow reap thresh mill forge smelt cast temper quench harden
sharp dull blunt keen brittle fragile sturdy stout tough sturdy rigid stiff
bend twist warp stretch shrink swell bulge dent scratch crack shatter splinter
fragment shard piece chunk slab block brick stonework masonry plaster mortar
ceiling rooftop chimney hearth fireplace furnace kiln oven stove cauldron kettle
vessel jug flask vial phial bottle jar urn cask keg barrel crate box chest coffer
satchel pouch sack bag wallet purse coinage currency payment ransom bounty reward
prize trophy medal emblem badge ribbon medal award honour glory fame legend myth
fable tale yarn story lore history chronicle record journal diary memoir letter
scroll parchment papyrus tablet inscription carving engraving etching rune sigil
talisman charm amulet pendant locket ring bracelet necklace brooch earring crown
diadem circlet coronet tiara sceptre orb regalia vestment robe cloak cape mantle
hood cowl helm helmet visor gauntlet pauldron greave sabaton cuirass breastplate
hauberk gambeson tunic jerkin doublet surcoat tabard mantle cape scarf shawl
girdle belt sash cummerbund wallet scabbard sheath holster quiver bandolier
trip wire trap snare net cage pen stable barn coop corral paddock pasture meadow
common guild plaza market bazaar souk fair carnival festival feast banquet
gala ball masquerade parade procession ceremony ritual rite custom tradition
superstition folklore legend myth tale story ballad song hymn chant psalm
incantation invocation prayer blessing curse hex jinx charm enchantment
divination scrying augury omen portent presage harbinger herald forerunner
precursor pioneer vanguard front runner leader chief chieftain elder sage
mentor tutor instructor professor lecturer scholar savant genius prodigy
apprentice novice initiate neophyte rookie tyro beginner amateur dilettante
hack charlatan fraud impostor charlatan quack pretender phoney fraud swindler
scammer trickster conman cheat cheater liar deceiver betrayer traitor turncoat
defector renegade rebel insurgent revolutionary agitator instigator provocateur
troublemaker mischief rascal rogue scoundrel villain knave rake cad bounder
gadabout vagrant wanderer drifter nomad gypsy tramp hobo vagabond rover explorer
adventurer pioneer settler colonist frontiersman prospector miner hunter trapper
fisherman fisher angler sailor seaman mariner navigator pilot coxswain helmsman
lookout watchman sentinel sentry picket patrol scout spy agent operative courier
messenger herald crier announcer presenter host emcee mc mastermistress
overseer supervisor manager director chief head boss leader captain general
admiral marshal commander officer sergeant corporal private recruit cadet
lieutenant captain colonel major general admiral commodore fleet armada flotilla
squadron battalion regiment brigade division corps army navy airforce marine
infantry cavalry artillery engineer medic doctor nurse surgeon physician apothecary
alchemist chemist pharmacist druggist herbalist healer shaman witch wizard
sorcerer warlock necromancer conjurer summoner enchanter illusionist mage
spellcaster thaumaturge theurgist pyromancer cryomancer geomancer aeromancer
hydromancer technomancer biomancer chronomancer spatial temporal gravitic
kinetic electrostatic thermal cryogenic combustion detonation implosion
explosion blast bang boom pop fizz hiss sizzle crackle snap pop fizzle
sparkle shimmer glimmer gleam glow shimmer glitter shine radiance brilliance
luminosity phosphorescence bioluminescence incandescence luminescence
fluorescence iridescence opalescence pearlescence prismatic kaleidoscopic
chromatic monochrome polychrome rainbow spectrum gradient hue shade tint
tonality saturation brightness contrast luminance intensity vividness
muted pastel neon fluorescent electric primary secondary tertiary analogue
digital virtual simulated simulated synthetic artificial organic inorganic
mineral metallic crystalline glassy vitreous ceramic porcelain pottery earthenware
stoneware terracotta clay adobe brickwork masonry concrete cement plaster
stucco render lime mortar grout filler putty sealant adhesive glue paste gum
resin pitch tar asphalt bitumen wax paraffin tallow lard grease oil lubricant
solvent thinner diluent reducer catalyst reagent solvent acid alkali base
salt compound mixture solution suspension emulsion colloid foam gel paste
ointment balm salve liniment lotion cream powder granule pellet tablet
capsule pill lozenge troche pastille drop dose dosage regimen schedule cycle
course session period phase stage step tier level rank grade class tier bracket
division league conference association federation union alliance coalition
partnership consortium syndicate cartel monopoly trust merger acquisition
takeover buyout leverage capital investment finance funding subsidy grant
stipend scholarship bursary allowance wage salary income revenue profit
dividend interest principal collateral security guarantee warranty deposit
installment annuity pension retirement savings nest egg rainy day fund
emergency reserve contingency plan fallback backup alternative option choice
possibility probability likelihood chance odds risk hazard danger peril
threat menace jeopardy vulnerability weakness frailty fragility brittleness
delicacy fragility vulnerability exposure susceptibility sensitivity
resistance immunity tolerance adaptation acclimation habituation conditioning
training practice drill exercise routine regimen discipline habit custom
tradition convention norm standard benchmark baseline reference point
milestone landmark benchmark yardstick criterion gauge measure metric
indicator barometer litmus bellwether harbinger omen portent augury
omen premonition forewarning foreshadowing hint clue inkling intimation
suspicion doubt uncertainty ambiguity vagueness obscurity opacity
clarity precision accuracy fidelity authenticity genuineness validity
reliability consistency uniformity constancy stability equilibrium balance
harmony symmetry proportion scale ratio rate frequency interval distance
displacement velocity acceleration momentum impulse force energy power
work effort labor toil exertion strain stress tension pressure load
weight mass density volume capacity size dimension extent magnitude
""".split())


def _build_common_words() -> frozenset[str]:
    """英语基础词表（wordfreq top5000 ∪ 游戏叙事补充词）。

    wordfreq 缺失时降级为内置精简词表（仅覆盖最常用词），
    专名收集偏保守（多收几个词、少丢专名），不阻断流程。
    """
    try:
        from wordfreq import top_n_list
        return frozenset(top_n_list("en", 5000)) | _GAME_COMMON_WORDS
    except Exception:  # noqa: BLE001  wordfreq 未安装时降级
        return _GAME_COMMON_WORDS


_COMMON_WORDS = _build_common_words()


# 全大写词形：游戏文本常全大写强调（大写叙事/警示牌），只有词典外的
# 全大写词（外星地名/人名/造词）才可能是专名；常见词全大写仍是普通词。
_UPPER_WORD = re.compile(r"\b[A-Z][A-Z0-9]{2,}(?:-[0-9]+)?\b")


def _is_common_word(w: str) -> bool:
    """词表命中（含常见词形变化：复数 s/es、过去式 ed、进行时 ing）。"""
    wl = w.lower()
    if wl in _COMMON_WORDS:
        return True
    if len(wl) > 5:
        if wl.endswith("ing") and (wl[:-3] in _COMMON_WORDS
                                   or wl[:-3] + "e" in _COMMON_WORDS):
            return True
        if wl.endswith("es") and wl[:-2] in _COMMON_WORDS:
            return True
        if wl.endswith("ed") and (wl[:-2] in _COMMON_WORDS
                                  or wl[:-2] + "e" in _COMMON_WORDS):
            return True
    if wl.endswith("s") and wl[:-1] in _COMMON_WORDS:
        return True
    return False


def collect_known_names(texts: list[str], min_occur: int = 2,
                        min_len: int = 5) -> list[str]:
    """从全部提取文本中收集疑似专名（全大写 + 词典外）注入翻译 prompt。

    启发式：全大写且不在英语基础词表的词，按出现频率排序；
    高频（≥min_occur）或长词（≥min_len，一次性出现也收）判定为专名。
    间隔大写（Y A W N）、普通词全大写（YOU/THE/CAUTION）不会被误收。
    返回最多 50 个（与 build_system_prompt 的注入上限一致）。
    """
    counter: Counter[str] = Counter()
    for t in texts:
        for m in _UPPER_WORD.findall(t or ""):
            if _is_common_word(m):
                continue
            counter[m] += 1
    names = [
        w for w, c in counter.items()
        if c >= min_occur or len(w) >= min_len
    ]
    names.sort(key=lambda w: (-counter[w], len(w)))
    return names[:50]


# 按提取器 reason / role 注入的专项翻译策略（指南 §4.2 角色策略）。
# 匹配优先级：条目 reason（提取器细粒度分类）→ 条目 role（兜底）。
# 细粒度 role（dialogue/quest_objective/...）当前提取器尚未产出，先定义好，
# 未来产出时自动生效；现有 reason 键立即生效。
ROLE_RULES: dict[str, str] = {
    # ---- reason 键（extractor._classify_object / v2 提取器产出）----
    "interaction_prompt": (
        "【专项·交互提示】这是操作提示（如 \"Press E to open\"）：保持简短，"
        "原样保留按键名与操作结构（按下/点击/拖拽），不得扩写或口语化改写。"),
    "single_visible_string": (
        "【专项·UI 控件文本】这是 UI 控件的唯一可见文本（按钮/标题/标签）："
        "按中文界面习惯用语翻译（\"开始游戏\"而非\"启动游戏之旅\"），保持简短。"),
    "core_menu_collection": (
        "【专项·主菜单项】这是游戏主菜单项：使用通用游戏菜单译名"
        "（开始游戏/继续/设置/选项/退出/加载存档），全游戏保持同一套译名。"),
    "core_menu_control": (
        "【专项·菜单控件】这是菜单控件状态/标签：使用标准中文界面用语，保持简短。"),
    "natural_language": (
        "【专项·对话/叙述】这是游戏对话或叙述文本：口语化翻译，贴合角色语气，"
        "拒绝翻译腔和欧化句式，保持原文的行数与分段。"),
    "object_has_display_evidence": (
        "【专项·界面显示文本】这是游戏内界面显示的短文本：按界面习惯用语翻译，"
        "不逐字直译，保持简短。"),
    "display_phrase": (
        "【专项·显示短语】这是界面/物品/存档描述短语：语义贴切、用词自然，"
        "专名部分按术语表处理。"),
    "localization_key_value": (
        "【专项·本地化键值】这是本地化表键值：译文保持简短，术语表译名必须严格遵循，"
        "键名与格式占位符不得改动。"),
    "dialogue_line": (
        "【专项·对话行】这是对话/字幕行：口语化、符合说话人身份，保留换行结构。"),
    # ---- role 键（兜底；细粒度角色未来由提取器产出）----
    "menu_button": (
        "【专项·菜单按钮】保持简短，符合中文界面习惯用语"
        "（\"设置\"而非\"设定选项\"），全游戏译名一致。"),
    "dialogue": (
        "【专项·对话】口语化翻译，贴合角色性格与语境，拒绝翻译腔；"
        "保留行数与分段结构。"),
    "quest_objective": (
        "【专项·任务目标】按中文任务目标惯例翻译（\"前往...\"\"击败...\"\"收集...\"），"
        "动作明确、用词简洁，任务名词严格使用术语表译名。"),
    "item_name": (
        "【专项·道具名】道具名翻译需简洁有力、贴合世界观；术语表指定译名必须严格遵循。"),
    "item_description": (
        "【专项·道具描述】描述语义准确、语气贴合游戏世界观，不添加原文没有的信息。"),
    "system_error": (
        "【专项·系统提示/错误】保持专业、准确、简洁；错误码与占位符原样保留。"),
    "subtitle": (
        "【专项·字幕】口语化、贴合语气，按说话节奏断句，保留换行结构。"),
    "format_template": (
        "【专项·格式模板】这是带占位符的模板文本：只翻译可见文字部分，"
        "所有占位符、格式标签、转义序列必须逐字原样保留。"),
    "proper_name": (
        "【专项·专名】这是人名/地名/专有名词：使用术语表指定译名；"
        "无指定时保留原文或按中文惯例音译，不得自由意译。"),
}


# #10：游戏本地化歧义词（Style 层面）——英文游戏文本中语义随语境变化
# 的常见词。模型脱离语境直译是「play→播放、resume→简历」的来源：
# 游戏界面语境下这些词几乎总是游戏操作/界面语义，禁止按通用词典义翻译。
_GAME_CONTEXT_WORDS: list[tuple[str, str, str]] = [
    ("play", "游戏界面/操作", "开始游戏、游玩（按钮上的 Play 是\"开始\"，不是\"播放\"）"),
    ("resume", "游戏界面/操作", "继续（游戏）——上一存档/暂停后继续，不是\"简历\""),
    ("load", "游戏界面/操作", "读取/加载（存档）"),
    ("save", "游戏界面/操作", "保存（存档）"),
    ("quit", "游戏界面/操作", "退出（游戏）"),
    ("back", "游戏界面/操作", "返回（上一界面）"),
    ("new game", "游戏界面/操作", "新游戏/开始新游戏"),
    ("continue", "游戏界面/操作", "继续（游戏）"),
    ("settings", "游戏界面/操作", "设置（界面项），不是\"设置项复数\"直译"),
    ("options", "游戏界面/操作", "选项/设置"),
    ("inventory", "游戏界面/操作", "背包/物品栏"),
    ("attack", "战斗语境", "攻击"),
    ("quest", "游戏任务语境", "任务"),
    ("enemy", "游戏战斗语境", "敌人"),
    ("level", "游戏语境", "关卡/等级（视语境），不是\"水平/级别\"直译"),
    ("screen", "游戏语境", "界面/画面（\"loading screen\"=加载画面），不是\"屏幕\"直译"),
    ("press any key", "操作提示", "按任意键"),
    ("select", "游戏界面/操作", "选择"),
    ("confirm", "游戏界面/操作", "确认"),
    ("cancel", "游戏界面/操作", "取消"),
]


def _game_context_rules() -> str:
    """游戏语境歧义词：20 词压缩为一行「词→核心译名」映射。

    2026-08-14 用户要求「大大精简提示词」：原格式每条带语境列与长说明
    （≈800 字符），压缩后 ≈300 字符；防直译提示（play 不是"播放"、
    resume 不是"简历"）保留在规则头。
    """
    pairs = "、".join(
        f"{word}→{tip.split('（')[0].split('(')[0].strip()}"
        for word, context, tip in _GAME_CONTEXT_WORDS)
    return ("【游戏语境歧义词】按游戏语境翻译，禁止按通用词典义直译"
            f"（play 不是\"播放\"、resume 不是\"简历\"）：{pairs}")


def build_game_context_block(profile) -> str:
    """设计文档 §15/16：Game Context 注入块——翻译与审校共用同一份数据。

    只注入简短核心信息（【游戏背景】【游戏简介】【语言风格】【相关角色】
    【相关术语】【翻译注意事项】），不膨胀上下文（§12）；无语境时返回
    空串。profile 兼容 GameProfile dataclass 与任意含 context_* 字段的
    对象（getattr 防御，测试桩/mock 不崩）。
    """
    parts: list[str] = []
    g = lambda key: str(getattr(profile, key, "") or "")
    gl = lambda key: [str(x) for x in (getattr(profile, key, None) or [])]
    if g("context_game_name") or g("context_genre") or g("context_setting"):
        bg = "，".join(p for p in (
            g("context_game_name"), g("context_genre"), g("context_setting"))
            if p)
        if bg:
            parts.append(f"【游戏背景】{bg}")
    if g("context_summary"):
        parts.append(f"【游戏简介】{g('context_summary')}")
    if g("context_style"):
        parts.append(f"【语言风格】{g('context_style')}")
    chars = gl("context_characters")[:20]
    if chars:
        parts.append(f"【相关角色】{'、'.join(chars)}")
    terms = gl("context_terms")[:30]
    if terms:
        parts.append(f"【相关术语】{'、'.join(terms)}")
    notes = gl("context_translation_notes")[:5]
    if notes:
        parts.append(f"【翻译注意事项】{'；'.join(notes)}")
    return "\n".join(parts)


def build_system_prompt(profile: GameProfile, glossary_lines: list[str] | str,
                        known_names: list[str] | None = None,
                        knowledge_lines: list[str] | str | None = None) -> str:
    """精简版 system_prompt（2026-08-14 用户要求：大大精简提示词）。

    只保留：本地化角色 + 精炼翻译规则 + 语境歧义词。术语表/专名/知识库
    不再全量注入——由 BatchTranslator 按条目检索命中注入（user prompt 内
    glossary_hits / knowledge_hits + 向量召回 _context_reference_lines，
    见 build_batch_user_prompt 与 batch_translator._build_item）。全量注入
    是 request exceeds context（--ctx-size 6144 实际 2048 实证）与注意力
    稀释的根因。参数保留仅为调用方兼容，不再渲染。
    """
    src = profile.source_lang
    if src == "auto":
        src = "游戏原文语言（自动判断，可能是英语/日语/韩语等）"
    parts = [
        # #10：明确的游戏本地化角色 + 行为边界（用户提供的角色定义精简版）
        f"你是专业游戏本地化翻译专家，负责把该游戏的{src}文本翻译为简体中文。"
        "你不是普通机器翻译器，而是游戏本地化译者：译文必须像中文玩家母语中"
        "看到的游戏文本，而非逐词直译的机器翻译结果。",
        "职责边界：你只做本地化翻译——不修改原文信息、不续写、不解释、不输出"
        "翻译说明；所有译文直接面向玩家，使用目标语言读者的自然表达。",
    ]
    if profile.game_name:
        parts.append(f"【游戏】{profile.game_name}" + (f"（{profile.genre}）" if profile.genre else ""))
    if profile.world_setting:
        parts.append(f"【世界观设定】{profile.world_setting}")
    if profile.tone_notes:
        parts.append(f"【文风要求】{profile.tone_notes}")
    # #10：Style/Personalization——用户自定义提示词（按游戏档案编辑）优先
    if profile.prompt_style:
        parts.append(f"【个性化风格要求（用户自定义，最高优先）】\n{profile.prompt_style}")
    # 设计文档 §15：Game Context 注入（翻译/审校共用同一份数据，§12
    # 不膨胀）。user-facing 游戏介绍 与 model-facing Game Context 同源。
    ctx_block = build_game_context_block(profile)
    if ctx_block:
        parts.append(ctx_block)
    parts.append(
        "【翻译规则】\n"
        "1. 原样保留所有占位符与格式标签（如 {0}、{name}、%s、<b>、<color=...>、[b]、\\n），不得增删改序。\n"
        "2. 全大写文本（字幕、UI 标题、[ S K I P ] 式标签）照常翻译成自然中文，"
        "不要因原文是大写而保留英文；但专名与品牌名（Playstation/Steam/Xbox 等）保留原文。\n"
        "3. 除专名、品牌名、按键名外，任何英文单词或短语（含 hello、back、press any key "
        "等短文本）都必须译为中文，禁止原样回显。\n"
        "4. 严格对照原文：不得续写、不得自行补全，不得改变行数，"
        "换行符保持原文形式（\\r\\n 与 \\n 不得相互转换）。\n"
        "5. 只输出 JSON，不要输出任何其他文字或代码块标记。\n"
        "6. 全大写且字母间有空格的词（如 * Y A W N *、G A S P、S C O F F）是文字化动作/"
        "音效表现（打哈欠/惊呼/叹息）：译为中文动作词或拟声词（* 哈欠 *、* 倒吸一口气 *），"
        "保留原文的星号与格式标签；仅当是人名/地名等专名时保留原文。",
    )
    parts.append(_game_context_rules())
    return "\n".join(parts)


def _role_rule_for(item: dict) -> str | None:
    """按条目 reason（优先）→ role（兜底）匹配专项翻译策略。"""
    reason = str(item.get("reason") or "")
    if reason in ROLE_RULES:
        return ROLE_RULES[reason]
    role = str(item.get("role") or "")
    if role in ROLE_RULES:
        return ROLE_RULES[role]
    return None


def build_batch_user_prompt(items: list[dict]) -> str:
    """items: [{id, text, context?, short?, reason?, role?}] → 要求模型按 JSON 数组返回。"""
    lines = [
        "请翻译以下游戏文本，返回严格 JSON 数组，每项形如 {\"id\": \"<原文id>\", \"translation\": \"<中文译文>\"}，"
        "id 必须一一对应且不遗漏。注意：译文中的英文双引号必须写成 \\\" 转义，换行写成 \\n，"
        "否则 JSON 无法解析。只输出 JSON，不要输出任何其他文字：",
        "",
    ]
    for it in items:
        if it.get("file"):
            lines.append(f"[来源文件] {it['file']}")
        if it.get("key_path"):
            lines.append(f"[定位键] {it['key_path']}")
        if it.get("role"):
            lines.append(f"[文本角色] {it['role']}")
        rule = _role_rule_for(it)
        if rule:
            lines.append(rule)
        if it.get("confidence"):
            lines.append(f"[识别置信度] {it['confidence']}")
        if it.get("context"):
            lines.append(f"[上下文] {it['context']}")
        if it.get("short"):
            lines.append("[标注] 下一条为 UI 短文本，保持简短")
        glossary_hits = it.get("glossary_hits")
        if glossary_hits:
            lines.append(
                "[术语命中] 本条原文包含以下术语，译文必须使用指定译名：" +
                "；".join(f"{s} → {t}" for s, t in glossary_hits))
        knowledge_hits = it.get("knowledge_hits")
        if knowledge_hits:
            # 2026-08-14 知识检索注入：只注入本条原文命中的知识对照
            # （match_text 精确命中），不再全量拼 system_prompt——全量
            # 注入稀释注意力且膨胀上下文（request exceeds context 根因
            # 之一）。格式与 format_for_prompt 一致（""译名"应译为…"）。
            lines.append(
                "[知识命中] 本条原文命中历史特殊文本规则：" +
                "；".join(
                    f"“{p}”应译为“{t}”"
                    for p, t, *_ in knowledge_hits))
        input_tokens = it.get("input_tokens")
        if input_tokens:
            lines.append(
                "[输入按键] 译文必须原样保留：" +
                "、".join(str(token) for token in input_tokens))
        budget = it.get("budget")
        if budget:
            lines.append(f"[长度预算] 下一条译文不得超过 {budget} 个字符（二进制存储限制，超出会被截断）")
        lines.append(f'{json.dumps(it["id"], ensure_ascii=False)}: {it["text"]}')
    return "\n".join(lines)
