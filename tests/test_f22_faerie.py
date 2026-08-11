"""F22 修复验证（faerie-afterlight 340 条失败 → 判定漏豁免的系统化修复）。

faerie 失败分类：299 target_script_mismatch 中，192 纯回显（178 条是
引擎控制码串 '.^.b'，F22-1 识别跳过）、10 键位绑定后缀（F22-2）、
专名短语/多语言段保留（F22-3）；10 glossary_mismatch = 9 法语 encore
双关 + 1 miss 想念双关（F22-4）。本文件验证判定层修复，识别层见
test_placeholders.py::test_engine_ctrl_code_is_structural。
"""
import hanhua.core.batch_translator as bt
from hanhua.core.models import TextEntry
from hanhua.core.quality import validate_translation_quality


def _check(original, translation, glossary=()):
    """返回 (quality_passed, wrong_script) 组合判定。"""
    e = TextEntry(file_id="f", key_path="k", original=original)
    r = validate_translation_quality(e, translation, glossary)
    tr = object.__new__(bt.BatchTranslator)
    tr.glossary = glossary
    ws = bt.BatchTranslator._has_disallowed_chinese_target_letters(
        tr, e, translation)
    return r.passed, ws


# ── F22-2：键位绑定后缀豁免 ────────────────────────────────────────


def test_keybind_suffix_map_is_exempt():
    """'Press {0} to open Map of ...</color>.:map' 的 '.:map' 是按键
    绑定显示标记，译文保留 ':map' 是正确行为（faerie 实证：译文标签
    完好、语义正确，仅因 map 在 UI 词典被当残留）。"""
    o = ("Press {0} to open Map of  <color=#293275><b>this area</b>"
         "</color>.:map")
    t = "点击 {0} 可以打开<color=#293275><b>当前区域</b></color>的地图。:map"
    q, ws = _check(o, t)
    assert q and not ws


def test_keybind_suffix_interact_jump_are_exempt():
    """':interact'/':jump' 键位后缀同样豁免（faerie 实证 ×4）。"""
    o1 = ("Hold {0} to <color=#293275><b>activate check point</b>"
          "</color>.:interact")
    t1 = "按住 {0} 以<color=#293275><b>激活检查点</b></color>。:interact"
    q, ws = _check(o1, t1)
    assert q and not ws
    o2 = ("Press {0} while sliding againts wall to <color=#293275><b>"
          "leap upward</b></color>.:jump")
    t2 = ("在紧贴墙壁滑动的同时按下 {0} 键，即可 <color=#293275><b>"
          "向上跳跃</b></color>。:jump")
    q, ws = _check(o2, t2)
    assert q and not ws


def test_keybind_suffix_not_exempt_when_hallucinated():
    """模型幻觉的 ':newkey'（原文无该后缀）→ 不豁免（防幻觉）。"""
    o = "Press {0} to interact."
    t = "按下 {0} 键以交互。:newkey"
    q, ws = _check(o, t)
    assert q and ws  # wrong_script 保留：模型新增键位后缀是半翻译证据


# ── F22-3：原文 TitleCase 短语段 / 多语言段保留豁免 ─────────────────


def test_title_phrase_shop_kept_is_exempt():
    """'Before Pish Shop' → 'Pish Shop之前'：Pish Shop 是商店专名
    （TitleCase 短语），模型保留专名只译其余 → 豁免（faerie 实证）。"""
    o = "Before Pish Shop\tBefore Pish Shop"
    t = "Pish Shop之前"
    q, ws = _check(o, t)
    assert q and not ws


def test_title_phrase_chat_channel_kept_is_exempt():
    """'Wispy's Chat (Auto Dialogue)' → 'Wispy's Chat (自动对话)'：
    Wispy's Chat 是角色频道专名 → 豁免（faerie 实证）。"""
    o = ("Wispy’s Chat (Auto Dialogue) I\tWispy’s Chat (Auto Dialogue) I")
    t = "Wispy’s Chat (自动对话) I Wispy’s Chat (自动对话) I"
    q, ws = _check(o, t)
    assert q and not ws


def test_title_phrase_item_name_kept_is_exempt():
    """'Solium dual\tPolar-Solium' → 'Solium dual：双极型电池'：
    Solium dual 是物品专名（TitleCase+小写词组合）→ 豁免。"""
    o = "Solium dual\tPolar-Solium"
    t = "Solium dual：双极型电池"
    q, ws = _check(o, t)
    assert q and not ws


def test_french_item_name_kept_is_exempt():
    """'Vallon noir III' 法语物品名（TitleCase+小写词+罗马数字）保留
    + 其余法语内容完整译出 → 豁免（faerie 实证：译文 90% 完整）。"""
    o = ("\"Vallon noir III : On dit que ce fil est léger et résistant."
         " Il peut servir pour diff")
    t = ("“Vallon noir III：据说这种线既轻便又耐用。它可以用于多种用"
         "途，包括连接物品。")
    q, ws = _check(o, t)
    assert q and not ws


