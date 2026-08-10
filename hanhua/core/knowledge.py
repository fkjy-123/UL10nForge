from __future__ import annotations
import re
import sqlite3
import threading
from pathlib import Path

from hanhua.core.placeholders import should_skip

# ────────────────────────────────────────────────────────────────────────
# 知识库：汉化全链路（识别/翻译/写回/质量门）遇到的特殊情况的经验存储。
#
# 与术语库（GlossaryStore）分工：术语库存「专名/术语的译名映射」；
# 知识库存「特殊情况 → 处置规则」，按 domain 分库、kind 细分：
#
#   domain=text     特殊文本形态（可翻译语义文本的特征模式）
#     kind=spaced_action      间隔动作词（* Y A W N * → * 哈欠 *）
#     kind=uppercase_action   全大写动作指令（TOSS TRASH → 丢垃圾）
#     kind=interaction_prompt 交互提示（Press E to open → 保留按键）
#   domain=file     特殊文件形态（容器/记录布局约束）
#     kind=us_record          #US 字符串（UTF-16 固定码元容量，预算=码元数）
#     kind=il2cpp_string      IL2CPP metadata（UTF-8 变长，链式 dataIndex）
#   domain=rule     抽象规则（跨场景的确定性处置策略）
#     kind=placeholder_restore   译文缺 {n} 补末尾（string.Format 按索引取参）
#     kind=truncation_partial    超容量按字符收尾 + 省略号（部分翻译写回）
#     kind=echo_no_exempt        全大写动作指令回显不豁免（质量门）
#
# 规则 = 匹配特征（pattern）+ 处置策略（action）+ 建议结果（map_to，可选）
# + 来源备注（note）+ 命中证据（hits）。内置种子规则随代码分发（立即生效，
# 确定性、零成本）；跑完每场游戏后 learn() 把「该翻未翻」的新模式自动
# 沉淀入库（幂等），跨游戏持续积累，后续版本可沉淀为内置规则。
# ────────────────────────────────────────────────────────────────────────

# ── 内置种子 1：文本形态识别（确定性，无需查库） ─────────────────────────

# 大写动作指令的动作动词表：全大写短语含这些词 → 判为动作/命令文本，
# 必须翻译（回显=失败）。MEGA CORP / STAR WARS 等真专名不含动作词，
# 不会误命中（专名仍走 proper_name_echo 豁免）。随游戏积累扩充。
_UPPERCASE_ACTION_VERBS = frozenset("""
toss throw pick press push pull use open close enter exit start stop go
skip drop grab take give combine inspect look read eat drink equip swap
craft build break chop mine fish sleep save load quit back next confirm
cancel walk run jump attack defend heal buy sell trade activate deactivate
turn flip drag release catch chase hide sneak shoot aim reload fill empty
pour stack unstack place remove insert attach detach fix repair unlock lock
search examine check view focus zoom pause resume accept decline agree
disagree pay earn win lose fight escape die respawn talk speak shout
scream call listen watch cut dig shovel plant water harvest cook grill
season serve taste smell touch lift carry throw spin rotate shake smash
kick punch hit poke pat clean wash rinse dry iron fold hang wear
""".split())


def _is_uppercase_action(text: str) -> bool:
    """全大写短语 + 含动作动词 → 大写动作指令（TOSS TRASH / PRESS START）。

    判定：2-5 个全大写词，整串字母全大写，至少一个词是动作动词。
    """
    stripped = str(text).strip()
    if not stripped or stripped.isdigit():
        return False
    words = re.findall(r"[A-Z][A-Z0-9']{1,}", stripped)
    if not 2 <= len(words) <= 5:
        return False
    letters = re.sub(r"[^A-Za-z]", "", stripped)
    if not letters or not letters.isupper():
        return False
    return any(word.casefold() in _UPPERCASE_ACTION_VERBS
               for word in words)


