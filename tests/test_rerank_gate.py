# -*- coding: utf-8 -*-
"""Reranker 语境匹配测试（任务一阶段 3）。

覆盖：softmax 归一化、排序正确性（Resume 样本选「继续」最高分）、
Top-3 封顶、无区分度阈值过滤（宁缺毋滥）、服务失败降级（不阻断）、
候选生成上限 20（T3-2）。服务为注入 fake，零真实模型调用。
"""
import pytest

from hanhua.core.context_library import ContextEntry, ContextStore
from hanhua.core.rerank_gate import (
    RerankGate,
    RerankService,
    generate_candidates,
    softmax_scores,
)


class _FakeRerank:
    """按文档原文返回预设 logits 的假 Reranker（index 与 documents 对齐）。"""

    def __init__(self, logits_by_text=None):
        self.logits_by_text = logits_by_text or {}
        self.calls = []

    def rerank(self, query, documents):
        self.calls.append((query, list(documents)))
        results = []
        for i, doc in enumerate(documents):
            results.append({"index": i, "relevance_score":
                            self.logits_by_text.get(doc, -10.0)})
        return results


# ── softmax ───────────────────────────────────────────────────────

def test_softmax_normalizes_to_probability():
    probs = softmax_scores([3.0, 1.0, 0.0])
    assert abs(sum(probs) - 1.0) < 1e-9
    assert probs[0] > probs[1] > probs[2]
    # logits 全相等 → 均分
    assert softmax_scores([-5.0, -5.0]) == [0.5, 0.5]
    assert softmax_scores([]) == []


# ── 排序正确性（T3-5 验收：Resume 样本「继续」最高分） ─────────────

def test_select_top_ranks_correct_translation_first():
    """Resume 主菜单语境：『继续』候选 logit 最高 → Top-1 是「继续」。"""
    fake = _FakeRerank({
        "Resume": 2.9e-06,          # 继续（主菜单）——最高
        "Continue the previous game": 8.2e-07,
        "简历（简历文档）": -3.1e-07,
        "恢复（健康恢复）": -1.4e-06,
    })
    gate = RerankGate(service=fake, top_k=3, min_prob=0.0)
    candidates = ["Resume", "Continue the previous game",
                  "简历（简历文档）", "恢复（健康恢复）"]
    ranked = gate.select_top("Resume", candidates)
    assert ranked[0][0] == "Resume"
    assert ranked[0][1] > ranked[1][1] > ranked[2][1]
    assert fake.calls[0][0] == "Resume"
    assert fake.calls[0][1] == candidates          # documents 对齐传入


def test_select_top_caps_at_top_k():
    fake = _FakeRerank({"a": 5.0, "b": 4.0, "c": 3.0, "d": 2.0, "e": 1.0})
    gate = RerankGate(service=fake, top_k=3, min_prob=0.0)
    ranked = gate.select_top("q", ["a", "b", "c", "d", "e"])
    assert len(ranked) == 3
    assert [c for c, _ in ranked] == ["a", "b", "c"]


def test_select_top_empty_when_no_discrimination():
    """logits 全相等（无区分度）→ 概率均分 → 低于阈值不注入（宁缺毋滥）。"""
    fake = _FakeRerank({"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0})
    gate = RerankGate(service=fake, top_k=3, min_prob=0.4)
    ranked = gate.select_top("q", ["a", "b", "c", "d"])
    assert ranked == []
    # 调低阈值 → 注入
    gate2 = RerankGate(service=fake, top_k=3, min_prob=0.1)
    assert len(gate2.select_top("q", ["a", "b", "c", "d"])) == 3


def test_select_top_degrades_on_service_failure():
    """服务调用失败 → 原序 Top-K（prob=0.0），不阻断翻译链。"""
    class _Broken:
        def rerank(self, query, documents):
            raise RuntimeError("服务挂了")

    gate = RerankGate(service=_Broken(), top_k=3, min_prob=0.0)
    ranked = gate.select_top("q", ["a", "b", "c", "d", "e"])
    assert [c for c, _ in ranked] == ["a", "b", "c"]


def test_select_top_without_service_keeps_order():
    gate = RerankGate(service=None, top_k=2, min_prob=0.0)
    assert gate.usable is False
    assert [c for c, _ in gate.select_top("q", ["x", "y", "z"])] == ["x", "y"]


def test_select_top_uses_context_entry_objects():
    """候选可为 ContextEntry 对象（source_text 提取文档）。"""
    entries = [
        ContextEntry(source_text="Resume", fingerprint="1"),
        ContextEntry(source_text="继续游戏", fingerprint="2"),
        ContextEntry(source_text="简历", fingerprint="3"),
    ]
    fake = _FakeRerank({"Resume": 3.0, "继续游戏": 1.0, "简历": -2.0})
    gate = RerankGate(service=fake, top_k=3, min_prob=0.0)
    ranked = gate.select_top("Resume", entries)
    assert ranked[0][0].source_text == "Resume"
    assert fake.calls[0][1] == ["Resume", "继续游戏", "简历"]


# ── 候选生成（T3-2，上限 20） ────────────────────────────────────

def test_generate_candidates_merges_and_dedups(tmp_path):
    store = ContextStore(tmp_path / "c.db")
    store.init_schema()
    store.seed()
    glossary = [("Resume", "继续"), ("Save", "保存")]
    knowledge = ["Load the latest save file"]
    cands = generate_candidates(
        "Resume", context_store=store, game="hickory",
        glossary_rows=glossary, knowledge_hits=knowledge, limit=20)
    assert len(cands) <= 20
    texts = [getattr(c, "source_text", str(c)) for c in cands]
    assert "Resume" in texts
    assert "Resume" not in [t for t in texts] or texts.count("Resume") == 1


def test_generate_candidates_caps_at_limit(tmp_path):
    store = ContextStore(tmp_path / "c2.db")
    store.init_schema()
    for i in range(30):
        store.add_entry(ContextEntry(
            source_text="cand 0", fingerprint=f"fp{i}",
            recommended_translation=f"译{i}", source="review_confirm",
            game=f"other{i}", evidence_count=1))
    cands = generate_candidates(
        "cand 0", context_store=store, game="g", limit=20)
    assert len(cands) == 20


# ── RerankService 单元（不启动真实服务） ─────────────────────────

def test_rerank_service_sig():
    """RerankService 结构与签名（构造参数、状态文件命名）。"""
    svc = RerankService("C:/tmp/app")
    assert svc._state_file.name == "rerank_runtime.json"
    assert svc.startup_timeout >= 10.0
