"""语义审核器（reviewer.py）测试（2026-08-13 本地四级化后重写）。

覆盖：本地 4B 逐条审核调用、JSON 解析容错、无服务失败降级、
四级构造兼容（旧二值 verdict 映射）、术语词对提取（沉淀输入）。

注：原测试测云端 API（requests.post 到 api.deepseek.com）——云端
审核已按执行指令从代码删除，测试同步改为本地 llama.cpp 服务语义
（服务实例注入 fake，不真实启动）。
"""

from hanhua.core.reviewer import (ReviewItem, ReviewResult, SemanticReviewer,
                                  _REVIEW_SYSTEM_PROMPT, _build_item_prompt,
                                  _parse_result, extract_term_pairs)


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
    results, cancelled = reviewer.review_batch(items)
    assert cancelled == 0
    assert len(results) == 2
    assert results["1"].level == "CRITICAL"
    assert results["1"].issue == "术语错误"
    assert results["1"].suggestion == "继续"
    assert results["1"].needs_optimization is True
    assert results["2"].level == "PASS"
    assert results["2"].needs_optimization is False
    assert service.prompts[0].startswith("你是游戏本地化质量审核员")


def test_review_batch_handles_service_failure():
    """服务异常 → 显式 TRANSPORT_ERROR 错误结果（fail-closed，不伪装 pass）。"""
    reviewer = _make_reviewer(_FakeService(error=RuntimeError("网络故障")))
    items = [ReviewItem(entry_id="1", original="Hi", translation="你好")]
    results, cancelled = reviewer.review_batch(items)
    assert cancelled == 0
    assert len(results) == 1
    assert results["1"].is_error
    assert results["1"].error == "TRANSPORT_ERROR"
    assert results["1"].reviewed is False


def test_review_batch_handles_non_json_output():
    """服务返回非 JSON → 显式 PARSE_ERROR（不得伪装成「没有发现问题」）。"""
    reviewer = _make_reviewer(_FakeService(outputs=["一段普通文本"]))
    items = [ReviewItem(entry_id="1", original="Hi", translation="你好")]
    results, cancelled = reviewer.review_batch(items)
    assert cancelled == 0
    assert len(results) == 1
    assert results["1"].is_error
    assert results["1"].error == "PARSE_ERROR"
    assert results["1"].reviewed is False


def test_review_batch_cancellation_returns_cancelled_count():
    """取消事件触发 → 剩余条目计入 cancelled_count（取消是显式终态，
    不得归入 error 或 pass）。"""
    import threading
    reviewer = _make_reviewer(_FakeService(
        outputs=['{"level": "PASS", "reason": "正确"}']))
    items = [ReviewItem(entry_id=str(i), original=f"text{i}",
                        translation=f"译文{i}") for i in range(5)]
    evt = threading.Event()
    evt.set()   # 预先置位 → 整批都应计入 cancelled
    results, cancelled = reviewer.review_batch(items, cancellation_event=evt)
    assert cancelled == len(items)
    assert results == {}


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


# ── #43 阶段 E：十维审校（重构指令 §10 / §16 知识优先级链） ─────────

def test_system_prompt_has_ten_dimensions():
    """审核系统 prompt 含十维（含幻觉/自然度/歧义/机翻痕迹）。"""
    for dim in ("语义准确", "游戏语境", "术语一致", "自然度", "风格",
                "完整性", "幻觉", "结构完整", "歧义", "机翻痕迹"):
        assert dim in _REVIEW_SYSTEM_PROMPT
    assert "overall_score" in _REVIEW_SYSTEM_PROMPT   # JSON 契约扩展
    assert "dimensions" in _REVIEW_SYSTEM_PROMPT


def test_parse_result_ten_dimension_fields():
    """十维 JSON（overall_score + dimensions）→ ReviewResult 新字段。"""
    r = _parse_result(
        '{"level": "MAJOR", "overall_score": 62, '
        '"dimensions": {"语义准确": 90, "自然度": 55, "术语一致": 80}, '
        '"reason": "翻译腔重", '
        '"issues": [{"type": "机翻痕迹", "detail": "语序直译", '
        '"suggestion": "地道表达"}]}', "e0")
    assert r.overall_score == 62
    assert r.dimensions == {"语义准确": 90, "自然度": 55, "术语一致": 80}
    assert r.level == "MAJOR"
    assert r.issue == "机翻痕迹"


def test_parse_result_legacy_json_compat():
    """旧模型输出（无新字段）→ overall_score=0 / dimensions={}（零破坏）。"""
    r = _parse_result('{"level": "PASS", "reason": "正确"}', "e0")
    assert r.overall_score == 0
    assert r.dimensions == {}
    assert r.level == "PASS"


def test_parse_result_score_clamped_and_bad_types_ignored():
    """越界分截断 0-100；非数值/非 dict 类型安全忽略。"""
    r = _parse_result(
        '{"level": "PASS", "overall_score": 250, "dimensions": {"a": "x"}}',
        "e0")
    assert r.overall_score == 100
    assert r.dimensions == {}
    r2 = _parse_result('{"level": "PASS", "overall_score": "高"}', "e0")
    assert r2.overall_score == 0


def test_review_result_dimension_defaults():
    """ReviewResult 默认 overall_score=0 / dimensions={}（构造兼容）。"""
    r = ReviewResult("1", level="PASS")
    assert r.overall_score == 0
    assert r.dimensions == {}


def test_build_item_prompt_injects_hints():
    """术语参考 + 语境参考注入 prompt；旧调用（无 hint）不注入。"""
    item = ReviewItem(entry_id="a1", original="Resume", translation="继续",
                      text_type="按钮", term_hint="Resume=继续；Save=保存",
                      context_hint="「继续」(context_exact, 置信 0.90)")
    prompt = _build_item_prompt(item)
    assert "术语参考：Resume=继续；Save=保存" in prompt
    assert "语境参考：「继续」(context_exact, 置信 0.90)" in prompt
    legacy = _build_item_prompt(ReviewItem(
        entry_id="a2", original="Hi", translation="你好"))
    # 系统 prompt 维度 3 提到「术语参考/语境参考」字样，注入形态以冒号区分
    assert "术语参考：" not in legacy
    assert "语境参考：" not in legacy


def test_review_batch_ten_dimension_end_to_end():
    """端到端：十维 JSON 输出 → 评分/维度随结果透出。"""
    service = _FakeService(outputs=[
        '{"level": "MINOR", "overall_score": 88, '
        '"dimensions": {"语义准确": 95, "自然度": 80}, '
        '"reason": "略有翻译腔"}'])
    reviewer = _make_reviewer(service)
    items = [ReviewItem(entry_id="1", original="Resume", translation="继续",
                        text_type="按钮", term_hint="Resume=继续")]
    results, cancelled = reviewer.review_batch(items)
    assert cancelled == 0
    assert results["1"].overall_score == 88
    assert results["1"].dimensions["自然度"] == 80
    assert results["1"].level == "MINOR"
    # hint 已进送审 prompt（知识优先级链注入生效）
    assert "术语参考：Resume=继续" in service.prompts[0]