def _is_spaced_action(text: str) -> bool:
    """间隔动作词：单字母以空格间隔的全大写词（* Y A W N * / G A S P）。
    字母间有空格 = 文字化动作/音效表现（打哈欠/惊呼），非专名。"""
    stripped = str(text).strip("* \t")
    if len(stripped) < 3 or " " not in stripped:
        return False
    parts = stripped.split()
    return bool(parts and all(
        len(part) == 1 and part.isupper() for part in parts))


# 其他语言（非英语）源文本的脚本特征：日文假名（平/片）与带重音拉丁
# 字母（法/意/西/葡等欧洲语言）。游戏多语言打包（同一对象存英/法/意/日
# 四版文本）时，英中模型对日语/重音文本倾向输出**英语译文**（alisa-demo
# 实证 26 条日语/意语 → 准确英语但目标语错误）——质量门须拦截（英文残留），
# 重试走「第一跳英语译文 → 第二跳英译中」双跳，或同对象译例（同 obj
# 兄弟条目的成功译文作参考注入）。
_JAPANESE_KANA_RE = re.compile(r"[぀-ヿㇰ-ㇿ]")
_ACCENTED_LATIN_RE = re.compile(
    r"[À-ÖØ-Þßà-öø-ÿ]")
# 罗曼语族（法/意/西/葡）ASCII 功能词：与英语共用拉丁字母，但冠词/介词
# 不同（Chiave di Ferro 的 di、Il cibo 的 Il）。英语中这些词罕见（多为
# 音名/叹词，如 la/si/e）——出现即疑为罗曼语言源文本，须译中文。
_ROMANCE_FUNCTION_WORDS = frozenset("""
il lo la le les i gli un una di del della dei delle du des au aux
su sul sulla nel nella nello nei negli nelle con per tra fra che chi si
je tu il elle nous vous et mais ou avec en por para entre
da de ne ve ci vi
""".split())
_ASCII_WORD_RE = re.compile(r"[A-Za-z]{2,}")


def _is_multilingual_source(text: str) -> bool:
    """原文含日文假名/带重音拉丁字母/罗曼语功能词 → 非英语源文本。

    判定独立于目标语：这类原文模型对其默认输出英语是目标语错误
    （质量门拦截 + 双跳修复 + 同对象译例兜底）。
    """
    if _JAPANESE_KANA_RE.search(text) or _ACCENTED_LATIN_RE.search(text):
        return True
    words = [w.casefold() for w in _ASCII_WORD_RE.findall(text)]
    return any(w in _ROMANCE_FUNCTION_WORDS for w in words)


