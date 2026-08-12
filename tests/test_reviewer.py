"""语义审核器（reviewer.py）测试（2026-08-13 本地四级化后重写）。

覆盖：本地 4B 逐条审核调用、JSON 解析容错、无服务失败降级、
四级构造兼容（旧二值 verdict 映射）、术语词对提取（沉淀输入）。

注：原测试测云端 API（requests.post 到 api.deepseek.com）——云端
审核已按执行指令从代码删除，测试同步改为本地 llama.cpp 服务语义
（服务实例注入 fake，不真实启动）。
"""

from hanhua.core.reviewer import (ReviewItem, ReviewResult, SemanticReviewer,
                                  _build_item_prompt, extract_term_pairs)


class _FakeService:
    """假的本地审核服务：按输入返回预设 content。"""

    def __init__(self, outputs=None, error=None):
        self.outputs = list(outputs or [])
        self.error = error
        self.prompts = []

    def chat(self, prompt, *, max_tokens=1024, temperature=0.1,
             timeout=120.0):
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.outputs.pop(0) if len(self.outputs) > 1 \
            else self.outputs[0]

    @property
    def usable(self) -> bool:
        return True


def _make_reviewer(service=None):
    return SemanticReviewer(service=service or _FakeService(
        outputs=['{"level": "PASS", "reason": "正确"}']))


def test_reviewer_usable_with_service():
    reviewer = _make_reviewer()
    assert reviewer.usable is True


def test_build_item_prompt_contains_all_fields():
    """单条 prompt 包含类型/原文/译文与四级定义与 JSON 要求。"""
    item = ReviewItem(entry_id="a1", original="Resume", translation="继续",
                      text_type="按钮")
    prompt = _build_item_prompt(item)
    assert "类型：按钮" in prompt
    assert "原文：Resume" in prompt
    assert "译文：继续" in prompt
    assert "PASS|MINOR|MAJOR|CRITICAL" in prompt
    assert "resume" in prompt.casefold()


def test_review_result_needs_optimization():
    """flag（旧二值）→ needs_optimization=True（映射 MAJOR）；pass → False。"""
    assert ReviewResult("1", verdict="flag").needs_optimization is True
    assert ReviewResult("1", verdict="flag").level == "MAJOR"
    assert ReviewResult("2").needs_optimization is False
    assert ReviewResult("3", level="CRITICAL").needs_optimization is True
    assert ReviewResult("4", level="MINOR").needs_optimization is False


def test_review_batch_parses_level_json():
    """本地服务返回四级 JSON → 解析为 ReviewResult；未覆盖条目保守缺失。"""
    service = _FakeService(outputs=[
        '{"level": "CRITICAL", "reason": "Resume 在 UI 语境是继续", '
        '"issues": [{"type": "术语错误", "detail": "简历误译", '
        '"suggestion": "继续"}]}',
        '{"level": "PASS", "reason": "正确"}',
    ])
    reviewer = _make_reviewer(service)
    items = [
        ReviewItem(entry_id="1", original="Resume", translation="简历",
                   text_type="按钮"),
        ReviewItem(entry_id="2", original="Start Game", translation="开始游戏",
                   text_type="按钮"),
    ]
    results = reviewer.review_batch(items)
    assert len(results) == 2
    assert results["1"].level == "CRITICAL"
    assert results["1"].issue == "术语错误"
    assert results["1"].suggestion == "继续"
    assert results["1"].needs_optimization is True
    assert results["2"].level == "PASS"
    assert results["2"].needs_optimization is False
    assert service.prompts[0].startswith("你是游戏本地化质量审核员")


def test_review_batch_handles_service_failure():
    """服务异常 → 返回空 dict（调用方按全部 pass 并告警，不阻断写回）。"""
    reviewer = _make_reviewer(_FakeService(error=RuntimeError("网络故障")))
    items = [ReviewItem(entry_id="1", original="Hi", translation="你好")]
    assert reviewer.review_batch(items) == {}


def test_review_batch_handles_non_json_output():
    """服务返回非 JSON → 兜底 PASS（reviewed=False，reason 留原文备查）。"""
    reviewer = _make_reviewer(_FakeService(outputs=["一段普通文本"]))
    items = [ReviewItem(entry_id="1", original="Hi", translation="你好")]
    results = reviewer.review_batch(items)
    assert len(results) == 1
    assert results["1"].level == "PASS"
    assert results["1"].reviewed is False


def test_extract_term_pairs():
    """术语类 flag + 建议含英文原词与中文 → 提取词对（知识库沉淀）。"""
    results = [
        ReviewResult("1", level="MAJOR", issue="术语错误",
                     suggestion="Resume→继续"),
        ReviewResult("2", level="CRITICAL", issue="术语错误",
                     suggestion="Resume→继续"),
        ReviewResult("3", level="MAJOR", issue="语境不当",
                     suggestion="你好呀"),
        ReviewResult("4", level="PASS"),
    ]
    pairs = extract_term_pairs(results)
    assert ("Resume", "继续") in pairs
    # 语境不当不是术语类 → 不入词对
    assert len(pairs) == 2
