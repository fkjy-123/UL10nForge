"""CSV 写回完整性校验 + 按 ID 写回测试（Rendezvous #30 漏写/行号错位实证）。

覆盖：
  - verify_csv_writeback：检测源列残留英文（漏写检测）
  - apply_csv_by_id：按 ID 匹配写回（引号逗号行合并时行号偏移也不串行）
"""
import csv
import io

from hanhua.core.formats.csv_format import (
    apply_csv_by_id,
    verify_csv_writeback,
)
from hanhua.core.models import TextEntry


SAMPLE = (
    "ID,IND,ENG,CHN\r\n"
    "SeaWall_D1,id1,Hello world,你好\r\n"
    "SeaWall_D2,id2,\"He said, \"\"hi\"\"\",他说\r\n"
    "SeaWall_D3,id3,Goodbye,再见\r\n"
)


def test_verify_csv_writeback_detects_leftovers():
    # ENG 列 1、3 行中文，2 行英文
    text = (
        "ID,IND,ENG,CHN\r\n"
        "A,id1,你好,你好\r\n"
        "B,id2,Still English,译\r\n"
    )
    leftovers = verify_csv_writeback(text)
    assert len(leftovers) == 1
    assert "Still English" in leftovers[0]


def test_verify_csv_writeback_clean():
    text = (
        "ID,IND,ENG,CHN\r\n"
        "A,id1,你好,你好\r\n"
        "B,id2,再见,再见\r\n"
    )
    assert verify_csv_writeback(text) == []


def test_apply_csv_by_id_handles_quoted_commas():
    """引号内逗号导致 csv.reader 行合并/行号偏移——按 ID 写回不串行。"""
    entries = [
        TextEntry(file_id="t", key_path="row/2", original="He said, hi",
                  translation="他说，嗨", meta={"id": "SeaWall_D2"}),
    ]
    out = apply_csv_by_id(entries, SAMPLE)
    rows = list(csv.reader(io.StringIO(out)))
    # 找到 SeaWall_D2 行，ENG 应为译文
    for row in rows:
        if row and row[0] == "SeaWall_D2":
            assert row[2] == "他说，嗨"
            return
    raise AssertionError("SeaWall_D2 row not found")


def test_apply_csv_by_id_writes_target_col_only():
    entries = [
        TextEntry(file_id="t", key_path="row/1", original="Hello world",
                  translation="你好世界", meta={"id": "SeaWall_D1"}),
    ]
    out = apply_csv_by_id(entries, SAMPLE)
    rows = list(csv.reader(io.StringIO(out)))
    for row in rows:
        if row and row[0] == "SeaWall_D1":
            assert row[2] == "你好世界"
            assert row[3] == "你好"  # 其他列不动
            return
    raise AssertionError("SeaWall_D1 row not found")