# 大写动作指令的机械直译词表（EN→ZH）。用途：learn() 沉淀「该翻未翻」
# 条目时自动生成建议译名（map_to）——重试降级走 native_translate（Hy-MT2
# 无 system prompt 契约），模型看不到知识库规则，译例通过 references 的
# terms 机制带出（"TOSS TRASH translates to 丢垃圾"）。词表是跨游戏通用
# 知识（动作/命令高频词），随游戏积累扩充，非单游戏特判。
_ACTION_VERB_ZH = {
    "toss": "丢", "throw": "扔", "press": "按", "push": "推", "pull": "拉",
    "use": "使用", "open": "打开", "close": "关闭", "enter": "进入",
    "exit": "离开", "start": "开始", "stop": "停止", "go": "出发",
    "skip": "跳过", "drop": "丢弃", "pick": "捡起", "grab": "抓住",
    "take": "拿取",
    "give": "交给", "combine": "组合", "inspect": "检查", "look": "查看",
    "read": "阅读", "eat": "吃掉", "drink": "喝掉", "equip": "装备",
    "swap": "交换", "craft": "制作", "build": "建造", "break": "破坏",
    "chop": "砍伐", "mine": "挖掘", "fish": "钓鱼", "sleep": "睡觉",
    "save": "保存", "load": "读取", "quit": "退出", "back": "返回",
    "next": "下一步", "confirm": "确认", "cancel": "取消", "walk": "行走",
    "run": "奔跑", "jump": "跳跃", "attack": "攻击", "defend": "防御",
    "heal": "治疗", "buy": "购买", "sell": "出售", "trade": "交易",
    "activate": "激活", "deactivate": "停用", "turn": "转动", "flip": "翻转",
    "drag": "拖拽", "release": "释放", "catch": "接住", "chase": "追逐",
    "hide": "躲藏", "sneak": "潜行", "shoot": "射击", "aim": "瞄准",
    "reload": "装弹", "fill": "装满", "empty": "清空", "pour": "倒出",
    "stack": "堆叠", "place": "放置", "remove": "移除", "insert": "插入",
    "attach": "安装", "detach": "分离", "fix": "修复", "repair": "修理",
    "unlock": "解锁", "lock": "锁定", "search": "搜索", "examine": "检查",
    "check": "查看", "focus": "聚焦", "zoom": "缩放", "pause": "暂停",
    "resume": "继续", "accept": "接受", "decline": "拒绝", "agree": "同意",
    "disagree": "不同意", "pay": "支付", "earn": "赚取", "win": "获胜",
    "lose": "失败", "fight": "战斗", "escape": "逃跑", "die": "死亡",
    "respawn": "重生", "talk": "交谈", "speak": "说话", "shout": "喊叫",
    "scream": "尖叫", "call": "呼叫", "listen": "聆听", "watch": "观看",
    "cut": "切割", "dig": "挖掘", "shovel": "铲挖", "plant": "种植",
    "water": "浇水", "harvest": "收获", "cook": "烹饪", "grill": "烧烤",
    "season": "调味", "serve": "端上", "taste": "品尝", "smell": "嗅闻",
    "touch": "触摸", "lift": "举起", "carry": "携带", "spin": "旋转",
    "rotate": "转动", "shake": "摇晃", "smash": "砸碎", "kick": "踢",
    "punch": "出拳", "hit": "击打", "poke": "戳", "pat": "轻拍",
    "clean": "清洁", "wash": "清洗", "rinse": "冲洗", "dry": "晾干",
    "iron": "熨烫", "fold": "折叠", "hang": "挂起", "wear": "穿戴",
}
# 大写动作短语中常见名词（TOSS TRASH 的 TRASH），补动作词的语义完整
_COMMON_NOUN_ZH = {
    "trash": "垃圾", "axe": "斧头", "ball": "球", "door": "门",
    "key": "钥匙", "box": "箱子", "sword": "剑", "shield": "盾牌",
    "arrow": "箭", "bow": "弓", "potion": "药水", "item": "物品",
    "wood": "木头", "stone": "石头", "food": "食物", "water": "水",
}


# 机械直译跳过的功能词（冠词/介词/连词），如 OPEN THE DOOR 的 THE
_ACTION_SKIP_WORDS = frozenset("""
the a an up down off on in out into onto to of with and from for at by
it its my your our their this that these those me you we they
""".split())


def translate_uppercase_action(text: str) -> str | None:
    """大写动作指令的机械直译（词表逐词映射，全部命中才返回）。

    "TOSS TRASH" → "丢垃圾"、"OPEN THE DOOR" → "打开门"；含词表外
    单词（如专名）→ None（不兜底，避免机械翻译弄出错误专名）。
    供 learn() 生成 map_to 建议译名。
    """
    stripped = str(text).strip()
    words = re.findall(r"[A-Z][A-Z0-9']{1,}", stripped)
    if not words:
        return None
    table = {**_ACTION_VERB_ZH, **_COMMON_NOUN_ZH}
    parts = []
    for word in words:
        if word.casefold() in _ACTION_SKIP_WORDS:
            continue
        zh = table.get(word.casefold())
        if zh is None:
            return None
        parts.append(zh)
    return "".join(parts) if parts else None


# ── 内置种子 2：抽象规则/文件知识（跨场景处置策略，随代码分发） ──────────

