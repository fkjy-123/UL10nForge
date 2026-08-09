import json
import threading
import time
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from hanhua.core.batch_translator import BatchTranslator
from hanhua.core.memory import ProjectStore
from hanhua.core.models import TextEntry, is_actionable_translation
from hanhua.core.translator import BaseClient, Usage


class FakeClient(BaseClient):
    """按原文映射翻译的假客户端。"""

    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.calls = 0

    def chat(self, system, messages):
        self.calls += 1
        out = []
        for m in messages:
            for line in m["content"].splitlines():
                if '": ' in line:
                    kid, text = line.split('": ', 1)
                    kid = kid.strip().strip('"')
                    out.append({"id": kid, "translation": self.mapping.get(text, "译文")})
        return json.dumps(out, ensure_ascii=False), Usage(10, 5)


def _entries(n=60):
    return [{"file_id": "f", "key_path": f"k{i}", "original": f"text{i}"} for i in range(n)]


@pytest.mark.parametrize(
    ("role", "disposition", "expected"),
    (("display", "structural", False),
     ("structural", "translate", True),
     ("display", "preserve", False)),
)
def test_actionability_uses_disposition_as_authoritative_scope(
        role, disposition, expected):
    entry = TextEntry(
        "f", "k", "Press E", meta={
            "role": role, "disposition": disposition, "confidence": "high",
        })
    assert is_actionable_translation(entry) is expected


def test_failed_entries_are_retried_on_next_run():
    # 质量门失败的条目不永久卡死：下次翻译会重试
    # （否则「质量门失败原因：untranslated_text N」统计残留，用户看到
    #  的就是翻译失败卡死的旧条目）
    entry = TextEntry(
        "f", "k", "Hello, my name is Mitch.", translation="Hello, my name is Mitch.",
        status="failed", meta={
            "role": "display", "disposition": "translate", "confidence": "high",
            "quality_passed": False, "quality_reasons": ["untranslated_text"],
        })
    assert is_actionable_translation(entry) is True

    client = FakeClient(mapping={"Hello, my name is Mitch.": "你好，我叫米奇。"})
    stats = BatchTranslator(
        client, batch_size=1, concurrency=1, lang="en→zh-CN",
    ).run([entry])
    assert client.calls == 1
    assert stats.done == 1 and stats.failed == 0
    assert entry.status == "translated"


def test_skipped_entries_never_reenter_run_scope():
    entry = TextEntry(
        "f", "k", "DOShakePosition: duration can't be 0", status="skipped",
        meta={"role": "display", "disposition": "structural",
              "confidence": "high"})
    assert is_actionable_translation(entry) is False


def _item_count(content: str) -> int:
    """条目数 = 以引号开头的行数（指令/标注行均不以引号开头）。"""
    return sum(1 for line in content.splitlines() if line.startswith('"'))


def _to_model(rows):
    from hanhua.core.models import TextEntry
    return [TextEntry(**r) for r in rows]


def test_batch_translator_all():
    bt = BatchTranslator(FakeClient(mapping={"text1": "文本一"}), batch_size=25, concurrency=2)
    entries = _to_model(_entries())
    stats = bt.run(entries)
    assert stats.total == 60 and stats.done == 60
    assert entries[1].translation == "文本一"
    assert all(e.status == "translated" for e in entries)
    assert stats.requests == 3
    assert stats.input_tokens == 30 and stats.output_tokens == 15


def test_progress_scope_excludes_structural_and_historical_entries():
    rows = [
        {
            "file_id": "code", "key_path": f"skip/{index}",
            "original": f"Method{index}", "status": "skipped",
            "meta": {"role": "structural", "confidence": "low"},
        }
        for index in range(1700)
    ]
    rows.extend(_entries(300))
    rows.append({
        "file_id": "ui", "key_path": "history/settings",
        "original": "Settings", "translation": "设置",
        "status": "translated", "meta": {"role": "display"},
    })
    progress = []

    stats = BatchTranslator(
        FakeClient(), batch_size=300, concurrency=1,
    ).run(_to_model(rows), progress_cb=progress.append)

    assert stats.total == 300
    assert stats.done == 300
    assert stats.failed == 0
    assert progress
    assert all(item.total == 300 for item in progress)
    assert progress[-1].done == 300


@pytest.mark.parametrize("batch_size", [1, 4])
def test_native_scheduler_never_multiplies_outer_and_inner_concurrency(
        batch_size):
    lock = threading.Lock()
    active = 0
    peak = 0

    class NativeClient:
        config = SimpleNamespace(timeout=120.0)

        def translate_text(self, source, _target_lang, _glossary):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.01)
            with lock:
                active -= 1
            return "译文", Usage(1, 1)

    stats = BatchTranslator(
        NativeClient(), batch_size=batch_size, concurrency=3,
    ).run(_to_model(_entries(12)))

    assert stats.done == 12
    assert peak == 3


