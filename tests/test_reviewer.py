"""语义审核器（reviewer.py）测试。

覆盖：批次 prompt 构造、无凭据降级、JSON 解析容错、
术语词对提取（知识库沉淀输入）。
"""

from unittest.mock import patch

from hanhua.core.reviewer import (ReviewConfig, ReviewItem, ReviewResult,
                                  SemanticReviewer, _build_batch_prompt,
                                  extract_term_pairs)


def _make_reviewer(api_key="sk-test"):
    return SemanticReviewer(ReviewConfig(
        base_url="https://api.deepseek.com/anthropic",
        api_key=api_key,
        model="deepseek-v4-flash",
    ))


def test_reviewer_unusable_without_credentials():
    """无凭据 → 审核不可用，review_batch 返回空（调用方按全部 pass）。"""
    reviewer = _make_reviewer(api_key="")
    assert reviewer.usable is False
    items = [ReviewItem(entry_id="1", original="Resume", translation="简历")]
    assert reviewer.review_batch(items) == {}


def test_build_batch_prompt_contains_all_fields():
    """批次 prompt 包含 id/类型/原文/译文，且 JSON 输出要求明确。"""
    items = [
        ReviewItem(entry_id="a1", original="Resume", translation="继续",
                   text_type="按钮"),
        ReviewItem(entry_id="b2", original="Hello", translation="你好"),
    ]
    prompt = _build_batch_prompt(items)
    assert "[id: a1]" in prompt
    assert "类型：按钮" in prompt
    assert "原文：Resume" in prompt
    assert "译文：继续" in prompt
    assert "[id: b2]" in prompt
    assert "输出 JSON 数组" in prompt
    assert "verdict" in prompt


def test_review_result_needs_optimization():
    """flag → needs_optimization=True；pass → False。"""
    assert ReviewResult("1", verdict="flag").needs_optimization is True
    assert ReviewResult("2").needs_optimization is False


def test_review_batch_parses_json_array():
    """API 返回 JSON 数组 → 解析为 ReviewResult 字典，未覆盖条目保守 pass。"""
    reviewer = _make_reviewer()
    items = [
        ReviewItem(entry_id="1", original="Resume", translation="简历",
                   text_type="按钮"),
        ReviewItem(entry_id="2", original="Start Game", translation="开始游戏",
                   text_type="按钮"),
        ReviewItem(entry_id="3", original="Hello", translation="你好"),
    ]
    fake_json = (
        '[{"id": "1", "verdict": "flag", "issue": "术语错误", '
        '"reason": "Resume 在 UI 语境是继续", "suggestion": "Resume→继续"},'
        '{"id": "2", "verdict": "pass", "issue": null, "reason": null, '
        '"suggestion": null}]'
    )
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "content": [{"type": "text", "text": fake_json}]}
        results = reviewer.review_batch(items)

    assert len(results) == 2
    assert results["1"].verdict == "flag"
    assert results["1"].issue == "术语错误"
    assert results["1"].suggestion == "Resume→继续"
    assert results["1"].needs_optimization is True
    assert results["2"].verdict == "pass"
    # 未覆盖条目（id=3）不在结果里——调用方按 pass 处理
    assert "3" not in results


def test_review_batch_handles_api_failure():
    """API 异常 → 返回空 dict（调用方按全部 pass 并告警，不阻断写回）。"""
    reviewer = _make_reviewer()
    items = [ReviewItem(entry_id="1", original="Hi", translation="你好")]
    with patch("requests.post", side_effect=Exception("network down")):
        assert reviewer.review_batch(items) == {}


def test_review_batch_respects_batch_size():
    """条目数超过 batch_size 时自动分批请求。"""
    reviewer = _make_reviewer()
    items = [ReviewItem(entry_id=str(i), original=f"word {i}",
                        translation=f"词 {i}") for i in range(5)]
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"content": []}
        reviewer.config.batch_size = 3
        reviewer.review_batch(items)
        assert mock_post.call_count == 2


def test_extract_term_pairs():
    """术语类 flag + 建议含英文原词与中文 → 提取词对（知识库沉淀）。"""
    results = [
        ReviewResult("1", verdict="flag", issue="术语错误",
                     suggestion="Resume→继续"),
        ReviewResult("2", verdict="flag", issue="术语错误",
                     suggestion="Resume→继续"),
        ReviewResult("3", verdict="flag", issue="语境不当",
                     suggestion="你好呀"),
        ReviewResult("4", verdict="pass"),
    ]
    pairs = extract_term_pairs(results)
    assert ("Resume", "继续") in pairs
    # 语境不当不是术语类 → 不入词对
    assert len(pairs) == 2
