# -*- coding: utf-8 -*-
"""Rendezvous 实证回归（2026-08-17）：CSV 对话表被误判为 YAML →
按行号重建丢表头 → 游戏 CSVParser 越界黑屏。修复：CSV 判定优先 +
yaml 判定排除 CSV + yaml 条目不过滤 + 行数守恒保护。"""
from __future__ import annotations

import pytest

from hanhua.core.formats import apply_format_text
from hanhua.core.formats.csv_format import looks_like_csv_text
from hanhua.core.formats.yaml_format import (apply_yaml, extract_yaml_text,
                                             looks_like_yaml_text)
from hanhua.core.models import STATUS_SKIPPED, TextEntry


# Rendezvous TextAsset#30 形态：首列表头为空 + 对话行含冒号（命中 YAML kv）
RENDEZVOUS_CSV = (
    " ,IND,ENG,FRE,ITA,GER,SPA,HGN,JPN,POL,POR,RUS,CHN\r\n"
    "SeaWall_D1,Arum: Apa kau ingat apa sebutan?,Arum: I can't remember,"
    "Tu te souviens?,,,¿Recuerdas?,,ここで,,,,\r\n"
    "SeaWall_D2,Mereka \"pulang\".,After our parents died,"
    "Ils rentrent,,,Que se van,,彼らは,,,,\r\n"
    "SeaWall_D3,Mereka bertemu kembali,Is this really how,"
    "Ils retrouvent,,,Se reúnen,,愛する人,,,,\r\n"
)


def _entry(key_path: str, original: str, translation: str = "",
           status: str = "", meta: dict | None = None) -> TextEntry:
    return TextEntry(
        file_id="f", key_path=key_path, original=original,
        translation=translation, status=status,
        meta={"line_no": int(key_path.rsplit("/", 1)[-1]),
              "raw": original, **(meta or {})})


def test_rendezvous_csv_detected_as_csv_not_yaml() -> None:
    """含冒号的对话 CSV：必须是 csv（行列宽一致），不得判 yaml。"""
    assert looks_like_csv_text(RENDEZVOUS_CSV) is True
    assert looks_like_yaml_text(RENDEZVOUS_CSV) is False


def test_yaml_plain_yaml_still_detected() -> None:
    """真 YAML（无 CSV 结构）判定不受影响。"""
    yaml_text = (
        "config:\n"
        "  name: game\n"
        "  title: Hello world\n"
        "settings:\n"
        "  volume: 0.8\n"
    )
    assert looks_like_yaml_text(yaml_text) is True


def test_yaml_rebuild_rejects_line_loss() -> None:
    """行数守恒保护：条目缺失任一行（表头被过滤的旧库场景）→
    apply_format_text 返回原文（宁漏勿坏），不产生丢行重建。"""
    text = "head: value\nbody: Hello world\n"
    entries = [
        _entry("line/0", "head: value", "head: 值"),
        # line/1 缺失（模拟表头/结构行被过滤后的旧库）
    ]
    out = apply_format_text("yaml", entries, text, {"kind": "textasset"})
    assert out == text  # 拒绝重建


def test_yaml_rebuild_full_rows_ok() -> None:
    """行集完整时正常重建（不误伤）。"""
    text = "head: value\nbody: Hello world\n"
    entries = [
        _entry("line/0", "head: value", "head: 值"),
        _entry("line/1", "body: Hello world", "body: 你好世界"),
    ]
    out = apply_format_text("yaml", entries, text, {"kind": "textasset"})
    assert "你好世界" in out
    assert len(out.splitlines()) == 2


def test_yaml_rebuild_skipped_rows_ok() -> None:
    """全行条目齐全（含 skipped 原样行）正常重建。"""
    text = "a: 1\nb: Two words\nc: 3\n"
    entries = [
        _entry("line/0", "a: 1", status=STATUS_SKIPPED),
        _entry("line/1", "b: Two words", "b: 两个词"),
        _entry("line/2", "c: 3", status=STATUS_SKIPPED),
    ]
    out = apply_format_text("yaml", entries, text, {"kind": "textasset"})
    assert "两个词" in out
    assert len(out.splitlines()) == 3


def test_yaml_extract_every_line_has_entry() -> None:
    """提取端：yaml 每一行（含表头/结构行）都有条目——保证重建行数守恒。"""
    entries = extract_yaml_text(
        "head: value\nbody: Hello world\n# comment\n\nkey: x\n")
    line_nos = {e.meta["line_no"] for e in entries}
    assert line_nos == {0, 1, 2, 3, 4}
