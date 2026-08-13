# -*- coding: utf-8 -*-
"""KnowledgeRetrieval 统一门面测试（审计计划 Phase C，P1-1 修复）。

覆盖：
1. capability 报告 —— 未装配全 off；装配后 context/vector active；
   outbox 积压 → vector degraded（原因含条数）；rerank 无服务 → off
2. query 组合 —— context_exact 置首位；similar/vector 参考；rerank
   重排标记（prob>0 → kind=rerank；服务退化 → 原序）
3. outbox 增量索引 —— add_entry 共识自动入队 → index_outbox 消费 →
   向量可检索；embed 失败保留待重试；译文变化归零重编（最终一致）
4. Composition Root 工厂 —— 默认装配齐全、复用显式注入实例
5. BatchTranslator 注入 —— kr.context_store / kr.vector_recall 直填链

全部零真实模型调用：embed/rerank 用注入 fake。
"""
import math

import pytest

from hanhua.core.batch_translator import BatchTranslator
from hanhua.core.context_library import (
    ContextEntry,
    ContextStore,
    fingerprint_for,
)
from hanhua.core.knowledge_retrieval import (
    KnowledgeRetrieval,
    create_knowledge_retrieval,
)
from hanhua.core.models import TextEntry
from hanhua.core.rerank_gate import RerankGate
from hanhua.core.translator import BaseClient, Usage
from hanhua.core.vector_store import VectorRecall, VectorStore


class _FakeEmbed:
    """确定性假嵌入：同文本同向量，近义文本向量接近（阶段 4 同款）。"""

    def __init__(self, vectors=None, fail=False):
        self.vectors = vectors or {}
        self.fail = fail
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        if self.fail:
            raise RuntimeError("embed 服务不可用")
        out = []
        for t in texts:
            if t in self.vectors:
                out.append(self.vectors[t])
                continue
            out.append([math.sin((i + 1) * 7 + len(t) * 13)
                        for i in range(32)])
        return out


class _FakeRerankService:
    """假重排服务：文档与查询单词重叠多 → 高分。"""

    def __init__(self):
        self.calls = []

    def rerank(self, query, documents):
        self.calls.append((query, documents))
        q_words = set(str(query).casefold().split())
        out = []
        for i, doc in enumerate(documents):
            text = getattr(doc, "source_text", str(doc))
            overlap = len(q_words & set(text.casefold().split()))
            out.append({"index": i, "relevance_score": float(overlap)})
        return out


class _FakeClient(BaseClient):
    """模型假客户端：任何模型调用都抛错（知识直填应覆盖翻译链）。"""

    def __init__(self, mapping=None):
        self.mapping = mapping or {}

    def chat(self, system_prompt, messages):
        text = ""
        for msg in messages:
            text += str(msg.get("content", ""))
        for src, dst in self.mapping.items():
            if src in text:
                return dst, Usage(prompt_tokens=1, completion_tokens=1)
        raise AssertionError(f"模型不应被调用：{text[:80]}")


def _unit(dim=32, i=0):
    """单位向量（精确构造余弦相似度）。"""
    vec = [0.0] * dim
    vec[i % dim] = 1.0
    return vec


@pytest.fixture()
def kr(tmp_path):
    """完整装配：真实 ContextStore + 真实 VectorStore + fake embed/rerank。"""
    store = ContextStore(tmp_path / "context.db")
    store.init_schema()
    vstore = VectorStore(tmp_path / "vector.db")
    vstore.init_schema()
    embed = _FakeEmbed()
    recall = VectorRecall(embed, vstore, game="hickory")
    gate = RerankGate(service=_FakeRerankService(), top_k=5, min_prob=0.15,
                      max_candidates=10)
    return KnowledgeRetrieval(
        context_store=store, vector_recall=recall, rerank=gate,
        embed_service=embed, vector_store=vstore, game="hickory")


def _add_consensus(store, text, translation, *, game="hickory",
                   scene="main_menu", source="review_confirm"):
    """一条共识证据（真实语境指纹，match_exact 可命中）。"""
    return store.add_entry(ContextEntry(
        source_text=text,
        fingerprint=fingerprint_for(scene=scene, text_type=""),
        correct_meaning="",
        recommended_translation=translation, source=source, game=game,
        scene=scene, text_type="", evidence_count=2))


# ── capability 报告 ───────────────────────────────────────────────

def test_capability_all_off_when_unwired():
    kr = KnowledgeRetrieval()
    cap = kr.capability()
    assert cap.context == "off" and cap.vector == "off" and cap.rerank == "off"
    assert "未装配" in cap.reasons["context"]
    summary = cap.summary()
    assert "context=off" in summary and "rerank=off" in summary


