# -*- coding: utf-8 -*-
"""Embedding 向量检索测试（任务一阶段 4，T4-6）。

覆盖：L2 归一化存储、点积检索、相似去重（≥0.95 复用）、相似召回
（≥0.8 参考）、同游戏过滤、top_k 封顶、服务失败降级（不阻断）、
EmbeddingService 签名。Embedding 用注入 fake（确定性向量），零真实
模型调用；真实模型维度已在阶段 0 冒烟验证（1024）。
"""
import math

import pytest

from hanhua.core.translator import BaseClient, Usage
from hanhua.core.vector_store import (
    DEDUPE_SIMILARITY,
    EmbeddingService,
    RECALL_SIMILARITY,
    VectorRecall,
    VectorStore,
    _normalize,
)


class _FakeEmbed:
    """确定性假嵌入：按文本哈希生成 32 维向量（同文本同向量，近义近）。"""

    def __init__(self, vectors=None):
        self.vectors = vectors or {}
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        out = []
        for t in texts:
            if t in self.vectors:
                out.append(self.vectors[t])
                continue
            # 确定性伪随机向量（文本稳定）
            vec = [math.sin((i + 1) * 7 + len(t) * 13) for i in range(32)]
            out.append(vec)
        return out


def _unit(i, dim=32):
    """单位向量（第 i 维为 1）——可精确构造余弦相似度。"""
    vec = [0.0] * dim
    vec[i % dim] = 1.0
    return vec


@pytest.fixture()
def vstore(tmp_path):
    s = VectorStore(tmp_path / "vector.db")
    s.init_schema()
    return s


def test_normalize_unit_length():
    vec = [3.0, 4.0]
    norm = _normalize(vec)
    assert abs(math.sqrt(sum(v * v for v in norm)) - 1.0) < 1e-9
    assert _normalize([0.0, 0.0]) == [0.0, 0.0]


def test_add_and_search_cosine(vstore):
    """同向量命中 1.0，正交向量命中 0.0。"""
    vstore.add("memory", 1, "Save the game", _unit(0), translation="保存游戏",
               game="hickory")
    vstore.add("memory", 2, "Load the game", _unit(1), translation="读取游戏",
               game="hickory")
    results = vstore.search(_unit(0), top_k=5)
    assert results[0]["text"] == "Save the game"
    assert results[0]["similarity"] > 0.999
    assert results[0]["translation"] == "保存游戏"
    assert len(results) == 2           # 第二命中接近 0 也返回（min 默认 0）


def test_search_min_similarity_and_top_k(vstore):
    for i in range(10):
        vstore.add("text", i, f"text {i}", _unit(i), translation=f"译{i}",
                   game="g")
    results = vstore.search(_unit(0), top_k=3, min_similarity=0.5)
    assert len(results) == 1
    assert results[0]["obj_id"] == 0


def test_search_game_filter(vstore):
    vstore.add("memory", 1, "Save", _unit(0), translation="保存",
               game="hickory")
    vstore.add("memory", 2, "Save", _unit(0), translation="另存为",
               game="other")
    same = vstore.search(_unit(0), top_k=5, game="hickory")
    assert len(same) == 1 and same[0]["game"] == "hickory"
    all_games = vstore.search(_unit(0), top_k=5)
    assert len(all_games) == 2


def test_add_idempotent_and_delete(vstore):
    vstore.add("memory", 1, "Save", _unit(0), game="g")
    vstore.add("memory", 1, "Save", _unit(0), translation="保存", game="g")
    assert vstore.count() == 1
    assert vstore.delete_by_obj("memory", 1) == 1
    assert vstore.count() == 0


def test_add_batch(vstore):
    rows = [{"obj_type": "memory", "obj_id": i, "text": f"t{i}",
             "embedding": _unit(i), "translation": f"译{i}", "game": "g"}
            for i in range(5)]
    assert vstore.add_batch(rows) == 5
    assert vstore.count() == 5


# ── VectorRecall：去重/召回/降级（T4-3/T4-4） ─────────────────────

def test_dedupe_reuses_similar_translation(vstore):
    """同游戏 ≥0.95 命中 → 复用译文（含自身命中——重复文本去重核心场景）。"""
    embed = _FakeEmbed({"Are you sure?": _unit(0), "Different text": _unit(1)})
    vstore.add("memory", 1, "Are you sure?", _unit(0), translation="你确定吗？",
               game="hickory")
    recall = VectorRecall(embed, vstore, game="hickory")
    hits = recall.dedupe(["Are you sure?"])
    assert hits == {"Are you sure?": "你确定吗？"}
    # 低相似（正交向量）→ 不命中
    vstore.add("memory", 2, "Different text", _unit(1), translation="不同",
               game="hickory")
    hits2 = recall.dedupe(["Different text"])
    assert hits2 == {"Different text": "不同"}
    hits3 = recall.dedupe(["Save Game"])          # 库中无近邻 → 空
    assert hits3 == {}


