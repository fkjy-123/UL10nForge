from __future__ import annotations
import json
from hanhua.core.models import GameProfile


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


def build_system_prompt(profile: GameProfile, glossary_lines: list[str] | str,
                        known_names: list[str] | None = None) -> str:
    src = profile.source_lang
    if src == "auto":
        src = "游戏原文语言（自动判断，可能是英语/日语/韩语等）"
    parts = [
        f"你是资深游戏本地化翻译专家。请将以下游戏的{src}文本翻译为简体中文。",
        "这是深度本地化翻译，不是逐字直译：译文必须贴合游戏世界观、角色性格与对话语境，读起来像母语中文玩家会看到的文本。",
    ]
    if profile.game_name:
        parts.append(f"【游戏】{profile.game_name}" + (f"（{profile.genre}）" if profile.genre else ""))
    if profile.world_setting:
        parts.append(f"【世界观设定】{profile.world_setting}")
    if profile.tone_notes:
        parts.append(f"【文风要求】{profile.tone_notes}")
    if profile.style_guide:
        parts.append(f"【风格指南】{profile.style_guide}")
    if isinstance(glossary_lines, str):
        glossary_lines = [glossary_lines] if glossary_lines else []
    if glossary_lines:
        parts.append("【术语表·必须严格遵守】\n" + "\n".join(glossary_lines))
    if known_names:
        parts.append("【已确认专名·全游戏保持一致】\n" + "、".join(known_names[:50]))
    parts.append(
        "【翻译规则】\n"
        "1. 必须原样保留所有占位符与格式标签（如 {0}、{name}、%s、<b>、<color=...>、[b]、\\n），不得增删改序。\n"
        "2. 术语表中的专名、人名、地名、道具名必须严格使用指定译名，不得自创译名。\n"
        "3. 短文本（UI 按钮、菜单项）保持简短自然，符合界面习惯用语（如\"开始游戏\"而非\"启动游戏之旅\"）。\n"
        "4. 对话文本口语化、符合角色身份；拒绝翻译腔和欧化句式。\n"
        "5. 语境不明时可利用相邻文本推断，保持同一批内语气与用词一致。\n"
        "6. 全大写文本（对话字幕、UI 标题、[ S K I P ] 式标签）照常翻译成自然中文："
        "全大写只表示强调语气，中文没有大小写，不要因原文是大写而保留英文。"
        "但专名与品牌名（游戏名、公司名、平台名如 Playstation/Steam/Xbox）保留原文。\n"
        "7. 无论原文是何种语言（英语/日语/俄语/意大利语/韩语等），一律翻译为简体中文；"
        "不得输出英文或其他语言的改写。\n"
        "8. 每一句都要翻译：除专名、品牌名、按键名外，任何英文单词或短语（包括 "
        "hello、back、press any key 这类短文本）都必须译为中文，禁止原样回显。\n"
        "9. 严格对照原文翻译：不得添加原文没有的句子或段落（不得续写、不得自行补全），"
        "不得改变行数，换行符保持原文形式（\\r\\n 与 \\n 不得相互转换）。\n"
        "10. 只输出 JSON，不要输出任何其他文字或代码块标记。"
    )
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
