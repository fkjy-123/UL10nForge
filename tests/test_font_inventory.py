# -*- coding: utf-8 -*-
"""Phase 1：FontConsumerInventory——字体消费者清单（审计 §7.2）。

完成标准：
- 静态可证明对象/动态对象/位图/未知栈分类正确（§9 样本 1-7/10 形态）；
- 会计恒等式：消费者总数 == 各终态之和（任何对象不得静默消失）；
- 未知对象同时进 unknown_objects 审计清单（§9 样本 7 教训）；
- 指纹 font_stacks 派生（tmp/ugui/ngui/bitmap_font/runtime_font_fallback/
  unverified_font_stack）；
- project.write_all 静态分支结果附带 required_glyphs（不可变快照）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from hanhua.core.font import (
    BITMAP_FONT_INJECTION_REQUIRED, BLOCKED, CANDIDATE_ONLY, COVERED,
    MISSING_CODEPOINT, NOT_A_CJK_TARGET, RUNTIME_PROVIDER_UNAVAILABLE,
    UNKNOWN_UNITY_VERSION, UNSUPPORTED_RENDERER, FontConsumer,
    FontConsumerInventory, FontObjectEvidence, ContainerEvidence,
    inventory_font_consumers,
)
from hanhua.core.font.inventory import _classify
from hanhua.core.font.contracts import REASON_CODES
from tests.fixtures.font_games import fixtures as fx


def _obj(**kwargs) -> FontObjectEvidence:
    fields = dict(asset_id="a1", container="c1", renderer="tmp_font")
    fields.update(kwargs)
    return FontObjectEvidence(**fields)


def _entry(text: str, key: str = "k1") -> fx.TextEntry:
    return fx.make_entry(text, key_path=key)


def _inventory(objects, translations=None, **kwargs):
    containers = [ContainerEvidence(
        path=f"c{index}",
        font_objects=tuple(objects if index == 0 else []))
        for index in range(1)]
    return inventory_font_consumers(
        containers, translations or [_entry("继续游戏")], **kwargs)


# ── 分类：静态 / 动态 / 位图 / 未知 / sprite ──────────────────────

def test_static_tmp_classification():
    # replaced 信号由静态替换结果反哺（Phase 2 接线）；未替换 = 未覆盖
    inv = _inventory([_obj(glyph_count=1200,
                           font_codepoints=fx.cjk_font(),
                           layout_version="tmp2", replaced=True)],
                     unity_version="2021.3")
    per = inv.coverage().consumers[0]
    assert per.state == COVERED                       # 静态可证明完整覆盖
    assert per.consumer.kind == "tmp_font"


def test_static_not_replaced_is_incomplete():
    # 替换结果未反哺（replaced=False）→ 静态未覆盖（§9 样本 1 缺陷锁）
    inv = _inventory([_obj(glyph_count=1200,
                           font_codepoints=fx.cjk_font(),
                           layout_version="tmp2")],
                     unity_version="2021.3")
    per = inv.coverage().consumers[0]
    assert per.state == CANDIDATE_ONLY
    assert per.reason == "STATIC_NOT_REPLACED"


def test_zero_glyph_tmp_is_dynamic():
    # 0 glyph + 无码点 = TMP dynamic（运行时生成字形，静态无法证明）
    inv = _inventory([_obj(glyph_count=0, layout_version="")],
                     unity_version="2021.3")
    per = inv.coverage().consumers[0]
    assert per.consumer.kind == "dynamic_tmp"
    assert per.state == BLOCKED
    assert per.reason == RUNTIME_PROVIDER_UNAVAILABLE


def test_ngui_bitmap_classification():
    inv = _inventory([_obj(renderer="ngui", glyph_count=900)],
                     unity_version="2021.3")
    per = inv.coverage().consumers[0]
    assert per.consumer.kind == "ngui_bitmap"
    assert per.state == CANDIDATE_ONLY
    assert per.reason == BITMAP_FONT_INJECTION_REQUIRED


def test_unknown_renderer_goes_to_unknown_list():
    objects = [_obj(renderer="mystery_stack")]
    inv = _inventory(objects, unity_version="2021.3")
    assert len(inv.unknown_objects) == 1               # 审计清单不消失
    assert inv.unknown_objects[0].renderer == "mystery_stack"
    per = inv.coverage().consumers[0]                  # 且进消费者终态
    assert per.consumer.kind == "unknown"
    assert per.state == CANDIDATE_ONLY
    assert per.reason == UNSUPPORTED_RENDERER


def test_sprite_icon_consumer_not_cjk_target():
    inv = _inventory([_obj(sprite_icon=True, glyph_count=500)],
                     unity_version="2021.3")
    per = inv.coverage().consumers[0]
    assert per.state == COVERED
    assert per.reason == NOT_A_CJK_TARGET


def test_missing_unity_version_makes_static_unprovable():
    # 无 unity_version 的 tmp_font → UNKNOWN_UNITY_VERSION（选不了 bundle）
    inv = _inventory([_obj(glyph_count=1200,
                           font_codepoints=fx.cjk_font(),
                           layout_version="tmp2")],
                     unity_version=None)
    per = inv.coverage().consumers[0]
    assert per.state == CANDIDATE_ONLY
    assert per.reason == UNKNOWN_UNITY_VERSION


def test_atlas_ref_unresolved_when_stream_unknown():
    inv = _inventory(
        [_obj(glyph_count=1200, font_codepoints=fx.cjk_font(),
              layout_version="tmp2", atlas_ref="atlas.resS")],
        unity_version="2021.3",
        available_streams={"other.resS"})              # atlas.resS 不在已知流
    per = inv.coverage().consumers[0]
    assert per.consumer.atlas_resolved is False
    assert per.state == CANDIDATE_ONLY
    assert "ATLAS_REFERENCE_UNRESOLVED" == per.reason


# ── 会计恒等式：任何对象不得静默消失 ──────────────────────────────

def test_state_counts_sum_to_total():
    objects = [
        _obj(glyph_count=1200, font_codepoints=fx.cjk_font(),
             layout_version="tmp2"),
        _obj(renderer="ngui", glyph_count=900),
        _obj(renderer="mystery"),
        _obj(renderer="tmp_font", glyph_count=0),
        _obj(sprite_icon=True),
    ]
    inv = _inventory(objects, unity_version="2021.3")
    counts = inv.state_counts()
    assert sum(counts.values()) == len(inv.consumers) == len(objects)


def test_empty_inventory_is_covered_vacuously():
    inv = _inventory([])
    assert len(inv) == 0
    assert inv.coverage().overall == COVERED
    assert inv.state_counts() == {}


# ── 缺字回溯：任意缺字都能找到译文 locator ───────────────────────

def test_missing_glyph_backtraces_to_translation_locator():
    objects = [_obj(glyph_count=1200,
                    font_codepoints=fx.cjk_font(),      # 缺「饕」
                    layout_version="tmp2", replaced=True)]
    inv = _inventory(objects,
                     translations=[_entry(f"继续{fx.RARE_CHAR}", key="k9")],
                     unity_version="2021.3")
    per = inv.coverage().consumers[0]
    assert per.state == CANDIDATE_ONLY
    assert per.reason == MISSING_CODEPOINT
    assert fx.RARE_CP in per.missing_scalars
    assert "f:k9" in inv.required.sources_of(fx.RARE_CP)  # 可回溯


# ── _classify 直接契约 ───────────────────────────────────────────

def test_classify_renderer_matrix():
    container = ContainerEvidence(path="x")
    cases = {
        "tmp_font": "tmp_font", "legacy_font": "legacy_font",
        "textmesh": "textmesh", "ngui": "ngui_bitmap",
        "bmfont": "ngui_bitmap", "dynamic_tmp": "dynamic_tmp",
        "weird": "unknown",
    }
    for renderer, expected_kind in cases.items():
        kind, consumer = _classify(
            _obj(renderer=renderer, glyph_count=1), container,
            set(), "2021.3")
        assert kind == expected_kind, renderer
        assert consumer.kind == expected_kind, renderer


# ── fingerprint font_stacks 派生 ─────────────────────────────────

def test_fingerprint_font_stacks_derivation(monkeypatch):
    from hanhua.core.tooling.fingerprint import _derive_font_stacks
    assert _derive_font_stacks(("tmp", "ugui", "ngui", "bitmap_font"), ()) \
        == ("tmp", "ugui", "ngui", "bitmap_font")
    assert _derive_font_stacks(("tmp",), ("runtime_font_fallback",)) \
        == ("tmp", "runtime_font_fallback")
    assert _derive_font_stacks(("managed_assembly",), ()) \
        == ("unverified_font_stack",)                 # 一个栈都没识别到
    assert _derive_font_stacks((), ()) == ("unverified_font_stack",)


def test_game_fingerprint_carries_font_stacks(tmp_path, monkeypatch):
    from hanhua.core.tooling.fingerprint import fingerprint_game
    # 空目录：无任何字体证据 → unverified_font_stack
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    fp = fingerprint_game(game_dir)
    assert fp.font_stacks == ("unverified_font_stack",)


# ── project.py 快照冒烟 ──────────────────────────────────────────

def test_font_required_glyphs_snapshot(tmp_path):
    """store 行 → 渲染字形需求集：write_ready 取译文，否则回退原文。"""
    from hanhua.core.memory import ProjectStore
    from hanhua.core.project import _font_required_glyph_set

    store = ProjectStore(tmp_path / "proj.db")
    store.init_schema()
    store.add_file("f1", "text/zh.txt", "txt", "utf-8", "lf", {})
    # 真实写路径模式：upsert 建行（pending）→ update_translation 填译文
    store.upsert_entries([
        {"file_id": "f1", "key_path": "k1", "original": "Continue",
         "translation": "", "status": "pending", "meta": "{}"},
        {"file_id": "f1", "key_path": "k2", "original": "Rare<饕>",
         "translation": "", "status": "pending", "meta": "{}"},
    ])
    store.update_translation("f1", "k1", "继续游戏")
    glyphs = _font_required_glyph_set(store).scalars
    assert {ord(c) for c in "继续游戏"} <= glyphs    # 译文
    assert fx.RARE_CP in glyphs                     # 未翻条目原文回退
    # 富文本标签不产生字形需求：<b>呀</b> 只新增「呀」一个码点
    before = glyphs
    store.upsert_entries([
        {"file_id": "f1", "key_path": "k3", "original": "x",
         "translation": "", "status": "pending", "meta": "{}"},
    ])
    store.update_translation("f1", "k3", "<b>呀</b>")
    after = _font_required_glyph_set(store).scalars
    assert after - before == {ord("呀")}
