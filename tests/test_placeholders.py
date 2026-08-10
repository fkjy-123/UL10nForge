import pytest

from hanhua.core.placeholders import (extract_placeholders,
                                      is_credit_like,
                                      is_hard_structural,
                                      self_heal_format_tags,
                                      validate_translation, should_skip)


def test_extract_brace():
    assert extract_placeholders("欢迎 {name}！还剩 {0} 秒") == ["{name}", "{0}"]


def test_extract_dotnet_format_brace_placeholder():
    assert extract_placeholders(r"{0}kg\n£{1:0.00}") == [
        "{0}", r"\n", "{1:0.00}",
    ]


def test_extract_percent_and_tags():
    assert extract_placeholders("HP %d%% <b>恢复</b> [b]") == ["%d", "%%", "<b>", "</b>", "[b]"]


def test_validate_preserves_placeholder_multiplicity():
    ok, missing, extra = validate_translation("Lv.{0} -> {0}", "等级{0}")
    assert not ok and missing == ["{0}"] and not extra


def test_extract_and_validate_preserve_cross_type_order():
    assert extract_placeholders("HP %s / {0} <b>text</b>") == [
        "%s", "{0}", "<b>", "</b>",
    ]
    ok, missing, extra = validate_translation(
        "HP %s / {0}", "生命 {0} / %s")
    assert not ok and not missing and not extra


def test_validate_missing():
    ok, missing, extra = validate_translation("Take {item} now", "拿起物品")
    assert not ok and missing == ["{item}"]


def test_validate_extra():
    ok, missing, extra = validate_translation("Take the item", "拿起{item}物品")
    assert not ok and extra == ["{item}"]


def test_extract_renpy_wavetime_tag():
    # Ren'Py 样式 {w=秒} 等号值标记必须识别为占位符（a-catfiends 真实漏检）
    assert extract_placeholders("HELLO.{w=3}{x}") == ["{w=3}", "{x}"]


def test_validate_missing_renpy_wavetime_tag():
    # 译文丢失 {w=N} 必须被拒绝（现状漏检：译文丢 {w=3} 仍通过）
    ok, missing, extra = validate_translation(
        "SOBER.{w=0.5} NOW.{w=3}{x}", "清醒了。{x}")
    assert not ok and missing == ["{w=0.5}", "{w=3}"]


def test_extract_renpy_close_tag():
    # Ren'Py 结束标签 {/i} {/b} 也属于必须保留的标记
    assert extract_placeholders("Hi {i}you{/i}!") == ["{i}", "{/i}"]


def test_validate_missing_renpy_close_tag():
    ok, missing, extra = validate_translation(
        "Hi {i}you{/i}", "你好{/i}")
    assert not ok and missing == ["{i}"]


def test_self_heal_backfills_missing_renpy_wavetime():
    # a-catfiends 真实样本：译文丢 1 个 {w=0.5} → 按原文顺序插回（{w=3} 前）
    healed = self_heal_format_tags(
        "AND,{w=0.5} IN SOME CASES,{w=0.5}\nEVEN REVERSE THE FLOW OF TIME.{w=3}{x}",
        "在某些情况下，AND的值为{w=0.5}。\n甚至颠倒时间的流动。{w=3}{x}")
    assert healed == ("在某些情况下，AND的值为{w=0.5}。"
                      "\n甚至颠倒时间的流动。{w=0.5}{w=3}{x}")
    ok, missing, extra = validate_translation(
        "AND,{w=0.5} IN SOME CASES,{w=0.5}\nEVEN REVERSE THE FLOW OF TIME.{w=3}{x}",
        healed)
    assert ok


def test_self_heal_backfills_missing_closing_color_tag():
    # interdream 真实样本：译文丢尾部 </color> → append 到末尾
    src = ("<color=#888888FF>(Can be set)</color>\n"
           "<color=#FF0000FF>You will know</color>")
    dst = ("<color=#888888FF>(Can be set)</color>\n"
           "<color=#FF0000FF>You will know")
    assert self_heal_format_tags(src, dst) == src


def test_self_heal_reorders_reversed_closing_tags():
    # the-keeper 真实样本：</b></color> 逆序 → 重排为原文顺序 </color></b>
    src = "<b><color=#eb5354>Thanks!</color></b>"
    dst = "<b><color=#eb5354>谢谢！</b></color>"
    assert self_heal_format_tags(src, dst) == "<b><color=#eb5354>谢谢！</color></b>"


