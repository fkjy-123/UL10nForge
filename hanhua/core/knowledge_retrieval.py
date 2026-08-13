# -*- coding: utf-8 -*-
"""KnowledgeRetrieval：知识检索统一门面（审计计划 Phase C，P1-1 修复）。

背景（P1-1）：ContextStore / VectorRecall / RerankGate 在 Phase B 已建成
并有测试，但生产入口（GUI translate_page 与 headless runner）创建
BatchTranslator 时未接线——知识组件只活在定义文件与测试里。本模块提供：

1. KnowledgeRetrieval —— 唯一装配门面。一个对象持有全部三个能力，
   暴露 context_store / vector_recall / rerank 子组件供 BatchTranslator
   注入（其消费点 645-725 直填、1515-1562 参考注入保持不变），并提供
   query() 组合检索给审核/风险策略等新消费方（P1-3 语境证据）。
2. outbox 增量索引 —— ContextStore 落库共识证据的同时写 vector_outbox
   （同事务，最终一致）；index_outbox() 消费 outbox → embed →
   add_batch → 标记 indexed=1。失败保留 outbox 下次重试，幂等
   （UNIQUE(source_text, fingerprint)，译文变化时归零重编）。
3. capability 报告 —— active / degraded / off + 原因（审计完成标准 5）：
   证明每条链路是否被生产装配/调用。

全部子组件可选注入：任何组件缺失/服务失败都只降级不阻断主路径
（与 batch_translator 既有容错语义一致）。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hanhua.core.context_library import _DIRECT_FILL_MIN_CONFIDENCE


# ── 证据 / 能力 ──

@dataclass(frozen=True)
class RetrievalEvidence:
    """一条检索证据。

    kind：
      context_exact   同游戏同指纹精确命中（confidence ≥ 门禁可直填）
      context_similar 跨游戏相似语境参考
      vector          向量相似召回参考
      rerank          经重排提升的参考（prob > 0 时标记）
    """
    kind: str
    source_text: str
    translation: str
    game: str = ""
    confidence: float = 0.0
    source: str = ""          # 证据来源（manual/review_confirm/…）
    similarity: float = 0.0   # 向量相似度
    verdict: str = ""         # 审核判定留档（PASS/MINOR/…）
    provenance: str = ""      # 人类可读来源说明
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalCapability:
    """capability 报告：三条链路 active/degraded/off + 原因。"""
    context: str = "off"
    vector: str = "off"
    rerank: str = "off"
    reasons: dict = field(default_factory=dict)

    def summary(self) -> str:
        """一行摘要：context=active vector=degraded(滞后3条) rerank=off"""
        parts = []
        for key in ("context", "vector", "rerank"):
            state = getattr(self, key)
            reason = self.reasons.get(key, "")
            if reason:
                parts.append(f"{key}={state}({reason})")
            else:
                parts.append(f"{key}={state}")
        return " ".join(parts)


# ── 统一门面 ──

class KnowledgeRetrieval:
    """Context + Vector + Rerank 的唯一装配/查询门面。

    用法（Composition Root）：
        kr = KnowledgeRetrieval(
            context_store=ContextStore(app_dir / "context.db"),
            vector_recall=VectorRecall(embed_service, vector_store, game=g),
            rerank=RerankGate(service=...),
            game=game_name)
        translator = BatchTranslator(
            client, ...,
            context_store=kr.context_store, context_game=game_name,
            vector_recall=kr.vector_recall)
        n = kr.index_outbox()          # 增量索引（可在翻译前/后调用）
        print(kr.capability().summary())  # 审计证明
    """

    def __init__(self, *, context_store=None, vector_recall=None,
                 rerank=None, embed_service=None, vector_store=None,
                 game: str = ""):
        self.context_store = context_store
        self.vector_recall = vector_recall
        self.rerank = rerank
        # index_outbox 需要直接操作 embed + store：优先显式注入，否则从
        # vector_recall 提取（其构造持有同实例，保证同一索引库）。
        self._embed = embed_service or (
            vector_recall.embed_service if vector_recall is not None
            else None)
        self._vector_store = vector_store or (
            vector_recall.vector_store if vector_recall is not None
            else None)
        self.game = game
        self._lock = threading.RLock()
        self._indexed_total = 0

    # ── 子组件暴露（BatchTranslator 注入点） ──

    @property
    def usable(self) -> bool:
        """任一能力可用即为 usable（供调用方快速判断是否值得接）。"""
        return (self.context_store is not None
                or self.vector_recall is not None
                or self.rerank is not None)

    # ── 组合查询（审核/风险策略消费：P1-3 语境证据） ──

    def query(self, source_text: str, *, game: str = "", scene: str = "",
              ui_position: str = "", text_type: str = "",
              ctx_before=(), ctx_after=(), top_k: int = 5,
              ) -> list[RetrievalEvidence]:
        """组合检索：语境精确 → 语境相似 → 向量召回 → 重排。

        返回 evidence 列表：context_exact 命中置首位（可直填候选），
        其余参考按相似度降序；rerank 服务可用时按重排概率排序并把
        提升项标为 kind=rerank。任何能力缺失/失败只跳过对应段。
        """
        game = game or self.game
        exact: RetrievalEvidence | None = None
        refs: list[RetrievalEvidence] = []

        # 1) 语境精确（同游戏同指纹）
        if self.context_store is not None:
            try:
                match = self.context_store.match_exact(
                    game, source_text, scene=scene, ui_position=ui_position,
                    text_type=text_type, ctx_before=ctx_before,
                    ctx_after=ctx_after)
            except Exception:  # noqa: BLE001 知识库故障不阻断检索
                match = None
            if match is not None and match.recommended_translation:
                can_fill = match.confidence >= _DIRECT_FILL_MIN_CONFIDENCE
                exact = RetrievalEvidence(
                    kind="context_exact",
                    source_text=match.source_text,
                    translation=match.recommended_translation,
                    game=match.game or "",
                    confidence=match.confidence,
                    source=match.source or "",
                    verdict=match.verdict or "",
                    provenance=("同游戏同指纹语境命中"
                                + ("" if can_fill else "（低于直填门禁，仅参考）")),
                )

        # 2) 语境相似（跨游戏参考）
        if self.context_store is not None:
            try:
                similar = self.context_store.match_similar(
                    game, source_text, scene=scene, ui_position=ui_position,
                    text_type=text_type, ctx_before=ctx_before,
                    ctx_after=ctx_after, limit=top_k)
            except Exception:  # noqa: BLE001
                similar = []
            for entry in similar:
                if not entry.recommended_translation:
                    continue
                refs.append(RetrievalEvidence(
                    kind="context_similar",
                    source_text=entry.source_text,
                    translation=entry.recommended_translation,
                    game=entry.game or "",
                    confidence=entry.confidence,
                    source=entry.source or "",
                    verdict=entry.verdict or "",
                    provenance="跨游戏相似语境参考",
                ))

        # 3) 向量召回（≥0.8，跨游戏）
        if self.vector_recall is not None:
            try:
                vec_hits = self.vector_recall.recall(
                    [source_text], limit=top_k)
            except Exception:  # noqa: BLE001
                vec_hits = []
            for hit in vec_hits:
                refs.append(RetrievalEvidence(
                    kind="vector",
                    source_text=str(hit.get("text", "")),
                    translation=str(hit.get("translation", "")),
                    similarity=float(hit.get("similarity", 0.0)),
                    provenance="向量相似召回参考",
                ))

        # 4) 重排：候选按 translation 去重（exact 不参与，已是最高优先级）
        if self.rerank is not None and refs:
            seen: set[tuple[str, str]] = set()
            unique: list[RetrievalEvidence] = []
            for ev in refs:
                key = (ev.source_text, ev.translation)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(ev)
            try:
                ranked = self.rerank.select_top(
                    source_text, unique, top_k=top_k)
            except Exception:  # noqa: BLE001
                ranked = [(ev, 0.0) for ev in unique[:top_k]]
            if ranked:
                refs = []
                for ev, prob in ranked:
                    if prob > 0.0:
                        refs.append(RetrievalEvidence(
                            kind="rerank",
                            source_text=ev.source_text,
                            translation=ev.translation,
                            game=ev.game,
                            confidence=ev.confidence,
                            similarity=prob,
                            # 保留来源链：向量命中被重排提升时仍可溯源
                            provenance=(
                                "向量召回·重排提升"
                                if ev.kind == "vector"
                                else "重排提升参考"),
                        ))
                    else:
                        refs.append(ev)
        else:
            refs.sort(key=lambda ev: ev.similarity, reverse=True)
            refs = refs[:top_k]

        return ([exact] if exact is not None else []) + refs

    # ── outbox 增量索引（最终一致） ──

    def outbox_pending(self) -> int:
        """未消费的 outbox 条数（capability 判定用）。"""
        if self.context_store is None:
            return 0
        return self.context_store.outbox_pending_count()

    def index_outbox(self, limit: int = 200) -> int:
        """消费 vector_outbox → 向量索引，返回本次新索引条数。

        embed 服务失败/未启动 → 保留 outbox 返回 0（下次重试，不丢证据）；
        上下文任何能力缺失 → 0（降级无副作用）。
        """
        if (self.context_store is None or self._embed is None
                or self._vector_store is None):
            return 0
        try:
            pending = self.context_store.fetch_outbox(limit=limit)
        except Exception:  # noqa: BLE001
            return 0
        if not pending:
            return 0
        texts = [str(r["source_text"]) for r in pending]
        try:
            vectors = self._embed.embed(texts)
        except Exception:  # noqa: BLE001 服务暂不可用：下次再编
            return 0
        rows = [
            {"obj_type": "context_entry", "obj_id": int(r["id"]),
             "text": str(r["source_text"]),
             "embedding": vec,
             "translation": str(r["translation"]),
             "game": str(r["game"] or "")}
            for r, vec in zip(pending, vectors)
            if vec
        ]
        if not rows:
            return 0
        with self._lock:
            added = self._vector_store.add_batch(rows)
            indexed_ids = [int(r["id"]) for r in pending]
            try:
                self.context_store.mark_outbox_indexed(indexed_ids)
            except Exception:  # noqa: BLE001 标记失败下次重编（幂等）
                pass
            self._indexed_total += added
        return added

    @property
    def indexed_total(self) -> int:
        """本实例累计索引条数（审计证明用）。"""
        return self._indexed_total

    # ── capability 报告 ──

    def capability(self) -> RetrievalCapability:
        reasons: dict[str, str] = {}

        # context：装配即 active（SQLite 本地库，无外部服务）
        if self.context_store is None:
            context_state = "off"
            reasons["context"] = "未装配 ContextStore"
        else:
            context_state = "active"

        # vector：装配 = embed + store 都就绪；outbox 有积压 → degraded
        if (self.vector_recall is None and self._embed is None
                and self._vector_store is None):
            vector_state = "off"
            reasons["vector"] = "未装配 VectorRecall/Embedding"
        else:
            pending = self.outbox_pending()
            if pending > 0:
                vector_state = "degraded"
                reasons["vector"] = f"{pending} 条 outbox 待索引（增量滞后）"
            else:
                vector_state = "active"
                if self.vector_recall is None:
                    reasons["vector"] = "装配（embed 直连）"

        # rerank：gate 装配且服务注入才 active；gate 服务为 None → 退化
        # 原序（select_top 内部退化），报告 off 并说明。
        if self.rerank is None:
            rerank_state = "off"
            reasons["rerank"] = "未装配 RerankGate"
        elif getattr(self.rerank, "service", None) is None:
            rerank_state = "off"
            reasons["rerank"] = "重排服务未启动（候选原序）"
        else:
            rerank_state = "active"

        return RetrievalCapability(
            context=context_state, vector=vector_state,
            rerank=rerank_state, reasons=reasons)


# ── 唯一 Composition Root ──

def create_knowledge_retrieval(app_dir: str | Path, *,
                               game: str = "",
                               context_store: Any | None = None,
                               vector_recall: Any | None = None,
                               rerank: Any | None = None,
                               embed_service: Any | None = None,
                               vector_store: Any | None = None,
                               service_dir: str | Path | None = None,
                               ) -> KnowledgeRetrieval:
    """生产接线工厂（GUI 与 headless runner 共用同一装配逻辑）。

    显式传入的组件优先（调用方已有实例时复用，保证同一库文件）；
    否则在 app_dir 下创建默认实现：
      - ContextStore：<app_dir>/context.db
      - VectorStore：<app_dir>/vector.db
      - EmbeddingService：service_dir 或 app_dir 状态文件（embed_runtime.json）
      - VectorRecall：以上两者 + game
      - RerankGate：默认不注入服务（off，候选原序退化）——embed/rerank
        服务统一由 Phase D RuntimeCoordinator 启动后替换注入。

    service_dir：模型服务定位目录（默认 app_dir，runner 场景一致）。
    GUI 必须传 resource_dir——模型（models/*.gguf）与状态文件在资源根，
    数据（context.db/vector.db）在 app_dir（~/.hanhua），两者分离。
    （修复：GUI 审核/嵌入/重排模型缺失 → TRANSPORT_ERROR 的根因。）

    返回 KnowledgeRetrieval（未调 context_store.init_schema 时补建表）。
    """
    app_dir = Path(app_dir)
    service_dir = Path(service_dir) if service_dir is not None else app_dir
    app_dir.mkdir(parents=True, exist_ok=True)
    if context_store is None:
        from hanhua.core.context_library import ContextStore
        context_store = ContextStore(app_dir / "context.db")
        context_store.init_schema()
    if vector_store is None:
        from hanhua.core.vector_store import VectorStore
        vector_store = VectorStore(app_dir / "vector.db")
        vector_store.init_schema()
    if embed_service is None:
        from hanhua.core.vector_store import EmbeddingService
        embed_service = EmbeddingService(service_dir)
    if vector_recall is None:
        from hanhua.core.vector_store import VectorRecall
        vector_recall = VectorRecall(
            embed_service, vector_store, game=game)
    if rerank is None:
        from hanhua.core.rerank_gate import RerankGate
        rerank = RerankGate(service=None, top_k=5, min_prob=0.15,
                            max_candidates=10)
    return KnowledgeRetrieval(
        context_store=context_store, vector_recall=vector_recall,
        rerank=rerank, embed_service=embed_service,
        vector_store=vector_store, game=game)
