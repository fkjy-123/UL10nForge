from hanhua.core.models import GameProfile
from hanhua.core.prompts import build_system_prompt, build_batch_user_prompt


def test_system_prompt_includes_profile_but_not_full_glossary():
    """术语/专名不再全量注入 system_prompt（2026-08-14 用户要求「大大
    精简」：全量 296 条术语 ≈ 2800 tokens 是 request exceeds context
    根因）——由 BatchTranslator 按条目检索命中注入（glossary_hits /
    knowledge_hits，见 test_ctx_budget）。"""
    profile = GameProfile(game_name="Echoes", genre="RPG", world_setting="幽谷世界", tone_notes="口语化")
    prompt = build_system_prompt(profile, ["Aria → 艾莉亚（人名）"], known_names=["Aria", "Orin"])
    assert "Echoes" in prompt and "RPG" in prompt and "幽谷世界" in prompt
    assert "艾莉亚" not in prompt and "Orin" not in prompt   # 全量块移除
    assert "占位符" in prompt


def test_system_prompt_empty_profile():
    prompt = build_system_prompt(GameProfile(), "")
    assert "专业游戏本地化翻译专家" in prompt
    assert "【术语表" not in prompt


def test_batch_prompt_shape():
    items = [{"id": "e1", "text": "Hello", "context": "prev: Hi", "short": True}]
    user = build_batch_user_prompt(items)
    assert '"e1": Hello' in user and "prev: Hi" in user
    assert "JSON" in user and '"translation"' in user
    assert "UI 短文本" in user


def test_batch_prompt_includes_localization_evidence_and_explicit_budget():
    items = [{
        "id": "menu/title@ui.assets", "text": "New Game",
        "file": "ui.assets", "key_path": "menu/title", "role": "ui",
        "confidence": "high", "context": "prev: Continue | next: Settings",
        "short": True, "budget": 6,
    }]

    user = build_batch_user_prompt(items)

    assert "[来源文件] ui.assets" in user
    assert "[定位键] menu/title" in user
    assert "[文本角色] ui" in user
    assert "[识别置信度] high" in user
    assert "[上下文] prev: Continue | next: Settings" in user
    assert "不得超过 6 个字符" in user


def test_system_prompt_instructs_translating_uppercase_text():
    prompt = build_system_prompt(GameProfile(), "")
    # 全大写字幕/UI 标签照常翻译（真实失败样本：[ S K I P ]、WELCOME TO...）
    assert "全大写文本" in prompt
    assert "不要因原文是大写而保留英文" in prompt
    assert "专名与品牌名" in prompt


def test_batch_prompt_protects_interaction_input_tokens():
    user = build_batch_user_prompt([{
        "id": "prompt@ui.assets", "text": "Press E to open",
        "input_tokens": ["E"],
    }])

    assert "输入按键" in user
    assert "E" in user
    assert "原样保留" in user


def test_batch_prompt_injects_role_specific_rule_by_reason():
    # 交互提示 reason → 专项策略（保留按键/操作结构，不扩写）
    user = build_batch_user_prompt([{
        "id": "e1", "text": "Press E to open the door",
        "reason": "interaction_prompt", "role": "display",
    }])

    assert "【专项·交互提示】" in user
    assert "原样保留按键名" in user
    assert "[文本角色] display" in user


def test_batch_prompt_injects_role_rule_fallback_when_no_reason():
    # 无 reason 时按 role 兜底匹配（细粒度角色未来由提取器产出）
    user = build_batch_user_prompt([{
        "id": "e1", "text": "Defeat the Warden", "role": "quest_objective",
    }])

    assert "【专项·任务目标】" in user


def test_batch_prompt_no_rule_for_unknown_role():
    user = build_batch_user_prompt([{
        "id": "e1", "text": "hello", "role": "no_such_role",
    }])

    assert "【专项·" not in user


def test_batch_prompt_reason_takes_priority_over_role():
    user = build_batch_user_prompt([{
        "id": "e1", "text": "Press E", "reason": "interaction_prompt",
        "role": "quest_objective",
    }])

    assert "【专项·交互提示】" in user
    assert "【专项·任务目标】" not in user


def test_batch_prompt_injects_hit_glossary_terms():
    user = build_batch_user_prompt([{
        "id": "e1", "text": "Use the Moon Key to unlock",
        "glossary_hits": [("Moon Key", "月光钥匙"), ("Unlock", "解锁")],
    }])

    assert "[术语命中]" in user
    assert "Moon Key → 月光钥匙" in user
    assert "Unlock → 解锁" in user
    assert "必须使用指定译名" in user


def test_batch_prompt_omits_glossary_line_when_no_hits():
    user = build_batch_user_prompt([{
        "id": "e1", "text": "Hello",
    }])

    assert "[术语命中]" not in user


# ── #10：Style/Personalization——游戏本地化角色 + 行为边界 ────

def test_system_prompt_has_localization_role_and_boundaries():
    """明确的游戏本地化角色 + 行为边界（不是普通机器翻译器）。"""
    prompt = build_system_prompt(GameProfile(), "")
    assert "专业游戏本地化翻译专家" in prompt
    assert "不是普通机器翻译器" in prompt
    assert "游戏本地化译者" in prompt
    assert "职责边界" in prompt
    assert "只做本地化翻译" in prompt


def test_system_prompt_has_game_context_ambiguity_rules():
    """play/resume 等语境词按游戏语境翻译（修复 play→播放、resume→简历）。

    2026-08-14 精简：20 词压缩为一行「词→核心译名」映射（原格式每条
    带语境列 ≈ 800 字符 → ≈ 300 字符）。
    """
    prompt = build_system_prompt(GameProfile(), "")
    assert "游戏语境歧义词" in prompt
    assert "play→开始游戏" in prompt
    assert "不是\"播放\"" in prompt
    assert "resume→继续" in prompt
    assert "不是\"简历\"" in prompt


def test_system_prompt_injects_custom_style_prompt():
    """profile.prompt_style 非空 → 个性化风格要求块优先注入。"""
    profile = GameProfile(prompt_style="play/resume 按键词必须译成「开始/继续」；技能名保持两字格式")
    prompt = build_system_prompt(profile, "")
    assert "个性化风格要求" in prompt
    assert "「开始/继续」" in prompt
    assert "两字格式" in prompt
    # 自定义风格要求出现在翻译规则之前（优先生效）
    assert prompt.index("个性化风格要求") < prompt.index("翻译规则")


def test_system_prompt_custom_style_absent_by_default():
    """未填 prompt_style 时不出现个性化块，仅内置角色。"""
    prompt = build_system_prompt(GameProfile(), "")
    assert "个性化风格要求" not in prompt