@pytest.mark.parametrize(("source", "wrong"), [
    ("Settings", "설정"),
    ("ゲーム設定", "ゲーム設定"),
    ("게임 설정", "設定です"),
    ("Settings", "设置 Настройки"),
    ("Settings", "设置 الإعدادات"),
    ("Settings", "设置 설정"),
    ("Settings", "设置 Menu"),
])
def test_chinese_target_retries_wrong_script_output(source, wrong):
    class WrongThenChinese:
        config = SimpleNamespace(timeout=120.0)
        calls = 0

        def translate_text(self, *_args):
            self.calls += 1
            return (wrong if self.calls == 1 else "游戏设置"), Usage(1, 1)

    client = WrongThenChinese()
    entry = _to_model([{
        "file_id": "ui", "key_path": "settings", "original": source,
        "meta": {"role": "ui", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1,
                            lang="en→zh-CN").run([entry])

    assert client.calls == 2
    assert stats.done == 1 and entry.translation == "游戏设置"


@pytest.mark.parametrize(("source", "translation"), [
    (
        "A <#0080ff>simple</color> line of text.",
        "一条<#0080ff>简单的</color>文本行。",
    ),
    (
        "Please set the <b>API Key</b> in the <b>Gemini Dialogue</b> Game Object.",
        "请在<b>Gemini Dialogue</b>游戏对象中设置<b>API Key</b>。",
    ),
    (
        "You have selected link <#ffff00> ID 01",
        "您选择了链接 <#ffff00> ID 01",
    ),
    ("'X' to close", "按 X 键关闭"),
    ("Welcome {playerName}", "欢迎 {playerName}"),
    (
        "<b>WASD</b> - Movement\n<b>LMB</b> - Interact\n<b>RMB</b> - Focus/Zoom",
        "<b>WASD</b> - 移动\n<b>LMB</b> - 交互\n<b>RMB</b> - 聚焦/缩放",
    ),
    (
        "The Thirteenth Floor by Mike Lythgoe",
        "《第十三层》作者：Mike Lythgoe",
    ),
    ("A game by Comp-3 Interactive", "由 Comp-3 Interactive 制作的游戏"),
    ("Thanks to MC Mazzocchi for playtesting one of the first versions.",
     "感谢 MC Mazzocchi 对早期版本进行了测试。"),
    ("Thanks to MrPodunkian and Zizi for peering into the reasons my windows build wasn't working.",
     "感谢 MrPodunkian 和 Zizi，他们帮我弄清了为什么我的窗口构建无法正常运行的原因。"),
    ("<b>NVIDIA</b> graphics", "<b>NVIDIA</b> 显卡"),
    ("<b>STEAM</b> account", "绑定 <b>STEAM</b> 账户"),
    ("NVIDIA graphics", "NVIDIA 显卡"),
    ("STEAM account", "绑定 STEAM 账户"),
    ("SFX volume", "SFX 音量"),
    ("VFX quality", "VFX 质量"),
    # 真实语料：完美翻译保留专名/按键名/品牌，曾被误判 target_script_mismatch
    ("Escape exits the game. P will skip a scene instantly.",
     "Escape会退出游戏。P则会立即跳过当前场景。"),
    ("Thanks to MrPodunkian and Zizi for peering into the reasons "
     "my windows build was not working.",
     "感谢 MrPodunkian 和 Zizi，他们帮我明白了为什么我的 Windows "
     "构建过程无法正常运行的原因。"),
    ("Clips from youtube movies used in creating this game :",
     "用于制作此游戏的 YouTube 视频片段："),
    ("cbs intro", "CBS开场镜头"),
    ("Look Orbit X", "看看 Orbit X"),
    ("3D models used or modified for this game",
     "用于或修改用于此游戏的 3D 模型"),
    ("Sprite资源", "Sprite 资源"),
    ("UI_Title Screen", "UI_Title 屏幕"),
    ("Press Escape to open the menu", "按 Escape 打开菜单"),
])
def test_protected_target_script_spans(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is True
    assert entry.meta["quality_passed"] is True


@pytest.mark.parametrize(("source", "translation"), [
    # 专名/标签回显（字母序列相同 + 无小写/词典词）→ target_script_mismatch 豁免
    ("[ S K I P ]", "[S K I P]"),
    ("AI", "AI"),
    ("AR", "AR"),
    ("3DI70R 2024", "3DI70R 2024"),
    ("TOSS TRASH", "TOSS TRASH"),
])
def test_proper_name_echo_not_target_script_mismatch(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is True
    assert entry.meta["quality_passed"] is True


@pytest.mark.parametrize(("source", "translation"), [
    # 模型正确保留的专名载体不算英文残留（v3 失败样本误伤修复）：
    # 3+ 段路径、域名、@用户名、版本号、@ 显示名
    ("Screenshot saved to User/Blah/Hey/HotelParadiseScreenshot 90909090",
     "截图保存在 User/Blah/Hey/HotelParadiseScreenshot 90909090 目录下。"),
    ("(Only savefiles from 0.4.0beta are compatible)",
     "仅 0.4.0beta 版本的存档文件才兼容。"),
    ("game by fie (@zkfie)", "游戏由 fie (@zkfie) 制作"),
    ("Let us know in the comments on itch.io what you'd like to see",
     "请在 itch.io 的评论区告诉我们，您希望在完整游戏中看到什么内容！"),
    ("3D Models & additional assets from\nUnity Asset Store & OpenGameArt.com",
     "3D模型及来自……的其他资源\nUnity Asset Store & OpenGameArt.com"),
    ("@SoftdevWu", "@SoftdevWu"),
])
def test_safe_keeper_spans_are_not_target_script_mismatch(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is True
    assert entry.meta["quality_passed"] is True


@pytest.mark.parametrize(("source", "translation"), [
    # 日文专名回显（VTuber 频道名，proper_name_echo 也豁免日文脚本）：
    # 字母序列相同 + 无小写词 → 保留原文合理
    ("Korone Ch. 戌神ころね", "Korone Ch. 戌神ころね"),
])
def test_japanese_proper_name_echo_is_allowed(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is True


@pytest.mark.parametrize(("source", "translation"), [
    # 真半翻仍失败：普通小写词保留（非 @/域名/路径/版本号）
    ("Adjust ram pressure", "调整 ram 压力"),
    ("Open the steam valve", "打开 steam 阀门"),
    ("ragdoll count", "ragdoll 计数"),
])
def test_common_word_leftovers_still_target_script_mismatch(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is False


@pytest.mark.parametrize(("source", "translation"), [
    # 破折号后署名位小写名（resonance-of-the-ocean 译者署名 yamur）→ 允许
    ("Turkish Localization - yamur <3", "土耳其语本地化 – yamur <3"),
    # 文件扩展名（spolous 真实样本：SPOLOUS.exe 保留）
    ("「SPOLOUS.exe」をダブルクリックすれば、ゲームがスタートします。",
     "双击“SPOLOUS.exe”即可启动游戏。"),
    # 代码标记（the-supper 真实样本：变量管理器语法 [var:ID]）
    ("Sets the value of both Global and Local Variables, as declared in the "
     "Variables Manager. Integers can be set to absolute, incremented or "
     "assigned a random value. Strings can also be set to the value of a "
     "MenuInput element; Integers, booleans and floats can be set to Mecanim "
     "parameter values. When setting integers and floats, a formula can be "
     "entered, e.g. 2 + 3 * 4. Formulas can contain [var:ID] tags that "
     "represent the value of the variable, where ID is the unique number "
     "assigned to the variable in the Variables Manager.",
     "它用于设置全局变量和局部变量的值，这些变量是在变量管理器中声明的。"
     "整数可以被设置为绝对值、递增值或随机值。字符串也可以被设置为 "
     "MenuInput 元素的值；而整数、布尔值和浮点数则可以被设置为 Mecanim "
     "参数的值。在设置整数和浮点数时，还可以输入公式（例如 2 + 3 * 4），"
     "公式中可以包含 [var:ID] 这样的标记，用来表示变量的值，其中 ID "
     "是变量管理器中为该变量分配的唯一编号"),
])
def test_proper_name_carriers_and_signatures_are_allowed(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is True


@pytest.mark.parametrize(("source", "translation"), [
    # 无破折号的普通小写残留仍失败（签名豁免不适用）
    ("Turkish Localization - yamur <3", "Turkish Localization - yamur <3"),
    ("press any key", "Press any key"),
    # 首行英文词超过 2 个（问候 + 其他）→ 问候豁免不适用，仍失败
    ("press any key", "Hello, press any key 世界"),
])
def test_signature_echo_without_chinese_still_fails(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is False


@pytest.mark.parametrize(("source", "translation"), [
    # 问候行豁免（mimic-search 真实样本）：译文首行保留英文问候，
    # 其余已译为中文 → 本地化惯例，允许
    ("Hello,\n\n\nA few hours ago we received an anonymous phone call "
     "about a missing person.",
     "Hello,\n\n\n几小时前，我们接到了一个关于失踪人员的匿名电话。"),
    # 问候行豁免（soul-delivery 真实样本）：Hello, there. 双词问候
    ("Hello, there\n\nI've been working really hard on this game "
     "for the past 6 months",
     "Hello, there.\n\n在过去的6个月里，我一直在努力完善这款游戏"),
])
def test_greeting_first_line_allowed_when_rest_is_chinese(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is True


@pytest.mark.parametrize(("source", "translation"), [
    # rich-text 包裹的作者名（slendergus 真实样本：<b>lucd</b> 高亮作者名 +
    # lucd#9569 Discord id，credit 行其余已译中文）→ 允许
    ("\n<color=#FFD700><b>lucd</b></color> - Creator \n(lucd#9569)\n\n"
     "<color=#00FFFF>Gardok</color> -\n pages texture and logo\n\n"
     '<color=#FFA500>RudyRudys</color> - \ndoor model\n\n'
     '<color="red">MRBYE</color> - \ngame ',
     "\n<color=#FFD700><b>lucd</b></color> – 创作者\n(lucd#9569)\n\n"
     "<color=#00FFFF>加多克</color> -\n页面纹理和徽标\n\n"
     "<color=#FFA500>RudyRudys</color> -\n门型号\n\n"
     '<color="red">MRBYE</color> -\n游戏'),
])
def test_rich_text_wrapped_proper_name_allowed_when_rest_is_chinese(
        source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is True


@pytest.mark.parametrize(("source", "translation"), [
    # 回显仍判失败：UI 词典词（SFX）或小写词（Hello world）
    ("SFX", "SFX"),
    ("Hello world", "Hello world"),
])
def test_real_echo_still_target_script_mismatch(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is False


@pytest.mark.parametrize(("source", "translation"), [
    ("Ahoy matey", "Hey there!"),
    ("Settings", "设置 Menu"),
    ("Press E to Open", "按 E 键 Open"),
    ("SETTINGS", "设置 SETTINGS"),
    ("WELCOME HOME", "欢迎 WELCOME HOME"),
    ("<b>SETTINGS</b>", "<b>设置 SETTINGS</b>"),
    ("Open the steam valve", "打开 steam 阀门"),
    ("An epic battle", "一场 epic 战斗"),
    ("Adjust ram pressure", "调整 ram 压力"),
    # 按键名豁免不适用：除 Escape 外还有残留词 → 仍判失败
    ("Press Escape to open", "按 Escape 键打开 Open"),
])
def test_protected_target_script_does_not_allow_semantic_english(
        source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported-invalid", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is False
    assert entry.meta["quality_passed"] is False


@pytest.mark.parametrize(("source", "translation"), [
    # TitleCase 专名短语中的 UI 词典词（baldis 真实样本：游戏名
    # 《Baldi's Fun New School Remastered》 的 New 命中 UI 词典）→ 允许
    ("<size=50><color=green><u>WELCOME TO THE GAME CONTROLLER SETUP!"
     "</u></color></size>\n\nThis Setup Will Help You With Getting A Game "
     "Controller Connected Via <color=blue>Bluetooth</color> To Play "
     "Baldi's Fun New School Remastered.",
     "<size=50><color=green><u>欢迎使用游戏控制器设置程序！</u></color></size>"
     "\n\n此设置将帮助您通过 <color=blue>蓝牙</color> 连接游戏控制器，"
     "以便能够玩《Baldi's Fun New School Remastered》这款游戏。"),
])
def test_title_case_ui_word_inside_proper_name_phrase_allowed(
        source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is True


def test_lowercase_article_inside_proper_name_phrase_allowed():
    # eggs-for-bart 真实样本 credit 页（完整 2294 字符原文 + 1558 字符译文）：
    # 'Darth-artisan on the\nUnity Asset Store' 的 the 在语义剥离后的专名
    # 序列中 → 允许。构造最小用例会被 credit 术语剥离干扰，故用完整样本
    sample = json.loads(
        (Path(__file__).parent / "fixtures" / "eggs-for-bart-credit-page.json")
        .read_text(encoding="utf-8"))
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", sample["original"],
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, sample["translation"]) is True


@pytest.mark.parametrize(("source", "translation"), [
    # 小写冠词不夹在 TitleCase 词之间（真实半翻）→ 仍判失败
    ("Press the button to continue", "按下 the button 继续"),
    ("The End is near", "这是 the End 的开始"),
    # 孤立 UI 词典词半翻 → 仍判失败
    ("Save game", "保存 Save 游戏"),
])
def test_isolated_lowercase_word_inside_chinese_still_fails(
        source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is False


@pytest.mark.parametrize(("source", "translation"), [
    # 驼峰技术缩写（VSync）→ 界面标准术语，保留原文合理（vincent 真实样本）
    ("VSync: OFF", "VSync：关闭"),
])
def test_technical_camel_case_term_preserved_allowed(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, translation) is True


@pytest.mark.parametrize("source", [
    # lorem ipsum 占位文本（开发者填充的假拉丁文本）→ 回显是合理行为
    # （zero-deaths 真实样本，'Loem iipsum solar' 是错拼变体）
    "Loem iipsum solar",
    "Loem iipsum solar em demit solo demmy sorenson.",
    "Lorem ipsum dolor sit amet",
])
def test_lorem_ipsum_placeholder_echo_allowed(source):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, source) is True


def test_non_ascii_proper_name_echo_allowed():
    # zero-deaths 真实样本：'Stefánsson' 的 á 会让 _ENGLISH_WORD（ASCII）
    # 拆出 'nsson' 小写碎片 → 旧判定误拦；独立小写词检查应豁免专名回显
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", "Sir Stefán Karl Stefánsson",
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, "Sir Stefán Karl Stefánsson") is True


@pytest.mark.parametrize("source", [
    # 品牌纯串：模型保留原文合理，不应判 target_script_mismatch
    "Playstation",
    "Xbox",
    "NVIDIA",
])
def test_quality_allows_brand_only_source_kept_as_is(source):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, source) is True


def test_chinese_target_does_not_exempt_wrong_script_after_proper_name():
    class MixedProperNameClient:
        config = SimpleNamespace(timeout=120.0)
        calls = 0

        def translate_text(self, *_args):
            self.calls += 1
            return "爱丽丝 설정", Usage(1, 1)

    client = MixedProperNameClient()
    entry = _to_model([{
        "file_id": "dialogue", "key_path": "speaker/name",
        "original": "Alice",
        "meta": {"role": "proper_name", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(
        client, batch_size=1, concurrency=1, lang="en→zh-CN",
    ).run([entry])

    assert client.calls == 1
    assert stats.failed == 1
    assert entry.quality_reasons == ("target_script_mismatch",)


def test_chinese_target_glossary_allowance_uses_source_token_boundaries():
    class WrongThenChinese:
        config = SimpleNamespace(timeout=120.0)
        calls = 0

        def translate_text(self, *_args):
            self.calls += 1
            return ("开始 Menu" if self.calls == 1 else "开始"), Usage(1, 1)

    client = WrongThenChinese()
    entry = _to_model([{
        "file_id": "ui", "key_path": "start", "original": "Start",
        "meta": {"role": "ui", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(
        client, batch_size=1, concurrency=1, lang="en→zh-CN",
        glossary=[("art", "Menu")],
    ).run([entry])

    assert client.calls == 2
    assert stats.done == 1 and entry.translation == "开始"


def test_chinese_target_allows_applied_latin_glossary_target():
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN",
        glossary=[("Moon Key", "MoonKey")],
    )
    entry = TextEntry(
        "ui", "item", "Use the Moon Key",
        meta={"role": "display", "disposition": "translate"},
    )

    assert translator._apply_quality(entry, "使用 MoonKey") is True


def test_chinese_target_accepts_cjk_extension_ideograph():
    class ExtensionIdeographClient:
        config = SimpleNamespace(timeout=120.0)
        calls = 0

        def translate_text(self, *_args):
            self.calls += 1
            return "𠀀", Usage(1, 1)

    client = ExtensionIdeographClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "rare", "original": "Rare",
        "meta": {"role": "ui", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(
        client, batch_size=1, concurrency=1, lang="en→zh-CN",
    ).run([entry])

    assert client.calls == 1
    assert stats.done == 1 and entry.translation == "𠀀"


def test_local_single_item_fallback_accepts_plain_translation():
    class PlainLocalClient:
        accepts_plain_single = True
        config = SimpleNamespace(timeout=120.0)

        def chat(self, _system, _messages):
            return "按 E 键打开", Usage(8, 4)

    entry = _to_model([{
        "file_id": "ui", "key_path": "prompt/open",
        "original": "Press E to open", "meta": {"role": "display"},
    }])[0]

    stats = BatchTranslator(
        PlainLocalClient(), batch_size=1, concurrency=1,
    ).run([entry])

    assert stats.done == 1 and stats.failed == 0
    assert entry.translation == "按 E 键打开"


def test_request_error_keeps_detail_for_diagnosis():
    class RaisingClient:
        def chat(self, _system, _messages):
            raise RuntimeError("HTTP 404: endpoint mismatch")

    entry = _to_model([{
        "file_id": "ui", "key_path": "prompt/open",
        "original": "Press E to open", "meta": {"role": "display"},
    }])[0]

    stats = BatchTranslator(
        RaisingClient(), batch_size=1, concurrency=1,
    ).run([entry])

    assert stats.failed == 1
    assert entry.quality_reasons == ("request_error",)
    assert json.loads(entry.meta["request_error_detail"]) == {
        "type": "RuntimeError", "status": None,
        "message": "HTTP 404: endpoint mismatch",
    }


def test_cancellation_stops_scheduling_pending_batches():
    cancelled = threading.Event()

    class CancellingClient(FakeClient):
        def chat(self, system, messages):
            result = super().chat(system, messages)
            cancelled.set()
            return result

    client = CancellingClient()
    entries = _to_model(_entries(12))
    stats = BatchTranslator(
        client, batch_size=1, concurrency=1,
        cancellation_event=cancelled,
    ).run(entries)

    assert client.calls == 1
    assert stats.done == 0 and stats.failed == 0
    assert all(entry.status == "pending" for entry in entries)


def test_request_error_detail_redacts_credentials_and_bodies():
    secret = "sk-raw-secret"

    class ConfiguredClient(FakeClient):
        config = type("Config", (), {"api_key": secret})()

        def chat(self, _system, _messages):
            raise RuntimeError(
                f"Authorization: Bearer {secret} "
                f"https://user:{secret}@host/path?api_key={secret} "
                f'body={{"token":"{secret}"}}')

    entry = _to_model(_entries(1))[0]
    BatchTranslator(ConfiguredClient(), batch_size=1).run([entry])
    detail = entry.meta["request_error_detail"]
    diagnostic = json.loads(detail)

    assert set(diagnostic) == {"type", "status", "message"}
    assert secret not in detail
    assert "Authorization" not in diagnostic["message"]
    assert "api_key=" not in diagnostic["message"]
    assert "token" not in diagnostic["message"]


def test_native_local_translation_bypasses_json_batch_prompt_for_multiline_text():
    class NativeLocalClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, target_lang, glossary):
            self.calls.append((source, target_lang, tuple(glossary)))
            translations = {
                "Key30\nG - to throw\n": "Key30\nG – 投掷",
                "Operator: Flabby Pizza. Human Resources.\n":
                    "操作员：Flabby Pizza。人力资源部。",
            }
            return translations[source], Usage(20, 8)

        def chat(self, _system, _messages):
            raise AssertionError("native local translation must not use JSON chat")

    client = NativeLocalClient()
    entries = _to_model([
        {"file_id": "level3", "key_path": "prompt/throw",
         "original": "Key30\nG - to throw\n", "meta": {"role": "display"}},
        {"file_id": "level3", "key_path": "dialogue/hr",
         "original": "Operator: Flabby Pizza. Human Resources.\n",
         "meta": {"role": "display"}},
    ])

    stats = BatchTranslator(
        client, batch_size=8, concurrency=1,
        lang="auto→zh-CN", glossary=[
            ("throw", "投掷"), ("Key30", "Key30"),
            ("Flabby Pizza", "Flabby Pizza"),
        ],
    ).run(entries)

    assert stats.done == 2 and stats.failed == 0 and stats.requests == 2
    assert entries[0].translation == "Key30\nG – 投掷\n"
    assert len(client.calls) == 2
    assert all(call[1] == "zh-CN" for call in client.calls)


def test_native_multiline_mismatch_repairs_segments_and_exact_delimiters_once():
    class CollapsingClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, _target_lang, _glossary):
            self.calls.append(source)
            translations = {
                "\r\nSettings\r\n\r\n{0}kg\\n£{1:0.00}\r\n":
                    "设置\r\n{0}千克£{1:0.00}",
                "Settings": "设置",
                "{0}kg": "{0}千克",
                "£{1:0.00}": "£{1:0.00}",
            }
            return translations[source], Usage(5, 2)

    source = "\r\nSettings\r\n\r\n{0}kg\\n£{1:0.00}\r\n"
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/settings",
        "original": source, "meta": {"role": "ui"},
    }])[0]
    client = CollapsingClient()

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0
    assert entry.translation == "\r\n设置\r\n\r\n{0}千克\\n£{1:0.00}\r\n"
    assert client.calls == [source, "Settings", "{0}kg", "£{1:0.00}"]
    assert stats.requests == 4


def test_native_echo_repair_splits_long_paragraph_into_sentences():
    """长单段文本超出 ctx 时模型回显原文（untranslated_text）→ 拆句翻译拼接。

    这是后半段失败的稳定形态：长 prompt + 大输出被 clamp/截断后模型直接
    回显原文。短句回显概率极低，拆句逐段翻译后拼接再校验。
    """
    original = ("A long paragraph about the world that the model will echo "
                "back verbatim. It has many sentences inside it. And the "
                "last sentence ends it here.")
    sentences = {
        "A long paragraph about the world that the model will echo back "
        "verbatim.": "关于世界的长段落。",
        "It has many sentences inside it.": "里面有很多句子。",
        "And the last sentence ends it here.": "最后一句话到此结束。",
    }

    class EchoingParagraphClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, _target_lang, _glossary):
            self.calls.append(source)
            if source == original:
                return original, Usage(10, 2)   # 回显原文 → untranslated_text
            return sentences[source], Usage(3, 2)

    client = EchoingParagraphClient()
    entry = _to_model([{
        "file_id": "text", "key_path": "story/paragraph",
        "original": original, "meta": {"role": "display"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0
    # 句间空白（原文标点后空格）忠实保留
    assert entry.translation == ("关于世界的长段落。 里面有很多句子。 "
                                 "最后一句话到此结束。")
    assert client.calls == [
        original, "A long paragraph about the world that the model will "
                  "echo back verbatim.",
        "It has many sentences inside it.",
        "And the last sentence ends it here.",
    ]


def test_native_multiline_repair_precedes_actionable_ui_retry():
    class CollapsingUiClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, _target_lang, _glossary):
            self.calls.append(source)
            translations = {
                "Settings\nApply": "Settings Apply",
                "Settings": "设置",
                "Apply": "应用",
            }
            return translations[source], Usage(5, 2)

    client = CollapsingUiClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/settings-apply",
        "original": "Settings\nApply",
        "meta": {"role": "ui", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 3
    assert entry.translation == "设置\n应用"
    assert client.calls == ["Settings\nApply", "Settings", "Apply"]


def test_slot_repair_preserves_rich_text_newlines_and_inputs():
    source = "<b>Settings</b>\nPress E to Open {0}"

    class BreakingThenSegmentClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, text, _target_lang, _glossary):
            self.calls.append(text)
            translations = {
                source: "Settings 按 E 打开",
                "Settings": "设置",
                "Press": "按",
                "to Open": "以打开",
            }
            return translations[text], Usage(5, 2)

    client = BreakingThenSegmentClient()
    entry = TextEntry(
        "ui", "menu/slot-repair", source,
        meta={"role": "ui", "disposition": "translate"},
    )

    stats = BatchTranslator(
        client, batch_size=1, concurrency=1, lang="en→zh-CN").run([entry])

    assert stats.done == 1 and stats.failed == 0
    assert entry.translation == "<b>设置</b>\n按 E 以打开 {0}"
    assert entry.meta["quality_passed"] is True
    assert client.calls == [source, "Settings", "Press", "to Open"]


def test_slot_repair_handles_untranslated_semantics_around_input_token():
    source = "Press RMB to attack"

    class PartialThenSegmentClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, text, _target_lang, _glossary):
            self.calls.append(text)
            return {
                source: "按 RMB to attack",
                "Press": "按",
                "to attack": "以攻击",
            }[text], Usage(5, 2)

    client = PartialThenSegmentClient()
    entry = TextEntry(
        "ui", "prompt/attack", source,
        meta={"role": "display", "disposition": "translate"},
    )

    stats = BatchTranslator(
        client, batch_size=1, concurrency=1, lang="en→zh-CN").run([entry])

    assert stats.done == 1 and stats.failed == 0
    assert entry.translation == "按 RMB 以攻击"
    assert client.calls == [source, "Press", "to attack"]


def test_chat_slot_repair_preserves_rich_text_newlines_and_inputs():
    source = "<b>Settings</b>\nPress E to Open {0}"

    class BreakingThenSegmentChatClient:
        def __init__(self):
            self.calls = 0

        def chat(self, _system, _messages):
            translations = ["Settings 按 E 打开", "设置", "按", "以打开"]
            translation = translations[self.calls]
            self.calls += 1
            return json.dumps([{
                "id": "menu/chat-slot-repair@ui",
                "translation": translation,
            }], ensure_ascii=False), Usage(5, 2)

    client = BreakingThenSegmentChatClient()
    entry = TextEntry(
        "ui", "menu/chat-slot-repair", source,
        meta={"role": "ui", "disposition": "translate"},
    )

    stats = BatchTranslator(
        client, batch_size=1, concurrency=1, lang="en→zh-CN").run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 4
    assert entry.translation == "<b>设置</b>\n按 E 以打开 {0}"
    assert entry.meta["quality_passed"] is True
    assert client.calls == 4


@pytest.mark.parametrize("delimiter", ["\n", "\r\n", r"\n"])
def test_native_multiline_repair_restores_empty_segment_topology(delimiter):
    class MovingBlankLineClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self, source):
            self.source = source
            self.calls = []

        def translate_text(self, source, _target_lang, _glossary):
            self.calls.append(source)
            if source == self.source:
                return delimiter.join(("甲", "乙", "", "丙")), Usage(5, 2)
            return {"A": "甲", "B": "乙", "C": "丙"}[source], Usage(5, 2)

    source = delimiter.join(("A", "", "B", "C"))
    client = MovingBlankLineClient(source)
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/topology",
        "original": source, "meta": {"role": "ui"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 4
    assert entry.translation == delimiter.join(("甲", "", "乙", "丙"))
    assert client.calls == [source, "A", "B", "C"]


def test_native_multiline_repair_fails_when_a_meaningful_segment_stays_empty():
    class DroppingClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, _target_lang, _glossary):
            self.calls.append(source)
            translations = {
                "First\nSecond\nThird": "第一\n\n第三",
                "First": "第一",
                "Second": "",
            }
            return translations[source], Usage(5, 2)

    entry = _to_model([{
        "file_id": "dialogue", "key_path": "line/three",
        "original": "First\nSecond\nThird", "meta": {"role": "display"},
    }])[0]
    client = DroppingClient()

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 0 and stats.failed == 1
    assert entry.quality_reasons == ("line_content_mismatch",)
    assert client.calls == ["First\nSecond\nThird", "First", "Second"]
    assert stats.requests == 3


def test_native_actionable_ui_uses_builtin_references_and_retries_only_once():
    class EchoThenTranslateClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, target_lang, glossary):
            self.calls.append((source, target_lang, tuple(glossary)))
            result = "SFX" if len(self.calls) == 1 else "音效"
            return result, Usage(5, 2)

    client = EchoThenTranslateClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/sfx", "original": "SFX",
        "meta": {"role": "ui", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 2
    assert entry.translation == "音效"
    assert len(client.calls) == 2
    expected = {
        ("Settings", "设置"), ("Quit", "退出"),
        ("Resolution", "分辨率"), ("SFX", "音效"),
        ("Volume", "音量"), ("Resume", "继续"),
    }
    assert expected <= set(client.calls[0][2])
    assert client.calls[0][2] == client.calls[1][2]


def test_native_actionable_retry_on_input_token_loss():
    # deadbeat 真实样本：'tab : config' 按键被模型翻译成 '标签：配置'（丢按键）
    # → input_token_mismatch 触发 protected repair（剥离按键段 → 单独翻译
    #   ': config' → 回填按键前缀）；第二次保留按键 → 成功
    class TabThenFixClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, target_lang, glossary):
            self.calls.append((source, target_lang, tuple(glossary)))
            return ("标签：配置" if len(self.calls) == 1 else "Tab 键：配置",
                    Usage(5, 2))

    client = TabThenFixClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/config", "original": "tab : config",
        "meta": {"role": "ui", "disposition": "translate",
                 "reason": "interaction_prompt"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 2
    # 按键 tab 从原文剥离后回填（原文按键前缀 + 译文）；模型第二次补全按键
    assert entry.translation == "tab Tab 键：配置"
    assert [call[0] for call in client.calls] == ["tab : config", ": config"]


def test_protected_repair_backfills_key_when_stripped_segment_echoes():
    # deadbeat 真实失败：剥离段 ': config' 模型回显 'config'（无中文）→
    # protected repair 的剥离段翻译失败 → 降级：整段译文 '标签：配置' 语义
    # 已正确，只缺按键段 → 回填缺失的 protected 段 'tab' → 'tab 标签：配置'
    class EchoStrippedClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, target_lang, glossary):
            self.calls.append(source)
            if source == "tab : config":
                return "标签：配置", Usage(5, 2)
            return "config", Usage(2, 1)  # 剥离段回显，无中文

    client = EchoStrippedClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/config", "original": "tab : config",
        "meta": {"role": "ui", "disposition": "translate",
                 "reason": "interaction_prompt"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 2
    # 剥离段没翻出来 → 按键回填到整段译文前（不回填已含按键的译文）
    assert entry.translation == "tab 标签：配置"
    assert client.calls == ["tab : config", ": config"]


def test_protected_repair_backfill_skips_when_key_already_in_whole():
    # 整段译文已含按键翻译（'回车：配置'）→ 回填 'Enter' 会重复 → 跳过，
    # 剥离段本身翻译成功（'配置' 有中文）→ 直接用剥离段重建
    class StripOkClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, target_lang, glossary):
            self.calls.append(source)
            if source == "enter : config":
                return "回车：配置", Usage(5, 2)
            return "配置", Usage(2, 1)

    client = StripOkClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/config", "original": "enter : config",
        "meta": {"role": "ui", "disposition": "translate",
                 "reason": "interaction_prompt"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 2
    assert entry.translation == "enter 配置"
    assert client.calls == ["enter : config", ": config"]


def test_input_token_mismatch_is_actionable_ui_retry():
    # input_token_mismatch（按键丢失）加入可重试：protected repair 失败后
    # 仍有第二次完整原文重试机会
    entry = TextEntry(
        "ui", "reported", "tab : config",
        meta={"role": "ui", "disposition": "translate"},
    )
    entry.quality_reasons = ("input_token_mismatch",)

    assert BatchTranslator._is_actionable_ui_retry(entry) is True


def test_native_actionable_retry_stops_after_first_response_cancels():
    cancelled = threading.Event()

    class CancellingEchoClient:
        config = SimpleNamespace(timeout=120.0)
        calls = 0

        def translate_text(self, source, _target_lang, _glossary):
            self.calls += 1
            cancelled.set()
            return source, Usage(1, 1)

    client = CancellingEchoClient()
    entry = _to_model([{"file_id": "ui", "key_path": "menu/sfx",
                        "original": "SFX", "meta": {"role": "ui"}}])[0]
    stats = BatchTranslator(
        client, batch_size=1, concurrency=1,
        cancellation_event=cancelled,
    ).run([entry])

    assert client.calls == 1
    assert stats.done == stats.failed == 0
    assert entry.status == "pending" and entry.translation == ""


def test_native_actionable_retry_response_cancel_does_not_mutate_entry():
    cancelled = threading.Event()

    class RetryCancellingClient:
        config = SimpleNamespace(timeout=120.0)
        calls = 0

        def translate_text(self, source, _target_lang, _glossary):
            self.calls += 1
            if self.calls == 2:
                cancelled.set()
                return "设置", Usage(1, 1)
            return source, Usage(1, 1)

    client = RetryCancellingClient()
    entry = _to_model([{"file_id": "ui", "key_path": "menu/settings",
                        "original": "Settings", "meta": {"role": "ui"}}])[0]
    stats = BatchTranslator(client, batch_size=1, concurrency=1,
                            cancellation_event=cancelled).run([entry])

    assert client.calls == 2
    assert stats.done == stats.failed == 0
    assert entry.status == "pending" and entry.translation == ""
    assert "quality_passed" not in entry.meta
    assert "quality_reasons" not in entry.meta


def test_chat_batch_and_single_fallback_include_builtin_ui_references():
    class EchoThenTranslateChatClient:
        def __init__(self):
            self.prompts = []

        def chat(self, _system, messages):
            self.prompts.append(messages[0]["content"])
            translation = "SFX" if len(self.prompts) == 1 else "音效"
            return json.dumps([{
                "id": "menu/sfx@ui", "translation": translation,
            }], ensure_ascii=False), Usage(5, 2)

    client = EchoThenTranslateChatClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/sfx", "original": "SFX",
        "meta": {"role": "ui", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 2
    assert entry.translation == "音效" and len(client.prompts) == 2
    for prompt in client.prompts:
        assert "Reference the following translations:" in prompt
        for source, target in (
                ("Settings", "设置"), ("Quit", "退出"),
                ("Resolution", "分辨率"), ("SFX", "音效"),
                ("Volume", "音量"), ("Resume", "继续")):
            assert f"{source} translates to {target}" in prompt


def test_chat_multiline_mismatch_repairs_segments_without_whole_retry():
    class CollapsingChatClient:
        def __init__(self):
            self.prompts = []

        def chat(self, _system, messages):
            prompt = messages[0]["content"]
            self.prompts.append(prompt)
            translations = ["Settings Apply", "设置", "应用"]
            return json.dumps([{
                "id": "menu/settings-apply@ui",
                "translation": translations[len(self.prompts) - 1],
            }], ensure_ascii=False), Usage(5, 2)

    client = CollapsingChatClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/settings-apply",
        "original": "Settings\nApply",
        "meta": {"role": "ui", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 3
    assert entry.translation == "设置\n应用"
    assert len(client.prompts) == 3
    assert client.prompts[0].endswith(
        '"menu/settings-apply@ui": Settings\nApply')
    assert client.prompts[1].endswith(
        '"menu/settings-apply@ui": Settings')
    assert client.prompts[2].endswith(
        '"menu/settings-apply@ui": Apply')
    assert all("Reference the following translations:" in prompt
               for prompt in client.prompts)


def test_native_multiline_cancel_between_segments_stops_provider_calls():
    cancelled = threading.Event()

    class CancellingSegmentClient:
        config = SimpleNamespace(timeout=120.0)
        calls = []

        def translate_text(self, source, _target_lang, _glossary):
            self.calls.append(source)
            if len(self.calls) == 2:
                cancelled.set()
            return ({"One\nTwo": "One Two", "One": "一"}.get(source, "二"),
                    Usage(1, 1))

    client = CancellingSegmentClient()
    entry = _to_model([{"file_id": "ui", "key_path": "menu/two",
                        "original": "One\nTwo", "meta": {"role": "ui"}}])[0]
    stats = BatchTranslator(client, batch_size=1, concurrency=1,
                            cancellation_event=cancelled).run([entry])

    assert client.calls == ["One\nTwo", "One"]
    assert stats.done == stats.failed == 0 and entry.status == "pending"


def test_chat_multiline_cancel_between_segments_stops_provider_calls():
    cancelled = threading.Event()

    class CancellingSegmentChatClient:
        calls = 0

        def chat(self, _system, _messages):
            self.calls += 1
            if self.calls == 2:
                cancelled.set()
            translation = ["One Two", "一"][self.calls - 1]
            return json.dumps([{"id": "menu/two@ui",
                                "translation": translation}]), Usage(1, 1)

    client = CancellingSegmentChatClient()
    entry = _to_model([{"file_id": "ui", "key_path": "menu/two",
                        "original": "One\nTwo", "meta": {"role": "ui"}}])[0]
    stats = BatchTranslator(client, batch_size=1, concurrency=1,
                            cancellation_event=cancelled).run([entry])

    assert client.calls == 2
    assert stats.done == stats.failed == 0 and entry.status == "pending"


def test_chat_multiline_repair_fails_when_a_segment_stays_empty():
    class DroppingChatClient:
        def __init__(self):
            self.calls = 0

        def chat(self, _system, _messages):
            translations = ["设置应用", "设置", ""]
            translation = translations[self.calls]
            self.calls += 1
            return json.dumps([{
                "id": "menu/settings-apply@ui",
                "translation": translation,
            }], ensure_ascii=False), Usage(5, 2)

    client = DroppingChatClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/settings-apply",
        "original": "Settings\nApply",
        "meta": {"role": "ui", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 0 and stats.failed == 1 and stats.requests == 3
    assert entry.quality_reasons == ("line_content_mismatch",)
    assert client.calls == 3


def test_chat_multiline_proper_name_preserve_is_not_requested():
    class ProperNameChatClient:
        def __init__(self):
            self.calls = 0

        def chat(self, _system, _messages):
            self.calls += 1
            return json.dumps([{
                "id": "speaker/name@dialogue",
                "translation": "Flabby Pizza",
            }]), Usage(5, 2)

    client = ProperNameChatClient()
    entry = _to_model([{
        "file_id": "dialogue", "key_path": "speaker/name",
        "original": "Flabby\nPizza",
        "meta": {"role": "proper_name", "disposition": "preserve"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.total == 0 and stats.done == 0 and stats.failed == 0
    assert stats.requests == 0 and client.calls == 0
    assert entry.status == "pending" and entry.quality_reasons == ()


def test_native_actionable_ui_retry_is_not_limited_to_builtin_terms():
    class EchoThenTranslateClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = 0

        def translate_text(self, _source, _target_lang, _glossary):
            self.calls += 1
            result = "Apply Changes" if self.calls == 1 else "应用更改"
            return result, Usage(5, 2)

    client = EchoThenTranslateClient()
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/apply",
        "original": "Apply Changes",
        "meta": {"role": "ui", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.requests == 2
    assert entry.translation == "应用更改" and client.calls == 2


def test_native_proper_name_preserve_is_not_requested():
    class ProperNameClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = 0

        def translate_text(self, _source, _target_lang, _glossary):
            self.calls += 1
            return "Flabby Pizza", Usage(5, 2)

    client = ProperNameClient()
    entry = _to_model([{
        "file_id": "dialogue", "key_path": "speaker/name",
        "original": "Flabby Pizza",
        "meta": {"role": "proper_name", "disposition": "preserve"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.total == 0 and stats.done == 0 and stats.failed == 0
    assert entry.status == "pending" and entry.quality_reasons == ()
    assert client.calls == 0 and stats.requests == 0


@pytest.mark.parametrize(("role", "disposition"), [
    ("proper_name", ""),
    ("ui", "preserve"),
    ("ui", "structural"),
    ("ui", "code"),
    ("ui", "key"),
])
def test_native_multiline_nontranslate_disposition_is_not_requested(
        role, disposition):
    class PreserveNativeClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = []

        def translate_text(self, source, _target_lang, _glossary):
            self.calls.append(source)
            return "Flabby Pizza", Usage(5, 2)

    client = PreserveNativeClient()
    entry = _to_model([{
        "file_id": "dialogue", "key_path": "speaker/name",
        "original": "Flabby\nPizza",
        "meta": {"role": role, "disposition": disposition},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.total == 0 and stats.done == 0 and stats.failed == 0
    assert stats.requests == 0 and client.calls == []
    assert entry.status == "pending" and entry.quality_reasons == ()


def test_chat_proper_name_preserve_is_not_requested():
    class ProperNameChatClient:
        def __init__(self):
            self.calls = 0

        def chat(self, _system, _messages):
            self.calls += 1
            return json.dumps([{
                "id": "speaker/name@dialogue",
                "translation": "Flabby Pizza",
            }]), Usage(5, 2)

    client = ProperNameChatClient()
    entry = _to_model([{
        "file_id": "dialogue", "key_path": "speaker/name",
        "original": "Flabby Pizza",
        "meta": {"role": "proper_name", "disposition": "preserve"},
    }])[0]

    stats = BatchTranslator(client, batch_size=1, concurrency=1).run([entry])

    assert stats.total == 0 and stats.done == 0 and stats.failed == 0
    assert entry.status == "pending" and entry.quality_reasons == ()
    assert client.calls == 0 and stats.requests == 0


def test_duplicate_source_and_role_share_one_native_translation_request():
    class VaryingNativeClient:
        config = SimpleNamespace(timeout=120.0)

        def __init__(self):
            self.calls = 0

        def translate_text(self, _source, _target_lang, _glossary):
            self.calls += 1
            translation = "打开门" if self.calls == 1 else "开启门"
            return translation, Usage(10, 4)

    client = VaryingNativeClient()
    entries = _to_model([
        {"file_id": "level1", "key_path": "door/1",
         "original": "Open Door", "meta": {"role": "display"}},
        {"file_id": "level2", "key_path": "door/2",
         "original": "Open Door", "meta": {"role": "display"}},
    ])

    stats = BatchTranslator(
        client, batch_size=8, concurrency=1, lang="auto→zh-CN",
    ).run(entries)

    assert client.calls == 1
    assert stats.requests == 1
    assert stats.done == 2 and stats.failed == 0
    assert [entry.translation for entry in entries] == ["打开门", "打开门"]


def test_local_single_item_fallback_extracts_translation_from_echoed_prompt():
    class EchoingLocalClient:
        accepts_plain_single = True
        config = SimpleNamespace(timeout=120.0)

        def chat(self, _system, _messages):
            return (
                "[来源文件] ui\n"
                "[定位键] prompt/open\n"
                "[文本角色] display\n"
                "[输入按键] 译文必须原样保留：E\n"
                '"prompt/open@ui": 按 E 键打开',
                Usage(8, 4),
            )

    entry = _to_model([{
        "file_id": "ui", "key_path": "prompt/open",
        "original": "Press E to open", "meta": {"role": "display"},
    }])[0]

    stats = BatchTranslator(
        EchoingLocalClient(), batch_size=1, concurrency=1,
    ).run([entry])

    assert stats.done == 1 and stats.failed == 0
    assert entry.translation == "按 E 键打开"


def test_local_single_item_ignores_example_json_in_full_prompt_echo():
    class FullPromptEchoClient:
        accepts_plain_single = True
        config = SimpleNamespace(timeout=120.0)

        def chat(self, _system, messages):
            content = messages[0]["content"].replace(
                '"prompt/open@ui": Press E to open',
                '"prompt/open@ui": 按 E 键打开',
            )
            return content, Usage(8, 4)

    entry = _to_model([{
        "file_id": "ui", "key_path": "prompt/open",
        "original": "Press E to open", "meta": {"role": "display"},
    }])[0]

    stats = BatchTranslator(
        FullPromptEchoClient(), batch_size=1, concurrency=1,
    ).run([entry])

    assert stats.done == 1 and stats.failed == 0
    assert entry.translation == "按 E 键打开"


def test_placeholder_mismatch_marks_failed_when_slot_repair_is_invalid():
    class BadClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def chat(self, system, messages):
            translation = "没有占位符" if self.calls == 0 else ""
            self.calls += 1
            return json.dumps([{
                "id": "k0@f", "translation": translation,
            }], ensure_ascii=False), Usage(1, 1)

    bt = BatchTranslator(BadClient(), batch_size=25, concurrency=1)
    entries = _to_model([{"file_id": "f", "key_path": "k0", "original": "Take {item} now"}])
    stats = bt.run(entries)
    assert entries[0].status == "failed"
    assert stats.failed == 1


@pytest.mark.parametrize("invalid_translation", [None, 123, {"text": "打开"}])
def test_model_response_rejects_non_string_translation(invalid_translation):
    class InvalidSchemaClient(FakeClient):
        def chat(self, system, messages):
            return json.dumps([{
                "id": "k0@f", "translation": invalid_translation,
            }], ensure_ascii=False), Usage(1, 1)

    entry = _to_model([{
        "file_id": "f", "key_path": "k0", "original": "Open Door",
    }])[0]

    stats = BatchTranslator(InvalidSchemaClient(), batch_size=1).run([entry])

    assert stats.failed == 1 and entry.status == "failed"
    assert entry.quality_reasons == ("invalid_response",)


def test_model_translation_must_follow_glossary_and_persist_quality_metadata():
    store = ProjectStore(Path(tempfile.mkdtemp()) / "glossary-quality.db")
    store.init_schema()
    store.upsert_entries([{
        "file_id": "dialogue", "key_path": "line/1",
        "original": "Use the Moon Key", "status": "pending",
        "meta": {"role": "dialogue"},
    }])
    entry = _to_model([{
        "file_id": "dialogue", "key_path": "line/1",
        "original": "Use the Moon Key", "meta": {"role": "dialogue"},
    }])[0]
    client = FakeClient({"Use the Moon Key": "使用月之钥匙"})

    stats = BatchTranslator(
        client, memory=store, glossary=[("Moon Key", "月光钥匙")],
        batch_size=1, concurrency=1,
    ).run([entry])

    assert stats.failed == 1 and entry.status == "failed"
    assert entry.quality_reasons == ("glossary_mismatch",)
    row_meta = json.loads(store.get_entries()[0]["meta"])
    assert row_meta["quality_passed"] is False
    assert row_meta["quality_reasons"] == ["glossary_mismatch"]


def test_quality_normalized_translation_is_used_for_database_and_memory():
    store = ProjectStore(Path(tempfile.mkdtemp()) / "normalized.db")
    store.init_schema()
    row = {"file_id": "ui", "key_path": "menu/open", "original": "Open Door"}
    store.upsert_entries([row])
    entry = _to_model([row])[0]

    BatchTranslator(
        FakeClient({"Open Door": "  打开门  "}), memory=store,
        model="m", lang="en→zh-CN", batch_size=1, concurrency=1,
    ).run([entry])

    assert entry.translation == "打开门"
    assert store.get_entries()[0]["translation"] == "打开门"
    assert store.get_memory_hits(["Open Door"], "m", "en→zh-CN") == {
        "Open Door": "打开门",
    }


def test_memory_hit_skips_api():
    store = ProjectStore(Path(tempfile.mkdtemp()) / "m.db")
    store.init_schema()
    store.add_memory("text5", "已有缓存", "m", "en→zh-CN")
    fc = FakeClient()
    bt = BatchTranslator(fc, batch_size=25, concurrency=1, memory=store,
                         model="m", lang="en→zh-CN")
    entries = _to_model(_entries())
    stats = bt.run(entries)
    assert stats.from_memory == 1
    assert entries[5].translation == "已有缓存"


def test_bad_memory_is_evicted_and_falls_back_to_model_in_same_run():
    store = ProjectStore(Path(tempfile.mkdtemp()) / "quality-memory.db")
    store.init_schema()
    store.upsert_entries([{
        "file_id": "ui", "key_path": "menu/open", "original": "Open Door",
        "status": "pending", "meta": {"role": "ui", "max_chars": 12},
    }])
    store.add_memory("Open Door", "Open Door", "m", "en→zh-CN")
    entry = _to_model([{
        "file_id": "ui", "key_path": "menu/open", "original": "Open Door",
        "meta": {"role": "ui", "max_chars": 12},
    }])[0]

    client = FakeClient({"Open Door": "打开门"})
    stats = BatchTranslator(
        client, memory=store, model="m", lang="en→zh-CN",
    ).run([entry])

    assert stats.done == 1 and stats.failed == 0 and stats.from_memory == 0
    assert client.calls == 1
    assert entry.status == "translated" and entry.translation == "打开门"
    assert entry.quality_reasons == ()
    row = store.get_entries()[0]
    persisted_meta = json.loads(row["meta"])
    assert persisted_meta["quality_passed"] is True
    assert store.get_memory_hits(["Open Door"], "m", "en→zh-CN") == {
        "Open Door": "打开门",
    }


def test_locked_entries_skipped():
    bt = BatchTranslator(FakeClient(), batch_size=25, concurrency=1)
    rows = _entries(3)
    rows[1]["locked"] = True
    entries = _to_model(rows)
    stats = bt.run(entries)
    assert entries[1].status == "pending" and entries[1].translation == ""
    assert stats.done == 2


def test_automatic_translation_only_requests_display_text_with_sufficient_confidence():
    client = FakeClient()
    entries = _to_model([
        {"file_id": "f", "key_path": "code", "original": "PlayerController",
         "meta": {"role": "structural", "confidence": "high"},
         "confidence": "high"},
        {"file_id": "f", "key_path": "raw", "original": "Maybe visible",
         "meta": {"role": "display", "confidence": "low"},
         "confidence": "low"},
        {"file_id": "f", "key_path": "ui", "original": "Open Door",
         "meta": {"role": "display", "confidence": "high"},
         "confidence": "high"},
    ])

    stats = BatchTranslator(client, batch_size=10).run(entries)

    assert stats.done == 1 and client.calls == 1
    assert entries[0].status == "pending" and entries[0].translation == ""
    assert entries[1].status == "pending" and entries[1].translation == ""
    assert entries[2].status == "translated"


def test_request_exception_persists_stable_failure_reason():
    class ExplodingClient(FakeClient):
        def chat(self, system, messages):
            raise RuntimeError("provider unavailable")

    store = ProjectStore(Path(tempfile.mkdtemp()) / "request-error.db")
    store.init_schema()
    row = {"file_id": "f", "key_path": "k0", "original": "Open Door"}
    store.upsert_entries([row])
    entry = _to_model([row])[0]

    stats = BatchTranslator(
        ExplodingClient(), memory=store, batch_size=1, concurrency=1,
    ).run([entry])

    assert stats.failed == 1 and entry.status == "failed"
    assert entry.quality_reasons == ("request_error",)
    persisted = json.loads(store.get_entries()[0]["meta"])
    assert persisted["quality_passed"] is False
    assert persisted["quality_reasons"] == ["request_error"]


class BrokenJsonClient(FakeClient):
    """批量请求返回非法 JSON（模拟译文含未转义引号），单条请求返回合法 JSON。"""

    def chat(self, system, messages):
        self.calls += 1
        content = messages[0]["content"]
        if _item_count(content) > 1:
            return '不是JSON [{"id": "x', Usage(10, 5)
        return '[{"id": "k0@f", "translation": "单条翻译成功"}]', Usage(10, 5)


def test_batch_json_failure_falls_back_to_single():
    """整批 JSON 解析失败 → 逐条降级重试必须成功。"""
    bt = BatchTranslator(BrokenJsonClient(), batch_size=25, concurrency=1)
    entries = _to_model([{"file_id": "f", "key_path": "k0", "original": "text0"}])
    stats = bt.run(entries)
    assert stats.done == 1 and stats.failed == 0
    assert entries[0].translation == "单条翻译成功"


class HalfBadClient(FakeClient):
    """批内一条翻译为空（模拟缺条），单条请求成功。"""

    def chat(self, system, messages):
        self.calls += 1
        content = messages[0]["content"]
        if _item_count(content) > 1:
            return '[{"id": "k0@f", "translation": "第一条"}]', Usage(10, 5)
        if "k0@f" in content:
            return '[{"id": "k0@f", "translation": "补译第一条"}]', Usage(10, 5)
        return '[{"id": "k1@f", "translation": "补译第二条"}]', Usage(10, 5)


def test_batch_partial_failure_retries_failed_only():
    bt = BatchTranslator(HalfBadClient(), batch_size=25, concurrency=1)
    entries = _to_model(_entries(2))
    stats = bt.run(entries)
    assert stats.done == 2 and stats.failed == 0
    assert entries[0].translation == "第一条" or entries[0].translation == "补译第一条"


def test_same_source_and_role_share_one_consistent_translation():
    class DriftClient(FakeClient):
        def chat(self, system, messages):
            content = messages[0]["content"]
            out = []
            if "a@f" in content:
                out.append({"id": "a@f", "translation": "打开"})
            if "b@f" in content:
                out.append({"id": "b@f", "translation": "开启"})
            return json.dumps(out, ensure_ascii=False), Usage(1, 1)

    entries = _to_model([
        {"file_id": "f", "key_path": "a", "original": "Open",
         "meta": {"role": "ui"}},
        {"file_id": "f", "key_path": "b", "original": "Open",
         "meta": {"role": "ui"}},
    ])

    stats = BatchTranslator(DriftClient(), batch_size=2, concurrency=1).run(entries)

    assert stats.done == 2 and stats.failed == 0 and stats.requests == 1
    assert entries[0].status == entries[1].status == "translated"
    assert entries[0].translation == entries[1].translation == "打开"


def test_single_object_json_extract():
    from hanhua.core.translator import extract_json_array
    assert extract_json_array('{"id": "e1", "translation": "你好"}') == \
        [{"id": "e1", "translation": "你好"}]


def test_fallback_line_parse():
    from hanhua.core.translator import extract_json_array_fallback
    out = extract_json_array_fallback(
        '{"id": "e1", "translation": "你好"} {"id": "e2", "translation": "再见"}')
    assert out == [{"id": "e1", "translation": "你好"}, {"id": "e2", "translation": "再见"}]


def test_p0_quality_saves_raw_model_output_evidence():
    """P0-3：质量门保存模型原始输出证据（raw_output），
    归一化后与 raw 相同时不重复存 normalized_output。"""
    entry = _to_model([{
        "file_id": "f", "key_path": "k0", "original": "Open Door",
        "meta": {"role": "display", "disposition": "translate"},
    }])[0]

    BatchTranslator(
        FakeClient({"Open Door": "打开门"}), batch_size=1, concurrency=1,
        lang="en→zh-CN",
    ).run([entry])

    assert entry.status == "translated"
    assert entry.meta["raw_output"] == "打开门"
    assert "normalized_output" not in entry.meta


def test_p0_quality_saves_both_raw_and_normalized_when_healed():
    """P0-3：自愈改变了输出（占位符被补全）→ raw 与 normalized 都留存。"""
    class HealingClient(FakeClient):
        def chat(self, system, messages):
            return json.dumps([{
                "id": "k0@f", "translation": "拿着物品",
            }], ensure_ascii=False), Usage(1, 1)

    entry = _to_model([{
        "file_id": "f", "key_path": "k0", "original": "Take {item} now",
        "meta": {"role": "display", "disposition": "translate"},
    }])[0]

    BatchTranslator(
        HealingClient(), batch_size=1, concurrency=1, lang="en→zh-CN",
    ).run([entry])

    assert entry.status == "translated"
    assert entry.meta["raw_output"] == "拿着物品"
    assert "{item}" in entry.translation
    assert entry.meta["normalized_output"] == entry.translation


def test_p0_invalid_response_keeps_raw_content_evidence():
    """P0-3：JSON 解析失败时模型原始输出作为证据留存（审校可复盘）。"""
    class GarbageClient(FakeClient):
        def chat(self, system, messages):
            return "不是JSON的模型响应", Usage(1, 1)

    entry = _to_model([{
        "file_id": "f", "key_path": "k0", "original": "Open Door",
        "meta": {"role": "display", "disposition": "translate"},
    }])[0]

    BatchTranslator(
        GarbageClient(), batch_size=1, concurrency=1,
    ).run([entry])

    assert entry.status == "failed"
    assert entry.quality_reasons == ("invalid_response",)
    assert entry.meta["raw_output"] == "不是JSON的模型响应"


def test_p0_rejected_translation_keeps_raw_evidence():
    """P0-3：质量门拒绝（untranslated_text）后 raw 证据仍在 meta。"""
    class EchoClient(FakeClient):
        def chat(self, system, messages):
            return json.dumps([{
                "id": "k0@f", "translation": "Open Door",
            }], ensure_ascii=False), Usage(1, 1)

    entry = _to_model([{
        "file_id": "f", "key_path": "k0", "original": "Open Door",
        "meta": {"role": "display", "disposition": "translate"},
    }])[0]

    BatchTranslator(
        EchoClient(), batch_size=1, concurrency=1, lang="en→zh-CN",
    ).run([entry])

    assert entry.status == "failed"
    assert "untranslated_text" in entry.quality_reasons
    assert entry.meta["raw_output"] == "Open Door"


def test_batch_prompt_receives_hit_glossary_terms_e2e():
    """P1：术语按条目命中注入——只有本条原文命中的术语进入 prompt。"""
    seen = {}

    class SpyClient(FakeClient):
        def chat(self, system, messages):
            seen["user"] = messages[0]["content"]
            return json.dumps([{
                "id": "dialogue/line/1@f", "translation": "使用月光钥匙",
            }], ensure_ascii=False), Usage(1, 1)

    entry = _to_model([{
        "file_id": "f", "key_path": "dialogue/line/1",
        "original": "Use the Moon Key", "meta": {"role": "display"},
    }])[0]

    BatchTranslator(
        SpyClient(), glossary=[("Moon Key", "月光钥匙"), ("Sword", "长剑")],
        batch_size=1, concurrency=1, lang="en→zh-CN",
    ).run([entry])

    assert "[术语命中] 本条原文包含以下术语" in seen["user"]
    assert "Moon Key → 月光钥匙" in seen["user"]
    assert "Sword" not in seen["user"]


def test_stats_reports_elapsed_and_rate():
    """P3：run 统计耗时与吞吐（条/分）。"""
    entry = _to_model([{
        "file_id": "f", "key_path": "k0", "original": "Open Door",
        "meta": {"role": "display", "disposition": "translate"},
    }])[0]

    stats = BatchTranslator(
        FakeClient({"Open Door": "打开门"}), batch_size=1, concurrency=1,
        lang="en→zh-CN",
    ).run([entry])

    assert stats.done == 1
    assert stats.elapsed > 0
    assert stats.rate_per_minute > 0
    assert stats.rate_per_minute == 60.0 / stats.elapsed


def test_stats_rate_zero_without_elapsed():
    from hanhua.core.models import TranslateStats
    assert TranslateStats(done=5, elapsed=0.0).rate_per_minute == 0.0
    assert TranslateStats(done=0, elapsed=1.0).rate_per_minute == 0.0