def test_dedupe_other_game_not_used(vstore):
    vstore.add("memory", 1, "Save", _unit(0), translation="保存", game="other")
    recall = VectorRecall(_FakeEmbed(), vstore, game="hickory")
    assert recall.dedupe(["Save"]) == {}


def test_recall_injects_similar_references(vstore):
    """跨游戏 ≥0.8 命中 → 参考候选（Save→Load 相似召回）。"""
    embed = _FakeEmbed({"Save Game": _unit(0), "Load Game": _unit(0)})
    vstore.add("memory", 1, "Save the game.", _unit(0),
               translation="保存游戏。", game="hickory")
    vstore.add("memory", 2, "Load the game.", _unit(0),
               translation="读取游戏。", game="interdream")
    recall = VectorRecall(embed, vstore, game="hickory")
    refs = recall.recall(["Save Game"], limit=3)
    assert len(refs) == 2
    assert refs[0]["similarity"] >= RECALL_SIMILARITY
    assert any(r["translation"] == "保存游戏。" for r in refs)
    assert len(recall.recall(["Load Game"], limit=1)) == 1


def test_recall_degrades_without_service(vstore):
    recall = VectorRecall(None, vstore, game="g")
    assert recall.usable is False
    assert recall.dedupe(["x"]) == {}
    assert recall.recall(["x"]) == []


def test_recall_degrades_on_service_failure(vstore):
    class _BrokenEmbed:
        def embed(self, texts):
            raise RuntimeError("embed 服务挂了")

    vstore.add("memory", 1, "Save", _unit(0), translation="保存", game="g")
    recall = VectorRecall(_BrokenEmbed(), vstore, game="g")
    assert recall.dedupe(["Save"]) == {}
    assert recall.recall(["Save"]) == []


def test_dedupe_exclude_controlled_by_caller(vstore):
    """exclude 由调用方控制：默认允许自命中（去重核心）；显式排除则跳过。"""
    embed = _FakeEmbed({"Hello world": _unit(0)})
    vstore.add("memory", 1, "Hello world", _unit(0), translation="你好世界",
               game="g")
    vstore.add("memory", 2, "Hello world!", _unit(0), translation="你好世界！",
               game="g")
    recall = VectorRecall(embed, vstore, game="g")
    # 不排除 → 自命中（最高分是精确的自身记录）
    hits = recall.dedupe(["Hello world"])
    assert hits == {"Hello world": "你好世界"}
    # 显式排除自身 → 命中相似变体
    hits2 = recall.dedupe(["Hello world"], exclude=("Hello world",))
    assert hits2 == {"Hello world": "你好世界！"}


# ── EmbeddingService 单元 ─────────────────────────────────────────

def test_embed_service_sig():
    svc = EmbeddingService("C:/tmp/app")
    assert svc._state_file.name == "embed_runtime.json"
    assert svc.startup_timeout >= 10.0


# ── BatchTranslator 注入链（T4-3/T4-4 集成） ──────────────────────

class _NoCallClient(BaseClient):
    """断言模型零调用的假客户端。"""

    def __init__(self):
        self.calls = 0

    def chat(self, system, messages):
        self.calls += 1
        return "[]", Usage(1, 1)


def test_batch_vector_dedupe_fills_without_model(tmp_path, vstore):
    """向量去重直填：模型零调用，质量门复查通过。"""
    from hanhua.core.batch_translator import BatchTranslator
    from hanhua.core.models import TextEntry

    vstore.add("memory", 1, "Are you sure?", _unit(0), translation="你确定吗？",
               game="hickory")
    recall = VectorRecall(_FakeEmbed({"Are you sure?": _unit(0)}), vstore,
                          game="hickory")
    client = _NoCallClient()
    bt = BatchTranslator(client, batch_size=2, concurrency=1,
                         lang="en→zh-CN", vector_recall=recall)
    entry = TextEntry("f", "k", "Are you sure?", status="pending",
                      meta={"role": "display", "disposition": "translate",
                            "confidence": "high"})
    stats = bt.run([entry])
    assert client.calls == 0
    assert stats.done == 1 and stats.from_memory == 1
    assert entry.translation == "你确定吗？"


def test_batch_vector_reference_in_prompt(vstore):
    """向量相似召回注入 prompt 参考行（T4-4 集成）。"""
    from hanhua.core.batch_translator import BatchTranslator
    from hanhua.core.models import TextEntry

    vstore.add("memory", 1, "Save the game.", _unit(0), translation="保存游戏。",
               game="hickory")
    recall = VectorRecall(_FakeEmbed({"Save Game": _unit(0)}), vstore,
                          game="hickory")
    bt = BatchTranslator(_NoCallClient(), batch_size=2, concurrency=1,
                         lang="en→zh-CN", vector_recall=recall)
    entry = TextEntry("f", "k", "Save Game", status="pending",
                      meta={"role": "display", "disposition": "translate",
                            "confidence": "high"})
    user = bt._build_chat_user_prompt([
        bt._build_item([entry], 0, 0, single=True)])
    assert "相似参考：Save the game. → 保存游戏。" in user
