"""Embedding 向量检索（任务一阶段 4）。

统一知识检索层：相似文本去重、历史翻译检索、相似案例召回。零新增
第三方依赖——向量以 fp32 BLOB 存 SQLite（1024 维 × 4096 字节/条），
检索用纯 Python 余弦相似度（预归一化 → 点积即余弦，array('f') +
sum(map(mul, ...)) 约 50µs/条，千条候选 ~50ms，可接受）。

使用链（batch_translator 注入）：
- 相似去重（T4-3）：同游戏向量命中 ≥0.95 → 复用历史译文 + 质量门复查
- 相似召回（T4-4）：向量命中 ≥0.8 → 参考注入 prompt
- 记忆增强（T4-5）：先精确/子串（现有路径不变），再向量相似

服务管理（EmbeddingService）：独立 embed_runtime.json（端口 8083，
ctx 4096，固定 CPU，`--embeddings` 标志）。实测模型输出维度 **1024**
（Q8_0 实际维度，非预期 512——实现按 1024 设计，读响应长度自适应）。
"""
from __future__ import annotations

import array
import math
import operator
import sqlite3
import struct
import threading
from datetime import datetime
from pathlib import Path

import httpx

from .local_model import discover_server
from .model_registry import ModelRegistry, ModelSpec
from .runtime_coordinator import (
    build_effective_config,
    get_coordinator,
)

# 相似度阈值（T4-3/T4-4）
DEDUPE_SIMILARITY = 0.95      # ≥ 直接复用（质量门复查）
RECALL_SIMILARITY = 0.80      # ≥ 参考注入
SEARCH_TOP_K = 5


def _normalize(vec: list[float]) -> list[float]:
    """L2 归一化：归一化后点积 = 余弦相似度。"""
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0:
        return list(vec)
    return [v / norm for v in vec]


def _pack(embedding: list[float]) -> bytes:
    return struct.pack(f"<{len(embedding)}f", *embedding)


def _unpack(blob: bytes) -> array.array:
    return array.array("f", blob)


def _dot(a: array.array, b: array.array) -> float:
    """预归一化向量点积（= 余弦）。纯 Python 约 50µs/1024 维。"""
    return sum(map(operator.mul, a, b))