def test_capability_vector_degraded_until_outbox_consumed(kr):
    # 有共识证据入队但未索引 → degraded（原因含条数）
    _add_consensus(kr.context_store, "Are you sure?", "你确定吗？")
    cap = kr.capability()
    assert cap.context == "active"
    assert cap.vector == "degraded"
    assert "待索引" in cap.reasons["vector"]
    assert cap.rerank == "active"
    # 消费后 → active
    assert kr.index_outbox() == 1
    cap2 = kr.capability()
    assert cap2.vector == "active"


def test_capability_rerank_off_without_service(tmp_path):
    store = ContextStore(tmp_path / "context.db")
    store.init_schema()
    gate = RerankGate(service=None, top_k=5, min_prob=0.15)
    kr = KnowledgeRetrieval(context_store=store, rerank=gate)
    cap = kr.capability()
    assert cap.rerank == "off"
    assert "未启动" in cap.reasons["rerank"]


# ── query 组合 ────────────────────────────────────────────────────

def test_query_exact_hit_first(kr):
    _add_consensus(kr.context_store, "Resume", "继续", source="manual")
    evs = kr.query("Resume", game="hickory", scene="main_menu")
    assert evs and evs[0].kind == "context_exact"
    assert evs[0].translation == "继续"
    assert evs[0].confidence >= 0.3            # manual → 1.0 可直填
    assert "命中" in evs[0].provenance


def test_query_similar_and_vector_refs(kr):
    # 语境参考：同原文不同语境（fingerprint 不同）→ match_similar 候选
    kr.context_store.add_entry(ContextEntry(
        source_text="Save the game",
        fingerprint=fingerprint_for(scene="dialog"),
        recommended_translation="保存游戏", source="review_confirm",
        game="other_game", scene="dialog"))
    # 向量参考：索引 "Load the game"，查询近义变体 "Load the game now?"
    # （recall 排除查询文本自身，注入同向向量构造相似命中）
    unit = _unit()
    kr._embed.vectors["Load the game"] = unit
    kr._embed.vectors["Load the game now?"] = unit
    _add_consensus(kr.context_store, "Load the game", "读取游戏")
    assert kr.index_outbox() == 2  # 两条共识证据都入队（Save/Load）
    evs = kr.query("Load the game now?", game="hickory", scene="main_menu")
    kinds = {ev.kind for ev in evs}
    assert kinds <= {"context_exact", "context_similar", "vector", "rerank"}
    assert any(ev.similarity > 0.0 for ev in evs)   # 向量召回命中（来源跳）
    # 向量命中经重排提升 → rerank 标记但保留向量来源链
    assert any(ev.kind == "rerank" and "向量" in ev.provenance
               for ev in evs)


def test_query_rerank_reorders_and_tags(kr):
    # 两条参考：一条含 query 关键词（rerank 高分），一条不含
    kr.context_store.add_entry(ContextEntry(
        source_text="Save the game", fingerprint="fp-a",
        recommended_translation="保存游戏", source="review_confirm",
        game="game_a"))
    kr.context_store.add_entry(ContextEntry(
        source_text="Nothing to do here", fingerprint="fp-b",
        recommended_translation="这里无事可做", source="review_confirm",
        game="game_b"))
    # 查询真实场景文本（match_similar 同原文命中两条参考）
    evs = kr.query("Save the game", game="hickory")
    # 与查询重叠多的参考被重排到首位并标记 rerank
    assert evs and evs[0].kind == "rerank"
    assert evs[0].source_text == "Save the game"


def test_query_rerank_degraded_keeps_original_order(tmp_path):
    """rerank 服务为 None → select_top 退化原序，kind 不标 rerank。"""
    store = ContextStore(tmp_path / "context.db")
    store.init_schema()
    store.add_entry(ContextEntry(
        source_text="Save the game", fingerprint="fp-a",
        recommended_translation="保存游戏", source="review_confirm",
        game="game_a"))
    gate = RerankGate(service=None, top_k=5, min_prob=0.15)
    kr = KnowledgeRetrieval(context_store=store, rerank=gate)
    evs = kr.query("Save the game", game="hickory")
    assert evs and evs[0].kind == "context_similar"
    assert "Save the game" == evs[0].source_text


# ── outbox 增量索引 ───────────────────────────────────────────────

