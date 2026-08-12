"""任务四：知识库批量丰富（参考层入库脚本，防污染）。

5 个联网搜索方向 → ~30 条带来源参考条目，写入运行期 knowledge.db。

防污染规则（每条强制校验）：
- 域只允许 quality / unity_structure / component_compat（均在六库内，
  solve() 可检索；text 域会被 match_text / format_for_prompt 消费——
  参考条目绝不进 text 域，零行为影响）
- note 一律以 "ref:" 开头并带来源 URL（可追溯，区别于 seed/auto）
- source="web"（区别于 seed/manual/auto）
- 绝不写入 glossary.db（词对注入 prompt 的职能由术语表承担）

用法：python scripts/seed_knowledge_refs.py [knowledge.db 路径]
默认写入 ~/.hanhua/knowledge.db（运行期库）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hanhua.core.knowledge import KnowledgeStore  # noqa: E402

# ── 参考条目定义 ─────────────────────────────────────────────────
# pattern 是知识条目标识（非 text 域，不参与原文匹配，描述性标题即可）；
# map_to 供人工查阅对照；note 记录要点与来源。
# 来源：任务四五个搜索方向的网页资料（2026-08-13 采集）。
REFS: list[dict] = [
    # ── 方向 1：本地化行业规范（quality/l10n_guideline） ──────
    {"domain": "quality", "kind": "l10n_guideline",
     "pattern": "chinese_line_length", "action": "info",
     "map_to": "",
     "note": "ref:中文游戏文本行长规范：UI 单行一般 ≤ 27 个全角字符"
             "（约 27em），超过须允许换行或精简；控制台/手机端更短。"
             "来源：https://www.plumephp.com/client-localization-cjk-layout/",
     "url": "https://www.plumephp.com/client-localization-cjk-layout/"},
    {"domain": "quality", "kind": "l10n_guideline",
     "pattern": "placeholder_preservation", "action": "info",
     "map_to": "",
     "note": "ref:占位符/格式化串（%s、{0}、{name}）必须原样保留，"
             "参数顺序不得调换——换序或丢失会直接崩溃或显示乱码。"
             "来源：https://dev.epicgames.com/documentation/unreal-engine/text-localization-in-unreal-engine",
     "url": "https://dev.epicgames.com/documentation/unreal-engine/text-localization-in-unreal-engine"},
    {"domain": "quality", "kind": "l10n_guideline",
     "pattern": "voice_line_length_sync", "action": "info",
     "map_to": "",
     "note": "ref:有配音的台词行，译文长度须与口型/配音时长匹配："
             "过长会在播放未完时被截断，过短字幕悬空。"
             "来源：https://www.plumephp.com/client-localization-cjk-layout/",
     "url": "https://www.plumephp.com/client-localization-cjk-layout/"},
    {"domain": "quality", "kind": "l10n_guideline",
     "pattern": "cjk_punctuation", "action": "info",
     "map_to": "",
     "note": "ref:中文文本使用全角标点（，。！？「」），数字与英文"
             "保持半角；同一文本内中西混排须规范空格（中英之间可加半角空格）。"
             "来源：https://github.com/FAForever/fa/blob/develop/loc/guidelines.md",
     "url": "https://github.com/FAForever/fa/blob/develop/loc/guidelines.md"},
    {"domain": "quality", "kind": "l10n_guideline",
     "pattern": "short_string_context", "action": "info",
     "map_to": "",
     "note": "ref:短字符串（按钮/提示/属性名）脱离语境歧义极大，"
             "翻译须结合界面位置与相邻文本；开发术语如 Load/Save 在"
             "游戏语境下是 载入/存档 而非 装载/保存。"
             "来源：https://www.chinapharmconsulting.com/cn/hy_zs/78666.html",
     "url": "https://www.chinapharmconsulting.com/cn/hy_zs/78666.html"},
    {"domain": "quality", "kind": "l10n_guideline",
     "pattern": "locale_dependent_format", "action": "info",
     "map_to": "",
     "note": "ref:数字/日期/货币格式随语言变化（千分位、小数点、年月日"
             "顺序）；译文不得硬套原文格式。"
             "来源：https://www.plumephp.com/client-localization-cjk-layout/",
     "url": "https://www.plumephp.com/client-localization-cjk-layout/"},

    # ── 方向 2：游戏行业通用术语对照（quality/industry_terms） ──
    {"domain": "quality", "kind": "industry_terms",
     "pattern": "hp", "action": "info", "map_to": "生命值",
     "note": "ref:游戏通用缩写对照（UI 空间有限常用缩写，术语表参考）。"
             "来源：https://www.cnblogs.com/VincentValentine/p/15374372.html",
     "url": "https://www.cnblogs.com/VincentValentine/p/15374372.html"},
    {"domain": "quality", "kind": "industry_terms",
     "pattern": "mp", "action": "info", "map_to": "魔力值",
     "note": "ref:同上。来源：https://www.cnblogs.com/VincentValentine/p/15374372.html",
     "url": "https://www.cnblogs.com/VincentValentine/p/15374372.html"},
    {"domain": "quality", "kind": "industry_terms",
     "pattern": "xp", "action": "info", "map_to": "经验值",
     "note": "ref:同上。来源：https://www.cnblogs.com/VincentValentine/p/15374372.html",
     "url": "https://www.cnblogs.com/VincentValentine/p/15374372.html"},
    {"domain": "quality", "kind": "industry_terms",
     "pattern": "mob", "action": "info", "map_to": "怪物",
     "note": "ref:mobile/MOB 在游戏语境=怪物（非移动设备）。"
             "来源：http://www.fanyijia.com/news_view.asp?id=3788",
     "url": "http://www.fanyijia.com/news_view.asp?id=3788"},
    {"domain": "quality", "kind": "industry_terms",
     "pattern": "quest", "action": "info", "map_to": "任务",
     "note": "ref:Quest=任务（主线/支线），勿译「寻求」。"
             "来源：http://www.fanyijia.com/news_view.asp?id=3788",
     "url": "http://www.fanyijia.com/news_view.asp?id=3788"},
    {"domain": "quality", "kind": "industry_terms",
     "pattern": "inventory", "action": "info", "map_to": "背包/物品栏",
     "note": "ref:来源：https://www.cnblogs.com/VincentValentine/p/15374372.html",
     "url": "https://www.cnblogs.com/VincentValentine/p/15374372.html"},
    {"domain": "quality", "kind": "industry_terms",
     "pattern": "cooldown", "action": "info", "map_to": "冷却时间",
     "note": "ref:来源：https://www.cnblogs.com/VincentValentine/p/15374372.html",
     "url": "https://www.cnblogs.com/VincentValentine/p/15374372.html"},
    {"domain": "quality", "kind": "industry_terms",
     "pattern": "respawn", "action": "info", "map_to": "重生/复活点",
     "note": "ref:来源：http://www.fanyijia.com/news_view.asp?id=3788",
     "url": "http://www.fanyijia.com/news_view.asp?id=3788"},

    # ── 方向 3：专名/系列词与多义词（quality/false_friend） ──
    {"domain": "quality", "kind": "false_friend",
     "pattern": "new_game_plus", "action": "info", "map_to": "二周目",
     "note": "ref:New Game+ 社区标准译法为「二周目」（同类词：一周目/"
             "周目继承），直译「新游戏+」仅限严格对照场景。"
             "来源：https://zh.wikipedia.org/zh-cn/%E4%BA%8C%E5%91%A8%E7%9B%AE",
     "url": "https://zh.wikipedia.org/zh-cn/%E4%BA%8C%E5%91%A8%E7%9B%AE"},
    {"domain": "quality", "kind": "false_friend",
     "pattern": "charge", "action": "info", "map_to": "充能/冲锋/蓄力",
     "note": "ref:Charge 多义：技能蓄力/能量充能/近战冲锋——须按上下文"
             "判断，不可固定译法。来源：https://www.pttweb.cc/bbs/C_Chat/M.1659037029.A.6E2",
     "url": "https://www.pttweb.cc/bbs/C_Chat/M.1659037029.A.6E2"},
    {"domain": "quality", "kind": "false_friend",
     "pattern": "party", "action": "info", "map_to": "队伍",
     "note": "ref:Party 在 RPG=队伍（「派对」是聚会义）。"
             "来源：https://www.pttweb.cc/bbs/C_Chat/M.1659037029.A.6E2",
     "url": "https://www.pttweb.cc/bbs/C_Chat/M.1659037029.A.6E2"},
    {"domain": "quality", "kind": "false_friend",
     "pattern": "save", "action": "info", "map_to": "存档",
     "note": "ref:游戏语境 Save=存档（按钮/菜单），勿译「保存」；"
             "auto-save=自动存档。来源：https://www.chinapharmconsulting.com/cn/hy_zs/78666.html",
     "url": "https://www.chinapharmconsulting.com/cn/hy_zs/78666.html"},
    {"domain": "quality", "kind": "false_friend",
     "pattern": "dungeon", "action": "info", "map_to": "地下城",
     "note": "ref:来源：https://www.cnblogs.com/VincentValentine/p/15374372.html",
     "url": "https://www.cnblogs.com/VincentValentine/p/15374372.html"},
    {"domain": "quality", "kind": "false_friend",
     "pattern": "level", "action": "info", "map_to": "关卡/等级/级别",
     "note": "ref:Level 三义（关卡/角色等级/难度级别）须按语境区分。"
             "来源：http://www.fanyijia.com/news_view.asp?id=3788",
     "url": "http://www.fanyijia.com/news_view.asp?id=3788"},

    # ── 方向 4：Unity 本地化技术（unity_structure/localization_tech） ──
    {"domain": "unity_structure", "kind": "localization_tech",
     "pattern": "localizestringevent", "action": "info",
     "map_to": "",
     "note": "ref:LocalizeStringEvent（Unity Localization 1.x）绑定"
             " TextMeshPro 组件做运行时本地化：设置 String Table 引用 + "
             "Table Entry 后，语言切换自动更新文本。"
             "来源：https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/",
     "url": "https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/"},
    {"domain": "unity_structure", "kind": "localization_tech",
     "pattern": "stringtable_shared_entry", "action": "info",
     "map_to": "",
     "note": "ref:同类文本（如菜单「确定」「取消」）应共用同一 String "
             "Table Entry，保证全游戏术语一致；每场景单独建表会产生"
             "重复翻译。来源：https://learn.unity.com/tutorial/smarter-localization-with-unity-strings-assets-and-ui-toolkit",
     "url": "https://learn.unity.com/tutorial/smarter-localization-with-unity-strings-assets-and-ui-toolkit"},
    {"domain": "unity_structure", "kind": "localization_tech",
     "pattern": "addressables_localization", "action": "info",
     "map_to": "",
     "note": "ref:Localization 依赖 Addressables：本地化资源（表、字体、"
             "纹理）经 Addressables 异步加载，首次切换语言有加载延迟是"
             "正常现象。来源：https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/",
     "url": "https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/"},
    {"domain": "unity_structure", "kind": "localization_tech",
     "pattern": "locale_autodetect", "action": "info",
     "map_to": "",
     "note": "ref:Locale 自动检测（PlayerPrefs 缓存用户选择）；系统语言"
             "非支持列表时回退默认 locale——回退逻辑在部分版本有静默"
             "失效问题。来源：https://stackoverflow.com/questions/78444569/",
     "url": "https://stackoverflow.com/questions/78444569/"},
    {"domain": "unity_structure", "kind": "localization_tech",
     "pattern": "smart_format_placeholders", "action": "info",
     "map_to": "",
     "note": "ref:Unity Localization 默认用 Smart Format：{0}、{name}"
             " 为占位符，译文必须保留且可重排参数顺序；智能格式错误"
             "会整条文本不渲染。来源：https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/",
     "url": "https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/"},
    {"domain": "unity_structure", "kind": "localization_tech",
     "pattern": "localized_asset_variant", "action": "info",
     "map_to": "",
     "note": "ref:LocalizedAsset（纹理/音频/精灵）为每种语言存变体资源；"
             "汉化时若有中文版美术资源（如含字图片），须替换变体而非"
             "全局替换原图。来源：https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/",
     "url": "https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/"},

    # ── 方向 5：误译案例经验（quality/false_friend 案例化） ──
    {"domain": "quality", "kind": "false_friend",
     "pattern": "unit_measurement_localization", "action": "info",
     "map_to": "",
     "note": "ref:游戏内计量单位（英尺/英里/磅）汉化时按行业惯例换算为"
             "公制或保留原文加注释——不可直译「英尺」混入中式表达。"
             "来源：https://zhuanlan.zhihu.com/p/657516564",
     "url": "https://zhuanlan.zhihu.com/p/657516564"},
    {"domain": "quality", "kind": "false_friend",
     "pattern": "skill_name_style", "action": "info",
     "map_to": "",
     "note": "ref:技能名翻译保持四字风格统一（如「烈焰风暴」），同一"
             "系列技能名译法须成套；玩家社区对技能名有固定叫法时优先"
             "沿用社区叫法。来源：https://zhuanlan.zhihu.com/p/657516564",
     "url": "https://zhuanlan.zhihu.com/p/657516564"},
    {"domain": "quality", "kind": "false_friend",
     "pattern": "slang_register", "action": "info",
     "map_to": "",
     "note": "ref:俚语/口语须按角色语域处理（粗俗程度、时代感、地区感），"
             "直译会失真；语气词与口头禅应本地化为中文习惯表达。"
             "来源：https://zhuanlan.zhihu.com/p/657516564",
     "url": "https://zhuanlan.zhihu.com/p/657516564"},
    {"domain": "quality", "kind": "false_friend",
     "pattern": "boss_name_keep_original", "action": "info",
     "map_to": "",
     "note": "ref:专名（人名/地名/称号）先查官方中文版与玩家社区共识；"
             "无共识的高辨识度专名可保留原文，但首现须有对照注释。"
             "来源：https://zhuanlan.zhihu.com/p/657516564",
     "url": "https://zhuanlan.zhihu.com/p/657516564"},
    {"domain": "quality", "kind": "false_friend",
     "pattern": "chinese_four_character_idiom", "action": "info",
     "map_to": "",
     "note": "ref:成语/熟语翻译忌直译与套用汉化腔；优先级：官方译名 > "
             "社区通用译法 > 直译。来源：https://www.pttweb.cc/bbs/C_Chat/M.1659037029.A.6E2",
     "url": "https://www.pttweb.cc/bbs/C_Chat/M.1659037029.A.6E2"},

    # ── 组件兼容（component_compat/localization） ──
    {"domain": "component_compat", "kind": "localization",
     "pattern": "tmpro_font_fallback_cjk", "action": "info",
     "map_to": "",
     "note": "ref:TextMeshPro 显示中文须配置字体回退链（TMP Settings "
             "Fallback Font List）或中文 TMP 字体资源；缺回退时中文"
             "显示为方块。来源：https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/",
     "url": "https://docs.unity3d.com/Packages/com.unity.localization@1.4/manual/"},
    {"domain": "component_compat", "kind": "localization",
     "pattern": "ui_toolkit_localization", "action": "info",
     "map_to": "",
     "note": "ref:UI Toolkit（uGUI 后继）本地化走 UIElements 的 "
             "LocalizedStringBinding；与 TextMeshPro 的 LocalizeStringEvent"
             " 是两套机制，排查时须区分。来源：https://learn.unity.com/tutorial/smarter-localization-with-unity-strings-assets-and-ui-toolkit",
     "url": "https://learn.unity.com/tutorial/smarter-localization-with-unity-strings-assets-and-ui-toolkit"},
]

ALLOWED_DOMAINS = {"quality", "unity_structure", "component_compat"}


def main() -> int:
    db_path = Path(sys.argv[1] if len(sys.argv) > 1
                   else Path.home() / ".hanhua" / "knowledge.db")
    store = KnowledgeStore(db_path)
    store.init_schema()
    added = existed = 0
    for ref in REFS:
        assert ref["domain"] in ALLOWED_DOMAINS, \
            f"防污染校验失败（禁止域）：{ref}"
        assert ref["note"].startswith("ref:"), \
            f"note 必须 ref: 开头：{ref['pattern']}"
        assert ref["url"], f"必须带来源 URL：{ref['pattern']}"
        is_new = store.upsert(
            ref["domain"], ref["kind"], ref["pattern"],
            action=ref.get("action", "info"),
            map_to=ref.get("map_to", ""),
            note=ref["note"], source="web")
        added += is_new
        existed += not is_new
    print(f"入库完成：新增 {added} 条，已存在刷新 {existed} 条"
          f"（共 {added + existed} 条参考条目）→ {db_path}")
    print("── 逐域统计 ──")
    for domain in ("quality", "unity_structure", "component_compat"):
        rows = store.list_by_domain(domain)
        kinds: dict[str, int] = {}
        for r in rows:
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        print(f"{domain}: 共 {len(rows)} 条 {kinds}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