def test_self_heal_returns_unchanged_when_no_gap():
    assert self_heal_format_tags("<b>Hi</b>", "<b>你好</b>") == "<b>你好</b>"
    assert self_heal_format_tags("Hello world", "你好，世界") == "你好，世界"


def test_self_heal_does_not_remove_extra_placeholders():
    # 模型新增占位符（幻觉）→ 原样返回，不自动删（仍由判定失败暴露）
    dst = "拿起{item}物品"
    assert self_heal_format_tags("Take the item", dst) == dst


def test_self_heal_does_not_repair_reordered_placeholders():
    # 占位符顺序破坏（%s 与 {0} 互换）→ 不是子序列 → 原样返回
    dst = "生命 {0} / %s"
    assert self_heal_format_tags("HP %s / {0}", dst) == dst


def test_self_heal_does_not_reorder_when_opening_tags_differ():
    # 开标签顺序不同（内容结构变化）→ 不重排闭合标签
    src = "<b><color=#fff>Hi</color></b>"
    dst = "<color=#fff><b>你好</b></color>"
    assert self_heal_format_tags(src, dst) == dst


def test_base64_zip_payload_is_skipped():
    # Morfosi level5 str/0 实证：base64 编码 ZIP 包（PK\x03\x04 魔数 UEsDB，
    # 结尾 == 填充符）。此前 _BASE64 字符集不含 '=' → fullmatch 失败漏网，
    # 模型整段回显恒败（untranslated_text）。
    payload = (
        "UEsDBBQAAAgIAACYn+uubW6iYAIAAAUFAAALACQAZ3JhcGgwLmpzb24KACAAAAAAAAEAGAAAg"
        "D7V3rGdAQCAPtXesZ0BAIA+1d6xnQFlVEtzmzAQ/isenRsP4Ne4t9ZxnB7ymLidXLjI0mI0Fh"
        "IjidhOxv+9KyEMdbkg9tvHt9+u+CJC2RqY02ZjBH/SHMj3EfFn8m3Ug49wonuttuITOp93wV"
        "3pnWjweaNOaLSnPszqCpwR7IfaS++coLFRotCmWvM9rLR1Fs0FlRYQMtr5aIWmrxE54etu6U"
        "POeMoW/vSJp2UyuuCRgXJgBq6T6Xjpn3kWQ9LlIoa0EY1iklY1cE+/D0zT+XjWVVlm41lwVth"
        "e9EsCzLSUwkZ2xJ3r0P22LsGAb58Lis0GRp5ACWJfuvhxjX0pCgsuKmHo+V4Y1KxNSn7qVsi"
        "K2kNL74PKxpfJZvNAqk369B9+lwa4MLp67Oqmia/hSsEOb/TMqHUDpYfm+554GlQ6UnmgOwn"
        "vJahnvTG6URxBZxof2ljI7vvPa2urEtiht7dUb4xN3cveDbYbq+/hEro/raSodkH4aWvYSh3"
        "kDtsABkfzCwmHXbExBVo9iz8WftP9cKki8CCMdQjFLpWnt9ON8a5kHTTz3TRupY2CYI6ka1B"
        "UuvMrpnG3I7zBBmVvkAfqr08sHrHuVtyEBHPvnyQ30Ks+XodlS318Alu+NE4KBT1pDzyjTiu"
        "tVLthQ026sG1jCsoGYftG8H9XixSTaVYs5lM2X0xSOqF3nE0zihdlniZZBospCbsnFPZJ5WtL"
        "NMqDU1N9coV71v1VRhtD67Dt3NDjRnxWeiC5UIXeMgOgXtoMV+JgsAheS77mAgXagnNChXmT"
        "r5xIzQ7A82uiPHS6PjlD8z5LTmrxoZ235GQVfiM5uZDLX1BLAwQUAAAICAAAmJ/rpZsc7G0AA"
        "AB4AAAACQAkAG1ldGEuanNvbgoAIAAAAAAAAQAYAACAPtXesZ0BAIA+1d6xnQEAgD7V3rGdA"
        "atWKkstKs7Mz1OyUjDRM9IzNNJRUEovSizIKAaKGII4pZkpIHa0UpqxiVGauZlJspm5sWGic"
        "aJuSrKJUaKRpZGZoYGRUaq5iVIsUH1JZUGqX2JuKkRPQGJJRlpmXkpmXrqee1FmijvIaKXYWg"
        "BQSwECLQAUAAAICAAAmJ/rrm1uomACAAAFBQAACwAkAAAAAAAAAAAAAAAAZ3JhcGgwLmpzb24"
        "KACAAAAAAAAEAGAAAgD7V3rGdAQCAPtXesZ0BAIA+1d6xnQFQSwECLQAUAAAICAAAmJ/rpZsc"
        "7G0AAAB4AAAACQAkAAAAAAAAAAAAAACtAgAAbWV0YS5qc29uCgAgAAAAAAABABgAAIA+1d6x"
        "nQEAgD7V3rGdAQCAPtXesZ0BUEsFBgAAAAACAAIAuAAAAGUDAAAAAA==")
    assert should_skip(payload)
    # 无 = 填充的普通 base64 序列化数据（含数字）仍拦截（原有行为）
    assert should_skip("aGVsbG8gd29ybGQgdGhpcyBpcyBiYXNlNjQgZGF0YTEyMzQ1Njc4OTEyMzQ1"
                       "Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3")
    # 纯字母超长串（无数字、无填充符）不是 base64 特征 → 不误伤
    assert not should_skip("A" * 100)