def test_outbox_enqueued_on_consensus(kr):
    assert kr.outbox_pending() == 0
    _add_consensus(kr.context_store, "Are you sure?", "你确定吗？")
    assert kr.outbox_pending() == 1          # 落库即入队（同事务）


def test_outbox_not_enqueued_on_disagreement(kr):
    """分歧（多译文）不入队——suspicious 不向量化（防污染）。"""
    _add_consensus(kr.context_store, "Resume", "继续")
    kr.context_store.add_entry(ContextEntry(
        source_text="Resume",
        fingerprint=fingerprint_for(scene="main_menu", text_type=""),
        recommended_translation="简历", source="review_confirm",
        game="other_game"))
    assert kr.outbox_pending() == 1          # 共识证据已入队，分歧不新增
    assert kr.index_outbox() == 1


def test_index_outbox_roundtrip(kr):
    _add_consensus(kr.context_store, "Are you sure?", "你确定吗？")
    assert kr.index_outbox() == 1
    assert kr.outbox_pending() == 0
    assert kr.indexed_total == 1
    # 向量索引可检索（translation 保留）
    vectors = kr._embed.embed(["Are you sure?"])
    hits = kr._vector_store.search(vectors[0], top_k=5)
    assert hits and hits[0]["translation"] == "你确定吗？"


def test_index_outbox_embed_failure_keeps_pending(kr):
    kr._embed.fail = True
    _add_consensus(kr.context_store, "Are you sure?", "你确定吗？")
    assert kr.index_outbox() == 0            # 服务失败 → 不丢证据
    assert kr.outbox_pending() == 1          # 保留待重试
    kr._embed.fail = False
    assert kr.index_outbox() == 1            # 恢复后消费成功
    assert kr.outbox_pending() == 0


def test_outbox_reentry_idempotent_and_reindex_on_change(kr):
    """outbox 幂等：同指纹重复入队不新增行；译文变化归零重编。"""
    store = kr.context_store
    fp = fingerprint_for(scene="main_menu", text_type="")
    store._enqueue_outbox("Resume", fp, "继续", game="hickory")
    store._enqueue_outbox("Resume", fp, "继续", game="hickory")
    assert kr.outbox_pending() == 1          # 幂等：不重复入队
    assert kr.index_outbox() == 1
    assert kr.outbox_pending() == 0
    # 译文变化 → 同指纹行归零重编（最终一致）
    store._enqueue_outbox("Resume", fp, "恢复", game="hickory")
    assert kr.outbox_pending() == 1
    assert kr.index_outbox() == 1
    hits = kr._vector_store.search(kr._embed.embed(["Resume"])[0], top_k=5)
    assert hits and hits[0]["translation"] == "恢复"


def test_index_outbox_no_components_returns_zero():
    assert KnowledgeRetrieval().index_outbox() == 0
    assert KnowledgeRetrieval().outbox_pending() == 0


# ── Composition Root 工厂 ─────────────────────────────────────────

def test_create_factory_defaults(tmp_path):
    kr = create_knowledge_retrieval(tmp_path, game="hickory")
    assert kr.usable
    assert kr.context_store is not None
    assert kr.vector_recall is not None
    assert kr.vector_recall.game == "hickory"
    assert kr.rerank is not None
    cap = kr.capability()
    assert cap.context == "active"
    assert cap.rerank == "off"               # 默认不注入服务
    assert kr.index_outbox() == 0            # 空库无副作用


def test_create_factory_reuses_injected_instances(tmp_path):
    store = ContextStore(tmp_path / "custom.db")
    store.init_schema()
    kr = create_knowledge_retrieval(
        tmp_path, context_store=store, game="hickory")
    assert kr.context_store is store          # 显式注入复用，不重建


# ── BatchTranslator 注入（P1-1 修复验收） ──────────────────────────

def test_batch_translator_direct_fill_via_kr(kr):
    """kr 的子组件注入 BatchTranslator 后，精确命中直填不再调模型。"""
    _add_consensus(kr.context_store, "Are you sure?", "你确定吗？",
                   source="manual")
    kr.index_outbox()
    client = _FakeClient()
    bt = BatchTranslator(
        client, batch_size=2, concurrency=1,
        context_store=kr.context_store, context_game="hickory",
        vector_recall=kr.vector_recall)
    entry = TextEntry(
        file_id="f1", key_path="k1", original="Are you sure?",
        meta={"scene": "main_menu", "role": "", "kind": ""})
    stats = bt.run([entry])
    assert stats.done == 1
    assert stats.from_memory >= 1
    assert entry.translation == "你确定吗？"