class EmbeddingService:
    """Embedding 本地服务：跨实例复用 + 按需启动（委托 RuntimeCoordinator）。

    审计 Phase D（P1-10）：进程管理统一到 RuntimeCoordinator 基座——
    authenticated probe、fixed_cpu 断言（gpu_layers 强制 0）、端口租约/
    清场、owned PID、TTL、取消清理全部走基座；本类保留对外 API
    （ensure_running/embed/release/stop）与 /v1/embeddings 调用。
    """

    def __init__(self, app_dir: str | Path, *,
                 process_factory=None, probe=None, sleep=None,
                 token_factory=None, startup_timeout: float = 180.0):
        self.app_dir = Path(app_dir).resolve()
        self.startup_timeout = max(10.0, float(startup_timeout))
        # 共享协调器：同 app_dir 复用端口租约/owned 进程；测试注入
        # process_factory/probe 走 get_coordinator 首建者生效
        self._coord = get_coordinator(
            self.app_dir, process_factory=process_factory, probe=probe,
            sleep=sleep, token_factory=token_factory,
            startup_timeout=startup_timeout)

    def _spec(self) -> ModelSpec:
        return ModelRegistry(self.app_dir).by_kind("embed")

    def ensure_running(self, cancellation_event=None,
                       context_size: int | None = None) -> dict:
        spec = self._spec()
        if not spec.is_available:
            raise RuntimeError(
                f"Embedding 模型缺失：{spec.path}"
                f"（models/ 目录无 Qwen3-Embedding-0.6B GGUF）")
        server = discover_server("", self.app_dir)
        cfg = build_effective_config(
            "embed", model_path=spec.path, server_path=server,
            ctx=context_size or spec.default_ctx, parallel=1,
            cache_reuse=512,
            extra_args=("--embeddings",) + spec.server_args,
            source="embed_service")
        return self._coord.acquire(cfg,
                                   cancellation_event=cancellation_event)

    # ── 嵌入 ─────────────────────────────────────────────────────
    def embed(self, texts: list[str], *, timeout: float = 120.0
              ) -> list[list[float]]:
        """真实调用 /v1/embeddings，返回逐文本向量（维度自适应，实测 1024）。"""
        info = self.ensure_running()
        resp = httpx.post(
            info["base_url"] + "/embeddings",
            headers={"Authorization": f"Bearer {info['api_key']}"},
            json={"model": "local", "input": list(texts)},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        by_index = {int(item.get("index", i)): item.get("embedding", [])
                    for i, item in enumerate(data)}
        return [by_index.get(i, []) for i in range(len(texts))]

    def release(self) -> None:
        """refcount-1；常驻（ttl=0）保留给后续实例复用（基座语义）。"""
        self._coord.release("embed")

    def stop(self) -> None:
        self._coord.stop("embed")


class VectorStore:
    """向量索引（SQLite：vector.db，跨项目共享）。零第三方依赖。"""

    def __init__(self, db_path: str | Path):
        self.db = Path(db_path)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.db), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self):
        with self._lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS vectors(
                id INTEGER PRIMARY KEY,
                obj_type TEXT NOT NULL,
                obj_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                translation TEXT NOT NULL DEFAULT '',
                embedding BLOB NOT NULL,
                game TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                UNIQUE(obj_type, obj_id, text)
            );
            CREATE INDEX IF NOT EXISTS idx_vec_type ON vectors(obj_type);
            CREATE INDEX IF NOT EXISTS idx_vec_game ON vectors(game);
            """)
            self.conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 写入 ──
    def add(self, obj_type: str, obj_id: int, text: str, embedding: list[float],
            *, translation: str = "", game: str = "") -> None:
        """索引一条（幂等：同 (obj_type, obj_id, text) 覆盖）。"""
        if not text or not embedding:
            return
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO vectors"
                "(obj_type, obj_id, text, translation, embedding, game,"
                " created_at) VALUES (?,?,?,?,?,?,?)",
                (obj_type, obj_id, text, translation, _pack(
                    _normalize(embedding)), game, self._now()))
            self.conn.commit()

    def add_batch(self, rows: list[dict]) -> int:
        """批量索引。rows: [{obj_type, obj_id, text, embedding, translation, game}]"""
        if not rows:
            return 0
        with self._lock:
            self.conn.executemany(
                "INSERT OR REPLACE INTO vectors"
                "(obj_type, obj_id, text, translation, embedding, game,"
                " created_at) VALUES (?,?,?,?,?,?,?)",
                [(r["obj_type"], r["obj_id"], r["text"], r.get("translation", ""),
                  _pack(_normalize(r["embedding"])), r.get("game", ""),
                  self._now()) for r in rows])
            self.conn.commit()
            return len(rows)

    def delete_by_obj(self, obj_type: str, obj_id: int) -> int:
        with self._lock:
            cur = self.conn.execute(
                "DELETE FROM vectors WHERE obj_type=? AND obj_id=?",
                (obj_type, obj_id))
            self.conn.commit()
            return cur.rowcount

    def clear(self) -> int:
        with self._lock:
            cur = self.conn.execute("DELETE FROM vectors")
            self.conn.commit()
            return cur.rowcount

    # ── 检索 ──
    def search(self, query_embedding: list[float], *,
               top_k: int = SEARCH_TOP_K, min_similarity: float = 0.0,
               game: str | None = None,
               obj_types: tuple[str, ...] | None = None,
               exclude_texts: tuple[str, ...] = ()) -> list[dict]:
        """余弦检索：返回 [{"id", "obj_type", "obj_id", "text", "translation",
        "game", "similarity"}] 按相似度降序（top_k 封顶）。

        预归一化存储 → 点积即余弦。全量线性扫描（千条 ~50ms）。
        """
        if not query_embedding:
            return []
        query = _normalize(query_embedding)
        q = array.array("f", query)
        exclude = set(exclude_texts or ())
        sql = "SELECT id, obj_type, obj_id, text, translation, game, embedding" \
              " FROM vectors"
        conds: list[str] = []
        params: list = []
        if game is not None:
            conds.append("game=?")
            params.append(game)
        if obj_types:
            conds.append("obj_type IN (%s)"
                         % ",".join("?" * len(obj_types)))
            params.extend(obj_types)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        with self._lock:
            rows = self.conn.execute(sql, params).fetchall()
        scored = []
        for row in rows:
            if row["text"] in exclude:
                continue
            try:
                sim = _dot(q, _unpack(row["embedding"]))
            except (ValueError, TypeError, struct.error):
                continue
            if sim >= min_similarity:
                scored.append({"id": row["id"], "obj_type": row["obj_type"],
                               "obj_id": row["obj_id"], "text": row["text"],
                               "translation": row["translation"],
                               "game": row["game"], "similarity": sim})
        scored.sort(key=lambda item: item["similarity"], reverse=True)
        return scored[:max(1, top_k)]

    def count(self) -> int:
        with self._lock:
            row = self.conn.execute("SELECT COUNT(*) c FROM vectors").fetchone()
            return row["c"] if row else 0

    def stats(self) -> dict:
        with self._lock:
            row = self.conn.execute(
                "SELECT obj_type, COUNT(*) c FROM vectors GROUP BY obj_type"
            ).fetchall()
            total = self.conn.execute("SELECT COUNT(*) c FROM vectors"
                                      ).fetchone()["c"]
        return {"total": total, "by_type": {r["obj_type"]: r["c"] for r in row}}

    def close(self):
        with self._lock:
            self.conn.close()


# ── 集成层（T4-3/T4-4/T4-5） ─────────────────────────────────────

class VectorRecall:
    """batch_translator 注入封装：相似去重 + 相似召回 + 记忆增强。

    用法：
        recall = VectorRecall(embed_service, vector_store, game="hickory")
        hits = recall.dedupe(entries, [原文...], exclude=exact_hits)
        refs = recall.recall([原文...], limit=3)
    服务不可用 → 空结果（不阻断翻译链，退化现有精确路径）。
    """

    def __init__(self, embed_service: EmbeddingService | None = None,
                 vector_store: VectorStore | None = None,
                 game: str = ""):
        self.embed_service = embed_service
        self.vector_store = vector_store
        self.game = game

    @property
    def usable(self) -> bool:
        return self.embed_service is not None and self.vector_store is not None

    def dedupe(self, originals: list[str], *, min_similarity: float
              = DEDUPE_SIMILARITY, exclude: tuple[str, ...] = ()) -> dict:
        """相似去重（T4-3）：同游戏向量命中 ≥0.95 → 复用历史译文。

        返回 {原文: 译文}（译文来自向量库 translation 列）。服务失败 →
        空 dict（现有精确路径不受影响）。译文复用仍需质量门复查（调用方）。
        """
        if not self.usable or not originals:
            return {}
        try:
            vectors = self.embed_service.embed(list(originals))
        except (httpx.HTTPError, RuntimeError, KeyError, TypeError,
                ValueError):
            return {}
        hits: dict[str, str] = {}
        for text, vec in zip(originals, vectors):
            if not vec:
                continue
            # 允许命中查询文本自身——「Are you sure?」重复出现数百次正是
            # 去重核心场景（首译入库后，后续出现直接复用）；exclude 仅由
            # 调用方控制（如精确命中已从 memory 路径拿走的原文）。
            results = self.vector_store.search(
                vec, top_k=1, min_similarity=min_similarity,
                game=self.game, exclude_texts=exclude)
            if results and results[0]["translation"]:
                hits[text] = results[0]["translation"]
        return hits

    def recall(self, originals: list[str], *, min_similarity: float
              = RECALL_SIMILARITY, limit: int = 3,
              exclude: tuple[str, ...] = ()) -> list[dict]:
        """相似召回（T4-4）：向量命中 ≥0.8 → 参考注入候选。

        返回 [{"text", "translation", "similarity"}] 按相似度降序 limit 封顶。
        """
        if not self.usable or not originals:
            return []
        try:
            vectors = self.embed_service.embed(list(originals))
        except (httpx.HTTPError, RuntimeError, KeyError, TypeError,
                ValueError):
            return []
        refs: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for text, vec in zip(originals, vectors):
            if not vec:
                continue
            for row in self.vector_store.search(
                    vec, top_k=limit, min_similarity=min_similarity,
                    game=None, exclude_texts=(*exclude, text)):
                key = (row["text"], row["translation"])
                if key in seen:
                    continue
                seen.add(key)
                refs.append({"text": row["text"],
                             "translation": row["translation"],
                             "similarity": row["similarity"]})
        refs.sort(key=lambda r: r["similarity"], reverse=True)
        return refs[:limit]