def test_skip_rules():
    assert should_skip("12345")
    assert should_skip("https://example.com/x")
    assert should_skip("user@mail.com")
    assert should_skip("---")
    assert should_skip("a")
    assert should_skip("{0}")
    assert should_skip("1.0.3")
    assert should_skip("Unity.InputSystem")
    assert should_skip("Assets/Plugins/x.dll")
    assert should_skip("Assembly-CSharp")
    assert should_skip("browscap.ini")
    # Unity 实例化对象名 / 点开头扩展名（真实语料漏检样本）
    assert should_skip("frameVertical(Clone)")
    assert should_skip("GreyPipeBendDown(Clone)")
    assert should_skip("Player(Clone)(Clone)")
    assert should_skip(".spriteatlas")
    assert should_skip(".wav")
    # GUID 标识符 / Master Audio 总线行 / 署名年份行 / 富文本纯符号字符画
    assert should_skip("GUID:cef3ca5fc32178c449992c58120ccded")
    assert should_skip("\t2810670744\tSoundFX\t\t\t"
                       "\\Default Work Unit\\Master Audio Bus\\SoundFX\t")
    assert should_skip("Darien Gore (Fleebs) 2019")
    assert should_skip("<color=#2b3534>▓<color=#FE09DA>▓"
                       "<color=#00AEEF>▓<color=white>▓")
    # IL2CPP Burst 编译器符号 / PDB 调试路径（识别层误收的 metadata 字面量）
    assert should_skip("Unity.Burst.Intrinsics.X86, Unity.Burst, Version=0.0.0.0, "
                       "Culture=neutral, PublicKeyToken=null::DoGetCSRTrampoline()"
                       "--89425a97f3f5")
    assert should_skip('PdbAltPath="Faerie Afterlight_Data/Plugins/x86_64"')
    # 版本号横幅（\t**\t\tVERSION 0.4.3\t\t**）：保留原文是行业惯例，跳过翻译
    assert should_skip("\t**\t\tVERSION 0.4.3\t\t**")
    assert should_skip("\t**\t\tVERSION 0.4.0\t\t**")
    # JSON 序列化字符串（引擎把数据序列化成字符串存资源；翻译会破坏语法）
    assert should_skip('{"declarations":{"collection":{"$content":[],'
                       '"$version":"A"},"$version":"A"}}')
    assert should_skip('{"nest":{"source":"Macro","macro":0,"embed":null}}')
    assert should_skip('[1,2,3,"assets"]')
    # 以 {/[ 开头的真实对话/文本：解析失败 → 必须保留
    assert not should_skip("[Catkus Companion]")
    assert not should_skip("[When a 'memory' is saved, the game saves progress.]")
    assert not should_skip("{name} 攻击了 {target}")
    # 开发者模板占位（真实语料漏检样本）：内容未填写的占位字符串
    assert should_skip("beast description here")
    assert should_skip("Quest description here")
    assert should_skip("Option description here!!!")
    assert should_skip("Description here")
    # 含这些词的真实对话/提示：必须保留
    assert not should_skip("I'm new here.")
    assert not should_skip("I'm here to shop!")
    assert not should_skip("Hey, I wonder if there's anything good in here?")
    assert not should_skip("Put your name here, traveler")
    # I2 Localization 复数模板（{0:p:mine|mines} 运行时展开，翻译会破坏语法）
    assert should_skip("{0} - {1} {1:p:mine|mines}")
    assert should_skip("{0} {0:p:charge|charges}")
    assert should_skip("{1:p:mouse|mice} hidden")
    assert should_skip("Reveals {0} random {0:p:column|columns}.")
    assert should_skip("Restores {0} <b>{0:p:heart|hearts}</b>.")
    # 开发者重复占位行（Hello\nHello\nHello\nHello 模型必回显，flabby-pizza 真实样本）
    assert should_skip("Hello\nHello\nHello\nHello")
    assert should_skip("test\ntest\ntest\ntest")
    # 真实重复/句子形态：必须保留
    assert not should_skip("No. No. No. No.")
    assert not should_skip("Hello\nHello")
    assert not should_skip("Hi there\nHi there")
    # 含 :p: 片段但形态不同的真实文本：必须保留
    assert not should_skip("Press P to pause")
    # IL2CPP 生成的模块调试行（\nmodule.renderOrderPriority: 引擎内部字符串）
    assert should_skip("\nmodule.renderOrderPriority: ")
    assert should_skip("\nmodule.sortOrderPriority: ")
    assert not should_skip("Modules are ready")
    # zalgo 乱码文本（组合字符叠加的字体艺术，翻译必然失败）
    assert should_skip("Ĭ̴̔̈̒́̌̔̓"
                       "̱́̃̉́̈́"
                       "'̴̀̏́̒̃̑")
    assert not should_skip("<b>Save</b>")
    assert not should_skip("Hello world")
    assert not should_skip("你好")
    assert not should_skip("OK")
    assert not should_skip("Start Game")
    assert not should_skip("こんにちは。")