BUILTIN_RULES: tuple[dict, ...] = (
    # text：文本形态
    {"domain": "text", "kind": "spaced_action",
     "pattern": "字母单字空格间隔的全大写词（* Y A W N *）",
     "action": "translate",
     "map_to": "中文动作/音效词（* 哈欠 *），保留星号与格式",
     "note": "seed:规则11-间隔动作词文字化表现（a-catfiends 实证 6 条回显）"},
    {"domain": "text", "kind": "uppercase_action",
     "pattern": "全大写短语含动作动词（TOSS TRASH / PRESS START）",
     "action": "translate",
     "map_to": "中文动作/命令短语（丢垃圾）",
     "note": "seed:知识库首案（taxes 实证 2 条 TOSS TRASH 回显被专名豁免）"},
    {"domain": "text", "kind": "interaction_prompt",
     "pattern": "Press/按 + 按键 + 动作（Press E to open）",
     "action": "translate_keep_tokens",
     "map_to": "按 E 打开（保留按键字面量）",
     "note": "seed:交互提示——按键字面量必须原样保留"},
    {"domain": "text", "kind": "multilingual_source",
     "pattern": "原文含日文假名或带重音拉丁字母（法/意/西/葡…）",
     "action": "translate",
     "map_to": "中文（模型常误译为英语，须以中文为目标语：双跳或同对象译例）",
     "note": "seed:多语言打包游戏（alisa-demo 实证 26 条日语/意语 → 准确英语但目标语错误）"},
    {"domain": "text", "kind": "platform_name",
     "pattern": "小写平台/网站名（itch=itch.io、discord、steam 等）出现在 "
                "on/at + 平台名 + page/store/链接语境",
     "action": "keep_source",
     "map_to": "保留平台名原文 + 译其余（'itch page' → 'itch 页面'；模型把 "
               "itch 当普通词直译「痒页面」是稳定误译，backrooms 实证）",
     "note": "seed:独立游戏平台名（itch.io）跨游戏高频，直译破坏语境辨识"},
    # file：特殊文件形态
    # file：特殊文件形态
    {"domain": "file", "kind": "us_record",
     "pattern": "DLL #US 字符串记录（压缩前缀+UTF-16LE+标志字节）",
     "action": "capacity_fixed",
     "map_to": "容量=码元数；预算 max_chars=码元；超限截断+省略号",
     "note": "seed:#US 固定码元容量（taxes 'I did ' 实证 max_chars 字节/码元错位）"},
    {"domain": "file", "kind": "il2cpp_string",
     "pattern": "IL2CPP global-metadata 字符串池",
     "action": "capacity_variable",
     "map_to": "UTF-8 变长，dataIndex 链式更新，顺序配对验证",
     "note": "seed:IL2CPP 变长写回（v39 链式 dataIndex）"},
    # rule：抽象规则
    {"domain": "rule", "kind": "placeholder_restore",
     "pattern": "译文缺失原文的 {n} 占位符",
     "action": "restore_to_end",
     "map_to": "缺失占位符补到译文末尾（string.Format 按索引取参位置无关）",
     "note": "seed:模型漏 {n} 是稳定行为，机械补回避免 reject 丢好译文"},
    {"domain": "rule", "kind": "truncation_partial",
     "pattern": "译文超容量",
     "action": "partial_write",
     "map_to": "按字符收尾+省略号，部分翻译写入且不阻断发布",
     "note": "seed:截断=容量内最优解，不因 1 条截断拖垮整场写回"},
    {"domain": "rule", "kind": "echo_no_exempt",
     "pattern": "知识库文本规则命中但译文回显原文",
     "action": "fail_untranslated",
     "map_to": "回显一律判失败并重试（不得当专名豁免）",
     "note": "seed:全大写动作指令/间隔动作词回显不得豁免"},
    # ── 六库蓝图：unity_struct（Unity 结构与资源定位库） ──
    {"domain": "unity_struct", "kind": "unity_version",
     "pattern": "Unity 2018-2019：AssetBundle 常见、Text 组件多、Localization 少",
     "action": "info",
     "map_to": "资源结构简单但兼容旧格式；2021+：Addressables 增加、TMP 大量、"
               "Localization Package 普及 → 文本分散、写回复杂",
     "note": "seed:六库1-先判断 Unity 版本再选提取/写回方案"},
    {"domain": "unity_struct", "kind": "asset_type",
     "pattern": "TextAsset（配置/对话/JSON/CSV）",
     "action": "info",
     "map_to": "优先直接替换文本内容；MonoBehaviour 检查序列化字段；"
               "AssetBundle 备份+重建（直接改可能破坏结构）",
     "note": "seed:六库1-资源类型决定处理方式"},
    # ── 六库蓝图：text_type（文本类型与处理规则库） ──
    {"domain": "text_type", "kind": "debug_text",
     "pattern": "Debug 日志/调试输出文本",
     "action": "skip",
     "map_to": "不翻译（玩家不可见，翻译无价值且可能破坏日志语义）",
     "note": "seed:六库3-调试文本不翻译"},
    {"domain": "text_type", "kind": "code_text",
     "pattern": "无空格大写驼峰（PlayerController）→ 类名/代码标识符特征",
     "action": "skip",
     "map_to": "不翻译（代码按原名查找，翻译破坏功能）；"
               "Attack Damage +10% 等游戏文本才翻译",
     "note": "seed:六库3-代码文本 vs 游戏文本的判断规则"},
    {"domain": "text_type", "kind": "term_consistency",
     "pattern": "技能/装备/成就等游戏术语",
     "action": "translate_consistent",
     "map_to": "首次翻译后全局统一（Health→生命值，不得再出现 血量/生命/HP值）",
     "note": "seed:六库3-术语统一是汉化品质核心"},
    # ── 六库蓝图：component（Unity 组件兼容库） ──
    {"domain": "component", "kind": "ugui_text",
     "pattern": "Unity UI Text 组件中文乱码",
     "action": "replace_font",
     "map_to": "默认字体不支持中文 → 替换 Font 为中文支持字体",
     "note": "seed:六库4-后台成功游戏失败的第一类原因"},
    {"domain": "component", "kind": "textmeshpro",
     "pattern": "TMP 文本中文显示方块（□）",
     "action": "rebind_font_asset",
     "map_to": "TMP Font Asset 缺中文字形 → 生成中文 Atlas + 重新绑定 Font Asset",
     "note": "seed:六库4-TMP 是 2021+ 重点组件"},
    {"domain": "component", "kind": "dropdown",
     "pattern": "Dropdown 选项翻译成功但列表仍英文",
     "action": "patch_data_source",
     "map_to": "显示文本已改但数据源未替换 → 修改 Option List 数据源",
     "note": "seed:六库4-不是所有文本都直接改字符串"},
    {"domain": "component", "kind": "ui_toolkit",
     "pattern": "UI Toolkit 文本（UXML/USS/Localization Table）",
     "action": "locate_source",
     "map_to": "文本来源在 UXML/USS/Localization Table，先定位再替换",
     "note": "seed:六库4-UI Toolkit 与 UGUI 文本存放位置不同"},
    # ── 六库蓝图：quality（翻译质量库） ──
    {"domain": "quality", "kind": "scoring",
     "pattern": "翻译质量评分：语义 40 + 上下文 30 + 中文自然 20 + 术语统一 10",
     "action": "info",
     "map_to": "Critical Strike Chance 错译『关键打击机会』=40 分；"
               "『暴击率』=95 分——目标是游戏本地化而非机器翻译",
     "note": "seed:六库5-质量评分标准"},
    {"domain": "quality", "kind": "common_error",
     "pattern": "多义词按游戏语境判断：Charge→冲锋/蓄力/费用（非充电）、"
                "Skill Tree→技能树（非技能树木）",
     "action": "context_judge",
     "map_to": "翻译后自检：是否符合上下文/游戏习惯/无歧义/不与既有术语冲突",
     "note": "seed:六库5-常见翻译错误需上下文判断"},
    # ── 六库蓝图：writeback_verify（写回与运行验证库） ──
    {"domain": "writeback_verify", "kind": "verify_flow",
     "pattern": "写回后运行验证流程：启动→主菜单→设置→新游戏→核心玩法→"
                "暂停菜单→存档→退出",
     "action": "verify",
     "map_to": "各环节逐项检查：游戏启动正常/菜单正常/文本显示正常",
     "note": "seed:六库6-统一验证流程，不同游戏同样覆盖"},
    {"domain": "writeback_verify", "kind": "bundle_damage",
     "pattern": "写回后游戏黑屏",
     "action": "runtime_patch",
     "map_to": "Bundle 结构损坏 → 改用运行时替换方案，而非直接改 Bundle",
     "note": "seed:六库6-写回失败记录（黑屏=结构损坏信号）"},
)


