"""记录文档哨兵测试（审计 P2-9）：豁免放行统计哨兵 + 跳过分布聚合。

哨兵是根因 C（无反馈闭环）的收口：跳过/回显豁免是正常机制，但异常
比例是「大块形态未识别」的哑信号——阈值告警写进 summary.md，用户
第一眼可见，不再等实测发现问题。
"""
import json

from hanhua.core.memory import ProjectStore
from hanhua.core.record_writer import (
    _exemption_sentinels, _skipped_by_reason)


def _store(tmp_path, rows: list[dict]) -> ProjectStore:
    """rows 元素：(original, meta?, translation?, status?)。"""
    store = ProjectStore(tmp_path / "project.db")
    store.init_schema()
    store.add_file("f1", "file.txt", "txt", "utf-8", "")
    for i, row in enumerate(rows):
        entry = {"file_id": "f1", "key_path": f"k{i}", "original": row[0]}
        if len(row) > 1:
            entry["meta"] = row[1]
        if len(row) > 2:
            entry["translation"] = row[2]
        if len(row) > 3:
            entry["status"] = row[3]
        store.upsert_entries([entry])
    return store


def _normal(tmp_path, total: int) -> ProjectStore:
    """全 pending 基线（无跳过无豁免 → 无哨兵）。"""
    return _store(tmp_path, [("Hello player",) for _ in range(total)])


def test_no_warnings_on_balanced_store(tmp_path):
    """基线：无跳过/无豁免 → 哨兵不误报。"""
    rows = [("Translated text", {}, "译文", "translated") for _ in range(50)]
    rows += [("Pending text",) for _ in range(30)]
    assert _exemption_sentinels(_store(tmp_path, rows)) == []


def test_skip_rate_warning_fires_over_threshold(tmp_path):
    """跳过率 >70% 且 ≥30 条 → 显式告警（含跳过率与处置指引）。"""
    rows = [("Hello player",) for _ in range(20)]
    rows += [("skipped one",
              {"reason": "prefilter_engine_string", "skipped_count": 40},
              None, "skipped") for _ in range(3)]
    warnings = _exemption_sentinels(_store(tmp_path, rows))
    assert any("跳过率" in w and "异常高" in w for w in warnings)


def test_skip_rate_no_warning_below_minimum_sample(tmp_path):
    """小样本（<30 条跳过）不告警——防阈值误报（小游戏正常跳过少）。"""
    rows = [("Hello player",) for _ in range(2)]
    rows += [("skipped one",
              {"reason": "prefilter_engine_string", "skipped_count": 5},
              None, "skipped") for _ in range(1)]
    assert _exemption_sentinels(_store(tmp_path, rows)) == []


def test_echo_exempt_warning_fires_over_threshold(tmp_path):
    """回显豁免 >30% 且 ≥10 条 → 告警（模型大面积未翻译的信号）。"""
    rows = []
    for i in range(12):
        rows.append(("ProperName", {"echo_exempt": "proper_name"},
                     "ProperName", "translated"))
    for _ in range(18):
        rows.append(("Translated text", {}, "译文", "translated"))
    warnings = _exemption_sentinels(_store(tmp_path, rows))
    assert any("回显豁免" in w and "未翻译" in w for w in warnings)


def test_echo_exempt_no_warning_below_threshold(tmp_path):
    """回显豁免占比低（10%）→ 不告警。"""
    rows = [("ProperName", {"echo_exempt": "proper_name"}, "ProperName",
             "translated") for _ in range(2)]
    for _ in range(18):
        rows.append(("Translated text", {}, "译文", "translated"))
    assert _exemption_sentinels(_store(tmp_path, rows)) == []


def test_dominant_reason_warning_fires_on_concentration(tmp_path):
    """单一跳过原因 >90% 且 ≥30 条 → 提示复核该形态。"""
    rows = [("Hello player",) for _ in range(2)]
    rows += [("skipped one",
              {"reason": "prefilter_engine_string", "skipped_count": 30},
              None, "skipped") for _ in range(3)]
    warnings = _exemption_sentinels(_store(tmp_path, rows))
    assert any("集中于单一原因" in w and "prefilter_engine_string" in w
               for w in warnings)


def test_dominant_reason_no_warning_when_mixed(tmp_path):
    """跳过原因分散（无单一 >90%）→ 不提示；跳过率正常（≤70%）时不告警。"""
    rows = [("Hello player",) for _ in range(40)]
    rows += [("a", {"reason": "r1", "skipped_count": 20}, None, "skipped")
             for _ in range(1)]
    rows += [("b", {"reason": "r2", "skipped_count": 20}, None, "skipped")
             for _ in range(1)]
    assert _exemption_sentinels(_store(tmp_path, rows)) == []


def test_skipped_by_reason_aggregates_prefilter_samples_and_plain():
    """分布聚合：skipped_count 承载真实总数（样本留档），普通条目计 1。"""
    rows = [
        {"meta": {"reason": "prefilter_engine_string", "skipped_count": 40}},
        {"meta": {"reason": "prefilter_engine_string", "skipped_count": 12}},
        {"meta": {"reason": "code_line"}},
        {"meta": {}},
    ]
    dist = _skipped_by_reason(rows)
    assert dist["prefilter_engine_string"] == 52
    assert dist["code_line"] == 1
    assert dist["unknown"] == 1


def test_sentinel_meta_handles_stringified_json(tmp_path):
    """meta 是字符串 JSON 的行（GUI 存储形态）也能正确统计豁免。"""
    store = ProjectStore(tmp_path / "project.db")
    store.init_schema()
    store.add_file("f1", "file.txt", "txt", "utf-8", "")
    store.upsert_entries([{
        "file_id": "f1", "key_path": f"e{i}",
        "original": "ProperName",
        "translation": "ProperName",
        "meta": json.dumps({"echo_exempt": "proper_name"}),
        "status": "translated",
    } for i in range(12)] + [{
        "file_id": "f1", "key_path": f"t{i}",
        "original": "Text", "translation": "译文",
        "meta": json.dumps({"quality_passed": True}),
        "status": "translated",
    } for i in range(18)])
    warnings = _exemption_sentinels(store)
    assert any("回显豁免" in w for w in warnings)


def test_summary_includes_sentinel_section(tmp_path, monkeypatch):
    """哨兵告警写入 summary.md（用户第一眼可见），不依赖具体数据场景。"""
    from hanhua.core.record_writer import export_records
    from tests.test_scanner import _make_tree
    from hanhua.core.project import Project

    game_dir = _make_tree()
    proj = Project.open_game_dir(game_dir, tmp_path / "app")
    proj.scan()
    row = next(r for r in proj.store.get_entries()
               if r["status"] == "pending")
    proj.store.set_manual(row["file_id"], row["key_path"], "已翻译")

    monkeypatch.setattr(
        "hanhua.core.record_writer._exemption_sentinels",
        lambda store: ["跳过率 90% 异常高——测试告警"])
    out_root = tmp_path / "records"
    export_records(proj, out_root)
    rec_dir = out_root / proj.game_dir.name
    summary = (rec_dir / "summary.md").read_text(encoding="utf-8")
    assert "哨兵告警" in summary
    assert "跳过率 90% 异常高" in summary