@pytest.mark.parametrize("text", [
    "Click/Tap Me To Go To The Settings Screen.",
    "Click/Tap",
    "Load/Save",
    "Audio/Video",
    "On/Off",
    "Continue/",
    "Save/",
    "CREDITS/",
    r"Line one\nLine two",
    "<b>Press E</b> to continue.",
    "<color=#fff>Settings</color>",
])
def test_slashes_inside_display_text_are_not_paths(text):
    assert not should_skip(text)


def test_uri_mentioned_inside_display_sentence_is_not_a_full_value_uri():
    assert not should_skip("https://example.com/help is our support page.")


@pytest.mark.parametrize("text", [
    "https://example.com/settings",
    r"C:\\Games\\BFNS\\settings.json",
    "/usr/local/share/game/settings.json",
    "Assets/Plugins/x.dll",
    "config/ui/settings",
    "config/settings.json",
    r"config\settings.json",
    "../config/settings",
    "<Keyboard>/space",
    "<color=red>https://example.com/a?x=1</color>",
    "<b>http://example.com/help</b>",
])
def test_full_value_paths_uris_and_input_bindings_are_skipped(text):
    assert should_skip(text)


@pytest.mark.parametrize("text", [
    "UI/Navigate",
    "*/{Submit}",
    "Fonts & Materials/",
    "Sprite Assets/",
    "SpriteAssets/",
    "FontMaterials/",
    "DefaultPresets/",
    "Assets/",
    "Materials/",
    "Presets/",
    "*</size></b></color>",
])
def test_unity_input_actions_asset_folders_and_tag_fragments_are_skipped(text):
    assert should_skip(text)


@pytest.mark.parametrize("text", [
    # .NET 程序集全名（Addressables catalog m_AssemblyName 真实值）
    "Unity.ResourceManager, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null",
    "Assembly-CSharp, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null",
    # 协议相对 URL（A* 寻路库版权文件真实值）
    "//arongranberg.com/astar/",
    "//steamworks.github.io",
    # InputAction 绑定路径（swallow-the-sea level0 真实值，含方括号绑定段）
    "SwallowControls/MousePosition[/Mouse/position]",
    "Player/Aim[/Keyboard/mouse/point]",
    # CLI 参数（Burst 生成命令记录真实值）
    "--platform=Windows",
    "-target=Windows",
    "--linker-options=PdbAltPath=\"PanzerShoot_Data/Plugins/x86_64\"",
])
def test_structural_assembly_refs_protocol_urls_and_cli_args_are_skipped(text):
    assert should_skip(text)


@pytest.mark.parametrize("text", [
    # 对照组：带闭合 BB 标签的显示文本必须保持可翻译
    "Save[/b]",
    "Credits [More]",
    "- 下一行对话",
])
def test_bracketed_display_text_is_not_mistaken_for_structural(text):
    assert not should_skip(text)