class KnowledgeStore:
    """知识条目库（SQLite，跨项目共享）。多库 = domain 分库聚合。"""

    def __init__(self, db_path: str | Path):
        self.db = Path(db_path)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.db), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self):
        with self._lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                kind TEXT NOT NULL,
                pattern TEXT NOT NULL,
                action TEXT NOT NULL DEFAULT '',
                map_to TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                hits INTEGER NOT NULL DEFAULT 0,
                UNIQUE(domain, kind, pattern)
            );""")
            self.conn.commit()

    # ── 写入 ──

    def upsert(self, domain: str, kind: str, pattern: str, *,
               action: str = "", map_to: str = "", note: str = "",
               hits: int = 1) -> bool:
        """幂等入库：已存在则 hits+1 并刷新来源备注，返回是否新增。"""
        with self._lock:
            row = self.conn.execute(
                "SELECT id FROM knowledge_items"
                " WHERE domain=? AND kind=? AND pattern=?",
                (domain, kind, pattern)).fetchone()
            if row is None:
                self.conn.execute(
                    "INSERT INTO knowledge_items"
                    "(domain, kind, pattern, action, map_to, note, hits)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (domain, kind, pattern, action, map_to, note, hits))
                self.conn.commit()
                return True
            self.conn.execute(
                "UPDATE knowledge_items SET hits=hits+?, note=? WHERE id=?",
                (max(1, hits), note, row["id"]))
            self.conn.commit()
            return False

    def list_by_domain(self, domain: str) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(
                "SELECT * FROM knowledge_items WHERE domain=?"
                " ORDER BY hits DESC, id", (domain,))]

    def list_all(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(
                "SELECT * FROM knowledge_items ORDER BY domain, kind, hits DESC")]

    def delete(self, domain: str, kind: str, pattern: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM knowledge_items"
                " WHERE domain=? AND kind=? AND pattern=?",
                (domain, kind, pattern))
            self.conn.commit()

    def close(self):
        with self._lock:
            self.conn.close()


class KnowledgeBase:
    """知识库聚合入口：内置种子规则（BUILTIN_RULES）+ 持久库。

    识别/翻译/质量门/写回各阶段按需查询——文本形态用零成本确定性
    识别函数（_is_uppercase_action / _is_spaced_action），抽象规则
    与文件知识通过 describe/list 供给报告、文档与人工查阅。
    """

    def __init__(self, db_path: str | Path | None = None):
        self.store: KnowledgeStore | None = None
        if db_path is not None:
            self.store = KnowledgeStore(db_path)
            self.store.init_schema()

    # ── text 域：文本形态匹配（翻译/质量门用） ──

    def match_text(self, text: str) -> list[dict]:
        """文本形态识别：内置确定性函数 + 持久库精确原文对照。"""
        rules: list[dict] = []
        if _is_spaced_action(text):
            rules.append({
                "domain": "text", "kind": "spaced_action",
                "pattern": "spaced_uppercase", "action": "translate",
                "map_to": "", "note": "内置：字母间隔全大写=动作/音效表现",
            })
        if _is_uppercase_action(text):
            rules.append({
                "domain": "text", "kind": "uppercase_action",
                "pattern": "uppercase_verb_phrase", "action": "translate",
                "map_to": "", "note": "内置：全大写含动作动词=动作/命令文本",
            })
        if _is_multilingual_source(text):
            rules.append({
                "domain": "text", "kind": "multilingual_source",
                "pattern": "kana_or_accented_latin", "action": "translate",
                "map_to": "", "note": "内置：含假名/重音拉丁=其他语言，须译中文",
            })
        if self.store is not None:
            for row in self.store.list_by_domain("text"):
                if row["kind"] in {"spaced_action", "uppercase_action"}:
                    continue  # 形态识别已覆盖，持久库只存精确原文对照
                try:
                    if re.search(row["pattern"], text, re.I):
                        rules.append(row)
                except re.error:
                    continue
        return rules

    def requires_translation(self, text: str) -> bool:
        """命中「必须翻译」规则（回显不得豁免）→ True。"""
        return any(r["action"] == "translate"
                   for r in self.match_text(text))

    # ── prompt 注入 ──

    def format_for_prompt(self, limit: int = 0) -> str:
        """翻译阶段注入的规则文本：内置形态规则短句 + 持久库最新
        limit 条精确对照（map_to 有值才注入，避免膨胀）。"""
        lines = [
            "[特殊文本] * Y A W N * 等字母间隔全大写词是动作/音效表现，"
            "须译为中文动作词并保留星号（如 * Y A W N * → * 哈欠 *）",
            "[特殊文本] TOSS TRASH / PRESS START 等全大写短语是动作/命令"
            "文本（含动作动词），每个词都须译成中文"
            "（如 TOSS TRASH → 丢垃圾、PRESS START → 按开始），"
            "不得保留任何英文单词；人名/地名等专名才保留原文",
        ]
        if self.store is not None:
            rows = self.store.list_by_domain("text")
            if limit > 0:
                rows = rows[-limit:]
            for row in rows:
                if not row["map_to"]:
                    continue
                lines.append(
                    f"[特殊文本] “{row['pattern']}”应译为“{row['map_to']}”"
                    f"（{row['kind']}）")
        return "\n".join(lines)

    # ── 学习：跑完一场后从「该翻未翻」条目沉淀 ──

    def learn(self, entries, source_game: str,
              names: set[str] | None = None) -> tuple[int, int]:
        """从「该翻未翻」回显条目（译文==原文）提取模式入库。

        两类都是真实漏翻证据：质量门通过但回显（曾被专名豁免的 TOSS
        TRASH）、质量门拒绝的 untranslated_text 回显（重试仍回显，模型
        惯性——taxes 实证 2 条）。纯专名回显（在专名清单/无动作词）
        不学习。返回 (新增条数, 命中数)。
        """
        if self.store is None:
            return 0, 0
        names = names or set()
        learned = hits = 0
        for e in entries:
            if not e.translation:
                continue
            rejected = set(e.meta.get("quality_reasons", ()))
            if e.translation == e.original:
                # 回显：质量门通过但回显（曾被专名豁免）或拒绝 → 都学
                if not (rejected & {"untranslated_text", "action_word_residue"}
                        or e.meta.get("quality_passed")):
                    continue
            else:
                # 非回显：仅 action_word_residue 拒绝（半翻译残留英文）
                # 学习——其余失败与知识库形态无关
                if "action_word_residue" not in rejected:
                    continue
            original = str(e.original)
            if not original.strip() or original in names:
                continue
            # 结构键/代码串/专名载体（§ 键码、路径、URL…）不是「该翻未翻」
            # 的可译文本——学习会污染知识库（butterflies 实证：§m_language_en
            # ### 的 en 是语言代码后缀，被罗曼功能词误判成 multilingual_source
            # 入库，反向把结构键送入翻译）
            if should_skip(original):
                continue
            if _is_spaced_action(original):
                learned += self.store.upsert(
                    "text", "spaced_action", original, action="translate",
                    note=f"auto:{source_game}:间隔动作词回显")
                hits += 1
            elif _is_uppercase_action(original):
                # map_to 由动作词表机械直译生成：重试降级（native_translate
                # 无 system prompt）时作为 references 译例带出，模型照做
                learned += self.store.upsert(
                    "text", "uppercase_action", original, action="translate",
                    map_to=translate_uppercase_action(original) or "",
                    note=f"auto:{source_game}:大写动作指令回显")
                hits += 1
            elif _is_multilingual_source(original):
                # 其他语言源回显（法语 Clé en Fer 等模型不认识）→ 沉淀形态
                # 规则；译例需人工沉淀或同对象译例机制（batch_translator
                # 的 _obj_reference_pairs），模型对完全回显无机械直译来源
                learned += self.store.upsert(
                    "text", "multilingual_source", original, action="translate",
                    note=f"auto:{source_game}:其他语言源文本回显（含假名/重音字母）")
                hits += 1
        return learned, hits

    def format_reference_pairs(self) -> list[tuple[str, str]]:
        """知识库译例对照（pattern → map_to），并入 glossary references。

        native_translate（Hy-MT2 官方单段 prompt）用 terms 机制注入——
        source 命中原文即带出 "TOSS TRASH translates to 丢垃圾"，重试时
        模型看到具体译例，而非只有抽象规则。
        """
        if self.store is None:
            return []
        pairs = []
        for row in self.store.list_by_domain("text"):
            if row["map_to"]:
                pairs.append((str(row["pattern"]), str(row["map_to"])))
        return pairs

    # ── fail_case 域：失败案例库（六库蓝图 2，FAIL 标准格式） ──

    _FAIL_TYPES = frozenset(
        {"提取", "识别", "分类", "翻译", "写回", "显示", "崩溃"})

    def record_case(self, *, game: str, fail_type: str, problem: str,
                    root_cause: str, fix: str, symptom: str = "",
                    impact: str = "", version: str = "",
                    environment: str = "Unity") -> bool:
        """失败案例入库（fail_case 域，FAIL-编号标准格式）。

        案例即「经验大脑」的长期积累：下次发现同类失败 → search_cases
        检索历史 → 复用已验证的修复方案，而非重新追查。
        fail_type ∈ 提取/识别/分类/翻译/写回/显示/崩溃。幂等（同问题
        同游戏不重复）。"""
        if self.store is None:
            return False
        if fail_type not in self._FAIL_TYPES:
            fail_type = "翻译"
        existing = self.store.list_by_domain("fail_case")
        number = len(existing) + 1
        note = (f"FAIL-{number:05d}|游戏:{game}|环境:{environment}|"
                f"问题:{problem}|现象:{symptom}|根因:{root_cause}|"
                f"解决:{fix}|影响范围:{impact}|修复版本:{version}|"
                f"失败类型:{fail_type}")
        return bool(self.store.upsert(
            "fail_case", fail_type, problem, action="apply_fix", note=note))

    def search_cases(self, fail_type: str | None = None,
                     keyword: str | None = None) -> list[dict]:
        """检索失败案例库：按失败类型和/或关键词过滤（案例检索复用）。"""
        if self.store is None:
            return []
        rows = self.store.list_by_domain("fail_case")
        if fail_type:
            rows = [r for r in rows if r["kind"] == fail_type]
        if keyword:
            k = keyword.casefold()
            rows = [r for r in rows
                    if k in r["pattern"].casefold()
                    or k in r["note"].casefold()]
        return rows

    # ── 全库视图（报告/文档/人工查阅） ──

    def describe(self) -> list[dict]:
        """种子 + 持久库合并视图（rule/file 域供报告与人工查阅）。"""
        return list(BUILTIN_RULES) + (self.store.list_all() if self.store else [])

    def close(self):
        if self.store is not None:
            self.store.close()
            self.store = None