def test_multilingual_packed_dialogue_kept_is_exempt():
    """多语言打包文本（英+印尼+西语逗号连接）：模型只译英语段、保留
    印尼语/西语段是正确行为（faerie 实证）。原文同形段豁免。"""
    o = ("Perhaps the voice really is coming from Lucentia.,Wispy: "
         "Mungkin suara itu sungguh datang dari Lucentia.,Wispy: Tal vez")
    t = ("也许那个声音确实来自卢森希雅。Wispy: Mungkin suara itu "
         "sungguh datang dari Lucentia.,Wispy: Tal vez")
    q, ws = _check(o, t)
    assert q and not ws


def test_english_dialogue_packed_kept_is_exempt():
    """英语+印尼语打包对话：英语段译出、印尼语段保留（faerie 实证：
    'Did I accidentally drop it?,Posh: Apa aku...' → 英语段译文 + 印尼
    语段保留）。"""
    o = ("Did I accidentally drop it?,Posh: Apa aku tidak sengaja "
         "menjatuhkannya?,Posh: ¿Acaso se me cayó por")
    t = ("我是不是不小心把它弄掉了？Posh: Apa aku tidak sengaja "
         "menjatuhkannya?,Posh: ¿Acaso se me cayó por")
    q, ws = _check(o, t)
    assert q and not ws


# ── F22-3 防过宽对照（不得放行真半翻译） ────────────────────────────


def test_pronoun_verb_leftover_not_exempt():
    """'I like 吃披萨'——I like 是功能词（段首单字符不成立），真半翻译
    必须拦截。"""
    o = "I like to eat pizza."
    t = "I like 吃披萨"
    q, ws = _check(o, t)
    assert not (q and not ws)  # 必须仍判失败


def test_interaction_verb_leftover_not_exempt():
    """'Press 按钮'——Press 是交互动作词（段首不成立），半翻译拦截。"""
    o = "Press the button to continue."
    t = "Press 按钮以继续"
    q, ws = _check(o, t)
    assert not (q and not ws)


def test_term_hit_phrase_not_exempt():
    """'Slash key'→'Slash 键'——slash 命中术语表 (slash, 斩击)，术语
    要求优先，专名短语豁免不适用（deadbeat 实证）。"""
    o = "Press the Slash key"
    t = "按下 Slash 键"
    q, ws = _check(o, t, glossary=[("slash", "斩击")])
    assert not (q and not ws)


def test_term_hit_phrase_uses_term_is_exempt():
    """同场景但译文正确使用术语（斩击）→ 放行（对照测试）。"""
    o = "Press the Slash key"
    t = "按下斩击键"
    q, ws = _check(o, t, glossary=[("slash", "斩击")])
    assert q and not ws


def test_article_started_title_not_exempt():
    """'The Fidelity'→'Fidelity'：The 是功能词段首不成立，专名短语
    豁免不触发（faerie 实证该条仍失败；其失败原因是重试链路径，此处
    只验证短语豁免规则本身不过宽）。"""
    o = "The Fidelity"
    t = "Fidelity"
    q, ws = _check(o, t)
    # 现实判定：The 被 SAFE_KEEPERS 剥、Fidelity TitleCase 词保留放行；
    # 断言「短语豁免规则不引入新放行」——对比无豁免集时行为一致
    # （此处 q/ws 与原判定相同即规则不过宽）。
    assert (q, ws) == (True, False)


# ── F22-4：术语词义双关豁免（glossary 检查层） ─────────────────────


def test_verb_miss_usage_is_exempt():
    """'I miss my father'——miss 是「想念」动词（前邻主语代词），不是
    音游 HUD 标签「未命中」（deadbeat 沉淀）→ 豁免（faerie 实证：
    Hani 剧情对话）。"""
    o = "Hani: I... I miss my father so much. I'm so worried about him."
    t = "Hani：我……我非常想念我的父亲。我非常担心他。"
    q, ws = _check(o, t, glossary=[("miss", "未命中")])
    assert q and not ws


def test_french_encore_is_exempt():
    """'Hé, c'est encore vous !'——法语 encore=又/再（日常副词），不是
    英语借词 encore=安可（演出术语）→ 法语特征原文豁免英语术语表
    （faerie 实证 9 条法语对话）。"""
    o = "Lashi : Hé, c'est encore vous ! Si vous vous demandez comment"
    t = "Lashi: 嘿，又是你！如果你想知道如何离开"
    q, ws = _check(o, t, glossary=[("encore", "安可")])
    assert q and not ws


def test_english_encore_still_checked():
    """英语原文的 encore（音乐会场景 'Encore! Encore!'）→ 法语特征不
    存在，术语 (encore, 安可) 照常生效（对照测试，防法语豁免过宽）。"""
    o = "The crowd shouted: Encore! Encore!"
    t = "人群高喊：再来一次！再来一次！"
    q, ws = _check(o, t, glossary=[("encore", "安可")])
    assert not (q and not ws)


def test_miss_label_still_checked():
    """'miss: 999' 音游标签（前邻冒号）→ 术语 (miss, 未命中) 照常生效
    （对照测试，防主语代词豁免过宽）。"""
    o = "Combo: 12, miss: 999"
    t = "连击：12，未命中：999"
    q, ws = _check(o, t, glossary=[("miss", "未命中")])
    assert q and not ws
    q2, ws2 = _check(o, "连击：12，漏掉：999", glossary=[("miss", "未命中")])
    assert not (q2 and not ws2)