@pytest.mark.parametrize("text", [
    # credit/署名/版权行：翻译必然破坏人名/品牌/法律文本（真实失败样本）
    "Created by Sam Hogan for the GMTK Game Jam 2020",
    "A* star pathfind project (free version) by Aron Granberg",
    "Horror-Style Impact 1 - from AudioBlocks.com",
    "Trailer Hit - Psyche - from AudioBlocks.com",
    "©FREEZESTUDIOS 2020",
    "Copyright (c) 2020 My Studio",
])
def test_credit_attribution_and_copyright_lines_are_skipped(text):
    assert should_skip(text)


@pytest.mark.parametrize("text", [
    # 对照组：credit 形状的普通句子必须保持可翻译
    "Press - Start",
    "we were found by Gary.",
    "It was made by Gary",
    "Open the door from the inside",
])
def test_attribution_shaped_sentences_are_not_skipped(text):
    assert not should_skip(text)


@pytest.mark.parametrize("text", [
    # 署名/版权反模式（软猜测）：is_credit_like 命中……
    "A game by Kyuppin",
    "Created by Sam Hogan",
    "made in 48h",
    "© 2021 Some Studio",
    "Game by Team Awesome",
])
def test_is_credit_like_soft_guess_hits_credit_lines(text):
    assert is_credit_like(text)
    # 提取层行为不变：is_hard_structural 仍跳过署名行
    assert is_hard_structural(text)


@pytest.mark.parametrize("text", [
    # 含句子虚词/多段句子 → 不是署名行，软猜测不命中
    "A game by Kyuppin, and it was fun",
    "we were found by Gary.",
    "It was made by Gary and it works",
    "This game was made by a team of three",
    "",
])
def test_is_credit_like_soft_guess_misses_sentences(text):
    assert not is_credit_like(text)


@pytest.mark.parametrize("text", [
    # TMP SDF 字体资产名（真实失败样本：ComicsCarToon SDF Zesty）
    "ComicsCarToon SDF Zesty",
    "roquetteplain SDF Bonus",
    "LiberationSans SDF - Outline",
])
def test_tmp_sdf_font_asset_names_are_skipped(text):
    assert should_skip(text)


@pytest.mark.parametrize("text", [
    # 键盘噪音测试占位符（真实失败样本：开发者乱打文本，翻译必然回显）
    "asdasdasd\nasda sdasd",
    "fdji ijsdijn j jnf oij iuhwr i iu iujn iubt tdr rf",
    "aaaaaaaaaaaa",
    # jam 署名带前导空白/换行（roots 真实样本）
    " \nmade in 48h\nfor Ludum Dare 48",
])
def test_keyboard_noise_and_jam_credit_are_skipped(text):
    assert should_skip(text)


@pytest.mark.parametrize("text", [
    # 对照组：真实小写文本/短词必须保持可翻译
    "hello world",
    "press any key",
    "banana bread",
    "welcome to the game",
    "A pretty tasty fruit, nothing special",
])
def test_normal_text_is_not_mistaken_for_noise(text):
    assert not should_skip(text)


def test_undertale_bullet_star_is_protected():
    """Undertale 对话行首 "* " 是脚本标记 → 译文必须保留（DELTATRAVELER 样本：
    模型把 "* (Text)" 合成"（Text）"丢了星号）。"""
    original = "* (Thankfully a standard snow\n  poff.)"
    translation = "（幸好有标准的雪）\npoff.)"
    ok, _, _ = validate_translation(original, translation)
    assert ok is False

    kept = "* (幸好有标准的雪)\npoff.)"
    ok, _, _ = validate_translation(original, kept)
    assert ok is True


def test_undertale_timing_code_is_protected():
    """行尾计时码 ")^05" → 译文必须保留（模型常丢 "^NN"）。"""
    original = "* (A snow poff?)^05\n* (In these trying times??!)"
    ok, _, _ = validate_translation(original, "* (雪怪？)^05\n*（在这艰难时刻？？！）")
    assert ok is False

    ok, _, _ = validate_translation(original, "* (雪怪？)^05\n* （在这艰难时刻？？！）")
    assert ok is True


def test_regular_text_bullet_lines_keep_leading_star():
    """普通多行文本行首 "* "（非 markdown 语义）→ 保护后译文也须保留。"""
    ok, _, _ = validate_translation("* Item one\n* Item two", "* 项目一\n* 项目二")
    assert ok is True

    ok, _, _ = validate_translation("* Item one", "项目一")
    assert ok is False
