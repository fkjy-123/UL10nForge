# -*- coding: utf-8 -*-
"""游戏语境库（任务一阶段 2）：多义词按「词义 + 语境」结构化消歧。

Resume/Save/Charge 类多义词（翻译 C6）：同一原文在不同语境（主菜单按钮
vs 剧情文本）词义不同——Resume 主菜单=继续、文档=简历。语境库为每个
(原文, 语境指纹) 记录正确词义与推荐译文，命中链：

- **同游戏同指纹精确命中** → 直填（译文过质量门复查）
- **跨游戏相似指纹** → 注入 prompt 参考（参考不强制，防跨游戏污染）
- 置信度 <0.3 只参考不直填（T2-6 证据门禁）

数据源加权（T2-6）：manual（人工标注，种子）> review_confirm（审核
PASS 沉淀）> memory_promote（翻译记忆晋升）。suspicious 标记（阶段 3
Reranker 高分但质量门失败）降级该条目，防污染。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path


# ── 多义词种子（T2-4）：10 词 × 5 种常见游戏语境，人工标注验证集 ──────
# 每词 5 条：主菜单/暂停菜单/战斗/设置/剧情对话（覆盖最常见的语境分歧）。
# source="manual" 置信度最高（1.0），作为验证集与种子数据。
_POLYSEMY_WORDS = ("Resume Save Load Charge Quit Options "
                   "Attack Guard Run Skill").split()

# (词, 语境scene, 原文, 词义说明, 推荐译文)
_POLYSEMY_SEED = [
    # Resume：继续（游戏流程）vs 恢复/简历（其他语境）
    ("Resume", "main_menu", "Resume", "继续游戏（主菜单按钮）", "继续"),
    ("Resume", "pause_menu", "Resume Game", "暂停菜单：继续游戏", "继续游戏"),
    ("Resume", "dialog", "Resume your journey", "剧情：重新踏上旅程", "继续你的旅程"),
    ("Resume", "settings", "Resume playback", "设置：恢复播放", "恢复播放"),
    ("Resume", "combat", "Resume combat", "战斗：恢复战斗", "恢复战斗"),
    # Save：保存（存档）vs 救（剧情）vs 保存更改（设置）
    ("Save", "main_menu", "Save", "存档（主菜单按钮）", "保存"),
    ("Save", "pause_menu", "Save Game", "暂停菜单：保存游戏", "保存游戏"),
    ("Save", "dialog", "Save her from danger", "剧情：拯救", "从危险中救出她"),
    ("Save", "settings", "Save changes", "设置：保存更改", "保存更改"),
    ("Save", "save_load", "Save your progress", "存档界面：保存进度", "保存进度"),
    # Load：读取（存档）vs 装载（货物）vs 装填（武器）
    ("Load", "main_menu", "Load", "读取存档（主菜单按钮）", "读取"),
    ("Load", "pause_menu", "Load Game", "暂停菜单：读取游戏", "读取游戏"),
    ("Load", "dialog", "Load the cargo", "剧情：装载货物", "装载货物"),
    ("Load", "combat", "Load weapon", "战斗：装填武器", "装填武器"),
    ("Load", "settings", "Load defaults", "设置：载入默认值", "载入默认值"),
    # Charge：蓄力/充能（战斗·道具）vs 冲锋（剧情）vs 充电/费用（设置）
    ("Charge", "combat", "Charge attack", "战斗：蓄力攻击", "蓄力攻击"),
    ("Charge", "inventory", "Charge the crystal", "道具：给水晶充能", "为水晶充能"),
    ("Charge", "dialog", "Charge into battle", "剧情：冲锋", "冲锋陷阵"),
    ("Charge", "settings", "Charge controller", "设置：手柄充电", "手柄充电"),
    ("Charge", "save_load", "Charge per day", "租借：每日费用", "每日费用"),
    # Quit：退出（程序/游戏）vs 离开（组织）vs 放弃（任务）
    ("Quit", "main_menu", "Quit", "退出游戏（主菜单按钮）", "退出"),
    ("Quit", "pause_menu", "Quit Game", "暂停菜单：退出游戏", "退出游戏"),
    ("Quit", "dialog", "Quit the guild", "剧情：退出公会", "退出公会"),
    ("Quit", "settings", "Quit without saving", "设置：不保存退出", "不保存退出"),
    ("Quit", "combat", "Quit mission", "战斗：放弃任务", "放弃任务"),
    # Options：选项（界面）vs 选择（剧情）
    ("Options", "main_menu", "Options", "设置入口（主菜单按钮）", "选项"),
    ("Options", "settings", "Game Options", "设置：游戏选项", "游戏选项"),
    ("Options", "dialog", "You have options", "剧情：你有选择", "你有选择"),
    ("Options", "combat", "Tactical options", "战斗：战术选择", "战术选择"),
    ("Options", "pause_menu", "Display options", "暂停菜单：显示选项", "显示选项"),
    # Attack：攻击（指令/属性）vs 攻打（剧情）
    ("Attack", "combat", "Attack", "战斗指令", "攻击"),
    ("Attack", "dialog", "Attack the castle", "剧情：攻打城堡", "攻打城堡"),
    ("Attack", "main_menu", "Attack mode", "模式选择：攻击模式", "攻击模式"),
    ("Attack", "settings", "Attack sensitivity", "设置：攻击灵敏度", "攻击灵敏度"),
    ("Attack", "inventory", "Attack power", "装备属性：攻击力", "攻击力"),
    # Guard：防御（指令）vs 护卫（剧情）vs 警戒（设置）
    ("Guard", "combat", "Guard", "战斗指令：防御", "防御"),
    ("Guard", "dialog", "Guard the princess", "剧情：护卫公主", "护卫公主"),
    ("Guard", "main_menu", "Guard duty", "任务：守卫职责", "守卫任务"),
    ("Guard", "inventory", "Iron guard", "装备：铁护手", "铁护手"),
    ("Guard", "settings", "Guard range", "设置：警戒范围", "警戒范围"),
    # Run：逃跑（战斗）vs 奔跑（移动/速度）vs 运行（程序）
    ("Run", "combat", "Run", "战斗指令：逃跑", "逃跑"),
    ("Run", "dialog", "Run away!", "剧情：快跑", "快跑！"),
    ("Run", "settings", "Run on startup", "设置：启动时运行", "启动时运行"),
    ("Run", "main_menu", "Run game", "启动器：运行游戏", "运行游戏"),
    ("Run", "inventory", "Run speed", "属性：奔跑速度", "奔跑速度"),
    # Skill：技能（游戏系统）vs 熟练度（设置）vs 技能（剧情泛称）
    ("Skill", "combat", "Skill", "战斗界面：技能", "技能"),
    ("Skill", "inventory", "Skill points", "成长：技能点", "技能点"),
    ("Skill", "dialog", "A valuable skill", "剧情：宝贵技艺", "一项宝贵技能"),
    ("Skill", "settings", "Skill level", "设置：熟练度", "熟练度"),
    ("Skill", "main_menu", "Skills", "主菜单：技能页", "技能"),
]


@dataclass
class ContextEntry:
    source_text: str
    fingerprint: str
    correct_meaning: str = ""
    recommended_translation: str = ""
    confidence: float = 0.5
    source: str = "manual"          # manual | review_confirm | memory_promote
    game: str = ""
    scene: str = ""
    ui_position: str = ""
    text_type: str = ""
    context_window: str = ""        # JSON：{"before": [...], "after": [...]}
    evidence_count: int = 1
    id: int | None = None
    suspicious: int = 0
    verdict: str = ""               # Phase B-4：证据的审核判定
                                    # （PASS/MINOR/manual 等，仅证据留档）

    @property
    def context_window_before(self) -> list[str]:
        return _ctx_window_list(self.context_window, "before")

    @property
    def context_window_after(self) -> list[str]:
        return _ctx_window_list(self.context_window, "after")


def fingerprint_for(*, scene: str = "", ui_position: str = "",
                    text_type: str = "", ctx_before=(),
                    ctx_after=()) -> str:
    """语境指纹：场景+UI位置+文本类型+相邻文本摘要的 sha1 前 12 位。

    不含原文——(source_text, fingerprint) 联合唯一：同原文出现在不同
    语境（Resume 按钮 vs Resume 剧情）是两条记录；不同原文同语境可聚簇。
    采集失败（无语境）时要素全空 → 指纹退化但恒定，不影响精确命中
    （主菜单按钮通常相邻文本也稳定）。
    """
    material = "|".join((
        scene or "", ui_position or "", text_type or "",
        ",".join(str(b)[:_CTX_MATERIAL_MAX] for b in (ctx_before or ())),
        ",".join(str(a)[:_CTX_MATERIAL_MAX] for a in (ctx_after or ())),
    ))
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]


_CTX_MATERIAL_MAX = 40

# 置信度证据加权（T2-6）：人工 > 审核 PASS > 记忆晋升
_SOURCE_CONFIDENCE = {
    "manual": 1.0,
    "review_confirm": 0.7,
    "memory_promote": 0.5,
}
_DIRECT_FILL_MIN_CONFIDENCE = 0.3   # 低于此只参考不直填


class ContextStore:
    """游戏语境库（SQLite：context.db，跨项目共享）。"""

    def __init__(self, db_path: str | Path):
        self.db = Path(db_path)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.db), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self):
        with self._lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS context_entries(
                id INTEGER PRIMARY KEY,
                source_text TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                correct_meaning TEXT,
                recommended_translation TEXT,
                confidence REAL DEFAULT 0.5,
                source TEXT,
                game TEXT,
                scene TEXT,
                UI_POSITION TEXT,
                text_type TEXT,
                context_window TEXT,
                evidence_count INTEGER DEFAULT 1,
                suspicious INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(source_text, fingerprint)
            );
            """)
            # 老库兼容：suspicious 列（阶段 3 Reranker 存疑标记）
            cols = {r["name"] for r in self.conn.execute(
                "PRAGMA table_info(context_entries)")}
            if "suspicious" not in cols:
                self.conn.execute(
                    "ALTER TABLE context_entries"
                    " ADD COLUMN suspicious INTEGER DEFAULT 0")
            # Phase B-4（审计 P1-2）：证据库——每条 (source_text,
            # fingerprint, game, translation) 一条证据，保留 game/来源/
            # 审核判定/译文；共识聚合才更新 canonical，分歧置 suspicious，
            # 重复同一游戏不算独立证据。
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS context_evidence(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                translation TEXT NOT NULL,
                meaning TEXT DEFAULT '',
                source TEXT DEFAULT '',
                game TEXT DEFAULT '',
                verdict TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ctx_evidence_lookup
                ON context_evidence(source_text, fingerprint);
            """)
            # 向量索引 outbox（审计 Phase C）：共识证据落库同事务写入，
            # index_outbox 消费 → embed → add_batch → indexed=1。数据库
            # 与向量索引最终一致：译文变化时归零重编（ON CONFLICT DO
            # UPDATE SET indexed=0），失败保留待重试（幂等）。
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS vector_outbox(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                translation TEXT NOT NULL,
                game TEXT DEFAULT '',
                meaning TEXT DEFAULT '',
                verdict TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                indexed INTEGER DEFAULT 0,
                indexed_at TEXT DEFAULT '',
                UNIQUE(source_text, fingerprint)
            );
            CREATE INDEX IF NOT EXISTS idx_vector_outbox_pending
                ON vector_outbox(indexed);
            """)
            self.conn.commit()

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 写入 ──

    def add_entry(self, entry: ContextEntry) -> bool:
        """入库（Phase B-4，审计 P1-2 重写）：证据 → 共识聚合 → canonical。

        旧实现：同 (source_text, fingerprint) 直接 evidence+1、confidence
        叠加、game 被最后写入覆盖——**相反译法被当作支持证据**（P1-2 审计
        问题：不同游戏给同一语境提供相反译法时，证据互相「支持」，谁
        最后写谁说了算）。现在：

          1. 先落一条 context_evidence（每条 (source_text, fingerprint,
             game, translation) 一条；同游戏同译文重复只刷新时间戳——
             重复同一游戏不能算独立证据）；
          2. 重新聚合 canonical（context_entries 作为物化视图，读路径
             match_exact/match_similar 不变）：
             - 全部证据译法一致 → active（可直填），置信度按来源加权 +
               独立游戏数增量；
             - 存在译法分歧 → suspicious=1（不直填、不参与参考），
               保留多数派译法（平局保留既有 canonical 译文）；
             - 分歧恢复唯一需要人工 clear_suspicious（保守：分歧一旦
               出现不自动翻盘，防证据漂移）。

        返回是否新增了证据行（幂等语义：同证据重复返回 False）。
        """
        now = self._now()
        with self._lock:
            created = self._add_evidence_row(entry, now)
            self._rebuild_canonical(entry.source_text, entry.fingerprint,
                                    now, entry)
            self.conn.commit()
        return created

    def add_evidence(self, *, source_text: str, fingerprint: str,
                     translation: str, meaning: str = "",
                     source: str = "review_confirm", game: str = "",
                     verdict: str = "", scene: str = "",
                     ui_position: str = "", text_type: str = "") -> bool:
        """显式证据写入（Phase B-4 公开 API，供审核/结算路径调用）。

        与 add_entry 同一聚合管线；verdict 记录审核判定（PASS/MINOR/
        manual 等）作为证据留档——只有二审 PASS / 人工确认才是高权重
        证据（审计 Phase B 完成标准）。"""
        return self.add_entry(ContextEntry(
            source_text=source_text, fingerprint=fingerprint,
            correct_meaning=meaning,
            recommended_translation=translation,
            source=source, game=game, scene=scene,
            ui_position=ui_position, text_type=text_type,
            verdict=verdict))

    def _add_evidence_row(self, entry: ContextEntry, now: str) -> bool:
        """落一条证据：同 (source_text, fingerprint, game, translation)
        已存在 → 只刷新时间戳（同游戏同译文重复不新增独立证据）。"""
        row = self.conn.execute(
            "SELECT id FROM context_evidence WHERE source_text=?"
            " AND fingerprint=? AND game=? AND translation=?",
            (entry.source_text, entry.fingerprint, entry.game or "",
             entry.recommended_translation)).fetchone()
        if row is not None:
            self.conn.execute(
                "UPDATE context_evidence SET created_at=? WHERE id=?",
                (now, row["id"]))
            return False
        self.conn.execute(
            "INSERT INTO context_evidence"
            "(source_text, fingerprint, translation, meaning, source,"
            " game, verdict, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (entry.source_text, entry.fingerprint,
             entry.recommended_translation, entry.correct_meaning,
             entry.source, entry.game or "", entry.verdict, now))
        return True

    def _rebuild_canonical(self, source_text: str, fingerprint: str,
                           now: str, entry: ContextEntry) -> None:
        """按全部证据重聚合 canonical（context_entries 物化行）。

        共识（唯一译法）→ active；分歧 → suspicious（保留多数派译法，
        平局保留既有译文）。game 列 = 最新证据来源游戏（证据历史在
        context_evidence，不再被覆盖丢失）。"""
        rows = self.conn.execute(
            "SELECT translation, game, source, meaning, created_at, id"
            " FROM context_evidence WHERE source_text=? AND fingerprint=?"
            " ORDER BY id", (source_text, fingerprint)).fetchall()
        if not rows:
            return
        # 按译法分桶：独立游戏集合 + 最佳来源
        buckets: dict[str, dict] = {}
        for r in rows:
            bucket = buckets.setdefault(
                str(r["translation"]),
                {"games": set(), "source": "", "meaning": ""})
            bucket["games"].add(r["game"] or "")
            weight = _SOURCE_CONFIDENCE.get(r["source"], 0.5)
            if weight > _SOURCE_CONFIDENCE.get(bucket["source"], 0.0):
                bucket["source"] = r["source"]
                bucket["meaning"] = r["meaning"] or ""
        independent = sum(len(b["games"]) for b in buckets.values())
        existing = self.conn.execute(
            "SELECT id, recommended_translation, game, scene, UI_POSITION,"
            " text_type, context_window FROM context_entries"
            " WHERE source_text=? AND fingerprint=?",
            (source_text, fingerprint)).fetchone()
        ctx_json = json.dumps(
            {"before": entry.context_window_before,
             "after": entry.context_window_after}, ensure_ascii=False)
        latest = rows[-1]
        if len(buckets) == 1:
            # 共识：唯一译法 → active
            trans, bucket = next(iter(buckets.items()))
            games = sorted(bucket["games"])
            base = _SOURCE_CONFIDENCE.get(bucket["source"], 0.5)
            confidence = min(1.0, base + len(games) * 0.05)
            if bucket["source"] == "manual":
                confidence = 1.0
            values = dict(
                correct_meaning=bucket["meaning"],
                recommended_translation=trans,
                confidence=confidence,
                source=bucket["source"],
                game=latest["game"] or "",
                evidence_count=len(games),
                suspicious=0,
                updated_at=now,
            )
            # 共识证据入向量 outbox（Phase C）：只有 consensus active 才有
            # 资格向量化；分歧（suspicious）不入队。与落库同事务——向量
            # 索引不可用也不丢证据，index_outbox 消费后最终一致。
            self._enqueue_outbox(
                source_text, fingerprint, trans,
                game=latest["game"] or "", meaning=bucket["meaning"],
                verdict=entry.verdict or "")
        else:
            # 分歧：置 suspicious——canonical 只在共识下更新（审计：
            # 「共识聚合才更新 canonical；分歧置 suspicious」），分歧时
            # 保留既有 canonical 译文不翻盘；无既有行时取多数派译法
            # 落一条 suspicious 行（可见、可人工 clear_suspicious）。
            majority = max(buckets.items(),
                           key=lambda kv: len(kv[1]["games"]))
            majority_trans, majority_bucket = majority
            if existing is not None:
                existing_trans = existing["recommended_translation"] or ""
                keep_trans = (existing_trans if existing_trans in buckets
                              else majority_trans)
                majority_bucket = (buckets[existing_trans]
                                   if existing_trans in buckets
                                   else majority_bucket)
            else:
                keep_trans = majority_trans
            confidence = min(
                1.0, _SOURCE_CONFIDENCE.get(majority_bucket["source"], 0.5))
            values = dict(
                correct_meaning=majority_bucket["meaning"],
                recommended_translation=keep_trans,
                confidence=confidence,
                source=majority_bucket["source"],
                game=(existing["game"] if existing is not None
                      else latest["game"] or ""),
                evidence_count=independent,
                suspicious=1,
                updated_at=now,
            )
        if existing is None:
            self.conn.execute(
                "INSERT INTO context_entries"
                "(source_text, fingerprint, correct_meaning,"
                " recommended_translation, confidence, source, game,"
                " scene, UI_POSITION, text_type, context_window,"
                " evidence_count, suspicious, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (source_text, fingerprint, values["correct_meaning"],
                 values["recommended_translation"], values["confidence"],
                 values["source"], values["game"], entry.scene,
                 entry.ui_position, entry.text_type, ctx_json,
                 values["evidence_count"], values["suspicious"],
                 now, now))
        else:
            self.conn.execute(
                "UPDATE context_entries SET correct_meaning=?,"
                " recommended_translation=?, confidence=?, source=?,"
                " game=?, evidence_count=?, suspicious=?, updated_at=?"
                " WHERE id=?",
                (values["correct_meaning"],
                 values["recommended_translation"], values["confidence"],
                 values["source"], values["game"],
                 values["evidence_count"], values["suspicious"], now,
                 existing["id"]))

    # ── 向量 outbox（Phase C：增量索引，最终一致） ──

    def _enqueue_outbox(self, source_text: str, fingerprint: str,
                        translation: str, *, game: str = "",
                        meaning: str = "", verdict: str = "") -> None:
        """共识证据入向量索引 outbox（幂等：指纹唯一，译文变化归零重编）。

        在 _rebuild_canonical 共识分支内调用（add_entry 同一事务）。
        ON CONFLICT DO UPDATE：同一 (source_text, fingerprint) 重复入队
        不新增行；译文变化时归零重编（indexed=0 再次消费）。"""
        with self._lock:
            self.conn.execute(
                "INSERT INTO vector_outbox"
                "(source_text, fingerprint, translation, game, meaning,"
                " verdict, indexed) VALUES (?,?,?,?,?,?,0)"
                " ON CONFLICT(source_text, fingerprint) DO UPDATE SET"
                " translation=excluded.translation,"
                " game=excluded.game, meaning=excluded.meaning,"
                " verdict=excluded.verdict, indexed=0, indexed_at=''",
                (source_text, fingerprint, translation, game, meaning,
                 verdict))
            self.conn.commit()

    def fetch_outbox(self, limit: int = 200) -> list:
        """取待索引行（indexed=0，按入队顺序）。"""
        with self._lock:
            return list(self.conn.execute(
                "SELECT * FROM vector_outbox WHERE indexed=0"
                " ORDER BY id LIMIT ?", (max(1, int(limit)),)))

    def mark_outbox_indexed(self, ids) -> None:
        """消费完成标记（幂等：重复标记无害，commit 统一提交）。"""
        ids = [int(i) for i in ids if int(i) > 0]
        if not ids:
            return
        with self._lock:
            self.conn.executemany(
                "UPDATE vector_outbox SET indexed=1, indexed_at=?"
                " WHERE id=?",
                [(self._now(), i) for i in ids])
            self.conn.commit()

    def outbox_pending_count(self) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM vector_outbox WHERE indexed=0"
            ).fetchone()
        return int(row["n"]) if row else 0

    def seed(self) -> int:
        """写入多义词种子（T2-4，幂等：已存在不覆盖）。返回新增数。"""
        added = 0
        for word, scene, text, meaning, trans in _POLYSEMY_SEED:
            entry = ContextEntry(
                source_text=text,
                fingerprint=fingerprint_for(scene=scene, text_type="种子"),
                correct_meaning=meaning,
                recommended_translation=trans,
                source="manual",
                game="seed",
                scene=scene,
                text_type="种子",
                evidence_count=5,
            )
            if self.add_entry(entry):
                added += 1
        return added

    # ── 命中链（T2-3） ──

    def match_exact(self, game: str, source_text: str, *,
                    scene: str = "", ui_position: str = "",
                    text_type: str = "", ctx_before=(),
                    ctx_after=()) -> ContextEntry | None:
        """同游戏同指纹精确命中 → 可直填（置信度 ≥ 门禁）。

        直填资格由 confidence >= _DIRECT_FILL_MIN_CONFIDENCE 判定（T2-6），
        调用方拿到后仍需过质量门复查。suspicious 条目不直填。

        Phase B-4（审计 P1-2）：跨游戏共识条目的直填资格由证据判定——
        canonical 行 game 列只是最新证据提示，本游戏是否参与共识看
        context_evidence 是否含该游戏证据（共识游戏均可直填）。
        """
        fp = fingerprint_for(scene=scene, ui_position=ui_position,
                             text_type=text_type, ctx_before=ctx_before,
                             ctx_after=ctx_after)
        with self._lock:
            row = self.conn.execute(
                "SELECT ce.* FROM context_entries ce"
                " WHERE ce.source_text=? AND ce.fingerprint=? AND ce.suspicious=0"
                " AND (ce.game=? OR EXISTS("
                "   SELECT 1 FROM context_evidence ev"
                "   WHERE ev.source_text=ce.source_text"
                "   AND ev.fingerprint=ce.fingerprint AND ev.game=?))"
                " ORDER BY ce.confidence DESC, ce.evidence_count DESC LIMIT 1",
                (source_text, fp, game, game)).fetchone()
        return self._to_entry(row) if row else None

    def match_similar(self, game: str, source_text: str, *,
                      scene: str = "", ui_position: str = "",
                      text_type: str = "", ctx_before=(),
                      ctx_after=(), limit: int = 10) -> list[ContextEntry]:
        """跨游戏相似候选 → 注入 prompt 参考（参考不强制）。

        候选来源（去重，排除同游戏精确命中）：
        1. 同指纹（跨游戏同语境）
        2. 同原文（同原文不同语境——供模型对比消歧）
        3. 多义词种子（原文含种子词）
        按 confidence DESC, evidence_count DESC 取 limit 条。
        """
        fp = fingerprint_for(scene=scene, ui_position=ui_position,
                             text_type=text_type, ctx_before=ctx_before,
                             ctx_after=ctx_after)
        words = [w for w in _POLYSEMY_WORDS
                 if w.casefold() in source_text.casefold()]
        results: list[ContextEntry] = []
        seen: set[int] = set()
        with self._lock:
            queries = [
                ("SELECT * FROM context_entries WHERE fingerprint=?"
                 " AND game!=? AND suspicious=0"
                 " ORDER BY confidence DESC, evidence_count DESC LIMIT ?",
                 (fp, game, limit)),
                ("SELECT * FROM context_entries WHERE source_text=?"
                 " AND suspicious=0 AND (game!=? OR game IS NULL)"
                 " ORDER BY confidence DESC, evidence_count DESC LIMIT ?",
                 (source_text, game, limit)),
            ]
            for sql, params in queries:
                for row in self.conn.execute(sql, params):
                    entry = self._to_entry(row)
                    if entry is None or entry.id in seen:
                        continue
                    # 排除同游戏精确命中（已有直填通道，不重复参考）。
                    # Phase B-4：共识条目按证据判定归属（游戏列只是提示）
                    if self._belongs_to_game(entry, game):
                        continue
                    seen.add(entry.id)
                    results.append(entry)
            for word in words:
                for row in self.conn.execute(
                        "SELECT * FROM context_entries WHERE source_text LIKE ?"
                        " AND suspicious=0 AND source='manual'"
                        " ORDER BY confidence DESC LIMIT ?",
                        (f"%{word}%", 3)):
                    entry = self._to_entry(row)
                    if entry is None or entry.id in seen:
                        continue
                    # 种子词查询缺 SQL 游戏排除：Python 侧统一过滤
                    if self._belongs_to_game(entry, game):
                        continue
                    seen.add(entry.id)
                    results.append(entry)
        return results[:limit]

    def _belongs_to_game(self, entry: ContextEntry, game: str) -> bool:
        """条目是否属于该游戏（可直填）：游戏列命中或证据含该游戏。"""
        if entry.game == game:
            return True
        if not game:
            return False
        with self._lock:
            return self.conn.execute(
                "SELECT 1 FROM context_evidence"
                " WHERE source_text=? AND fingerprint=? AND game=? LIMIT 1",
                (entry.source_text, entry.fingerprint, game)).fetchone() \
                is not None

    # ── 存疑标记（阶段 3 T3-4） ──

    def mark_suspicious(self, entry_id: int) -> None:
        """Reranker 高分但质量门失败 → 标记存疑（防污染）。"""
        with self._lock:
            self.conn.execute(
                "UPDATE context_entries SET suspicious=1, updated_at=?"
                " WHERE id=?", (self._now(), entry_id))
            self.conn.commit()

    def clear_suspicious(self, entry_id: int | None = None) -> int:
        with self._lock:
            if entry_id is None:
                cur = self.conn.execute(
                    "UPDATE context_entries SET suspicious=0")
            else:
                cur = self.conn.execute(
                    "UPDATE context_entries SET suspicious=0 WHERE id=?",
                    (entry_id,))
            self.conn.commit()
            return cur.rowcount

    # ── 查询 ──

    def get(self, entry_id: int) -> ContextEntry | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM context_entries WHERE id=?",
                (entry_id,)).fetchone()
        return self._to_entry(row) if row else None

    def list_all(self, suspicious: int | None = None) -> list[ContextEntry]:
        sql = "SELECT * FROM context_entries"
        params: tuple = ()
        if suspicious is not None:
            sql += " WHERE suspicious=?"
            params = (suspicious,)
        sql += " ORDER BY confidence DESC, evidence_count DESC"
        with self._lock:
            return [self._to_entry(r) for r in
                    self.conn.execute(sql, params) if r]

    def list_evidence(self, source_text: str | None = None,
                      fingerprint: str | None = None) -> list[dict]:
        """证据明细（Phase B-4 可观测性：每条证据的 game/来源/判定/译文）。"""
        sql = "SELECT * FROM context_evidence"
        clauses, params = [], []
        if source_text is not None:
            clauses.append("source_text=?")
            params.append(source_text)
        if fingerprint is not None:
            clauses.append("fingerprint=?")
            params.append(fingerprint)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id"
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params)]

    def stats(self) -> dict:
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) c, SUM(evidence_count) ev,"
                " SUM(suspicious) sus FROM context_entries").fetchone()
            by_source = {r["source"]: r["c"] for r in self.conn.execute(
                "SELECT source, COUNT(*) c FROM context_entries"
                " GROUP BY source")}
            ev_row = self.conn.execute(
                "SELECT COUNT(*) c FROM context_evidence").fetchone()
        return {"entries": row["c"] or 0,
                "evidence_total": row["ev"] or 0,
                "suspicious": row["sus"] or 0,
                "by_source": by_source,
                "evidence_rows": ev_row["c"] or 0}

    @staticmethod
    def _to_entry(row: sqlite3.Row | None) -> ContextEntry | None:
        if row is None:
            return None
        ctx = {}
        try:
            ctx = json.loads(row["context_window"] or "{}")
        except (json.JSONDecodeError, TypeError, ValueError):
            ctx = {}
        return ContextEntry(
            id=row["id"],
            source_text=row["source_text"],
            fingerprint=row["fingerprint"],
            correct_meaning=row["correct_meaning"] or "",
            recommended_translation=row["recommended_translation"] or "",
            confidence=row["confidence"] or 0.0,
            source=row["source"] or "",
            game=row["game"] or "",
            scene=row["scene"] or "",
            ui_position=row["UI_POSITION"] or "",
            text_type=row["text_type"] or "",
            context_window=row["context_window"] or "",
            evidence_count=row["evidence_count"] or 1,
            suspicious=row["suspicious"] or 0,
        )

    # ── 格式化（注入 prompt） ──

    def format_reference(self, entry: ContextEntry) -> str:
        """单条参考行（注入 prompt 用，带语境与来源防污染）。"""
        parts = [f"{entry.source_text} → {entry.recommended_translation}"]
        if entry.correct_meaning:
            parts.append(f"（词义：{entry.correct_meaning}")
            if entry.scene:
                parts.append(f"·语境：{entry.scene}")
            parts.append(f"·来源：{entry.game or 'seed'}）")
        return " ".join(parts)

    def close(self):
        with self._lock:
            self.conn.close()


def _ctx_window_list(raw: str, key: str) -> list[str]:
    try:
        data = json.loads(raw or "{}")
        return [str(x) for x in data.get(key, [])]
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return []


def collect_window(entry_meta: dict) -> tuple[list[str], list[str]]:
    """从 TextEntry.meta 提取 ctx_before/ctx_after（提取器 T2-1 采集）。"""
    return ([str(x) for x in entry_meta.get("ctx_before", [])],
            [str(x) for x in entry_meta.get("ctx_after", [])])
