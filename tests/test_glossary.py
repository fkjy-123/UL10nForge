import tempfile
from pathlib import Path

from hanhua.core.glossary import GlossaryStore


def test_glossary_crud():
    g = GlossaryStore(Path(tempfile.mkdtemp()) / "g.db")
    g.init_schema()
    g.add("Aria", "艾莉亚", "人名", "女主")
    g.add("Vale", "幽谷", "地名")
    rows = g.list_all()
    assert len(rows) == 2 and rows[0]["term"] == "Aria"
    g.update("Aria", "艾莉亚·灰", "人名", "修正")
    assert g.list_all()[0]["translation"] == "艾莉亚·灰"
    g.delete("Vale")
    assert len(g.list_all()) == 1
    assert g.by_category("人名") == ["Aria"]
    assert g.format_for_prompt() == "Aria → 艾莉亚·灰（人名）"


def test_detect_conflicts_reports_same_source_different_translation():
    g = GlossaryStore(Path(tempfile.mkdtemp()) / "conflict.db")
    g.init_schema()
    g.add("Moon Key", "月光钥匙")
    g.add("moon key", "月之钥匙")     # 大小写变体 + 不同译名 → 冲突
    g.add("Magic Sword", "魔剑")

    conflicts = g.detect_conflicts()

    assert len(conflicts) == 1
    assert conflicts[0]["key"] == "moonkey"
    assert {r["term"] for r in conflicts[0]["rows"]} == {"Moon Key", "moon key"}
    assert len(conflicts[0]["rows"]) == 2


def test_detect_conflicts_same_source_same_translation_is_fine():
    g = GlossaryStore(Path(tempfile.mkdtemp()) / "ok.db")
    g.init_schema()
    g.add("Moon Key", "月光钥匙")
    g.add("moon key", "月光钥匙")     # 同源同译 → 无冲突

    assert g.detect_conflicts() == []


def test_detect_conflicts_ignores_punctuation_variants():
    g = GlossaryStore(Path(tempfile.mkdtemp()) / "punct.db")
    g.init_schema()
    g.add("Moon Key", "月光钥匙")
    g.add("Moon-Key", "月之钥匙")     # 空白/连字符变体 → 归一化后同源冲突

    conflicts = g.detect_conflicts()

    assert len(conflicts) == 1
    assert conflicts[0]["key"] == "moonkey"


def test_detect_conflicts_unrelated_terms_never_collide():
    g = GlossaryStore(Path(tempfile.mkdtemp()) / "none.db")
    g.init_schema()
    g.add("Sword", "剑")
    g.add("Shield", "盾")
    g.add("Echo", "回声")

    assert g.detect_conflicts() == []
