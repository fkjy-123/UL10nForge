"""census.py 普查通道测试：文本 run 探测 + 盲区覆盖 + 预算上限。"""
from __future__ import annotations

import pytest

from hanhua.core.census import (CensusHit, _scan_utf8_runs,
                                _scan_utf16le_runs, _should_skip_file,
                                sweep_game)


class TestUtf8Runs:
    def test_plain_ascii(self):
        hits = _scan_utf8_runs(b"  hello world  ", 0)[0]
        assert hits == [CensusHit("", 2, "utf-8", "hello world")]

    def test_multibyte_utf8(self):
        hits = _scan_utf8_runs(" 你好世界 ".encode("utf-8"), 0)[0]
        assert len(hits) == 1
        assert hits[0].text == "你好世界"
        assert hits[0].offset == 1

    def test_binary_break(self):
        hits = _scan_utf8_runs(b"abcd\x00\xff\xfeefgh", 0)[0]
        assert [h.text for h in hits] == ["abcd", "efgh"]

    def test_short_runs_filtered(self):
        assert _scan_utf8_runs(b"a b", 0)[0] == []

    def test_words_with_spaces_kept(self):
        hits = _scan_utf8_runs(b"ab cd ef", 0)[0]
        assert [h.text for h in hits] == ["ab cd ef"]

    def test_digits_only_filtered(self):
        assert _scan_utf8_runs(b"1234 5678", 0)[0] == []

    def test_whitespace_trimmed(self):
        hits = _scan_utf8_runs(b"  \thello world  \n", 0)[0]
        assert len(hits) == 1
        assert hits[0].text == "hello world"
        assert hits[0].offset == 3

    def test_offset_base(self):
        hits = _scan_utf8_runs(b"xxabcdyy", 100)[0]
        assert hits[0].offset == 100
        assert hits[0].text == "xxabcdyy"


class TestUtf16Runs:
    def test_latin_utf16le(self):
        raw = "Hello World".encode("utf-16-le")
        hits = _scan_utf16le_runs(b"\xff\xfe" + raw, 0)[0]
        assert len(hits) == 1
        assert hits[0].text == "Hello World"
        assert hits[0].offset == 2

    def test_binary_garbage_rejected(self):
        # 随机字节对解码为可打印 CJK（如 \x40\x6f → 潈），无 ASCII 字母
        # → 必须拒绝（假阳性防线）
        garbage = bytes.fromhex("406f4c480b004000" * 3)
        assert _scan_utf16le_runs(garbage, 0)[0] == []

    def test_pure_cjk_no_ascii_rejected(self):
        # 纯 CJK UTF-16（无拉丁字母）当前不覆盖——宁漏勿噪
        hits = _scan_utf16le_runs("你好世界".encode("utf-16-le"), 0)[0]
        assert hits == []

    def test_mixed_cjk_ascii_kept(self):
        raw = "任务 Item 12".encode("utf-16-le")
        hits = _scan_utf16le_runs(raw, 0)[0]
        assert len(hits) == 1
        assert hits[0].text == "任务 Item 12"


class TestSkipLogic:
    def test_covered_suffixes(self, tmp_path):
        for name in ("x.assets", "x.dll", "x.json", "x.png", "x.txt"):
            p = tmp_path / name
            p.write_bytes(b"")
            assert _should_skip_file(p) is not None, name

    def test_blindspot_suffixes(self, tmp_path):
        for name in ("data.dat", "data.bin", "data.bytes", "custom.pakx",
                     "noextension"):
            p = tmp_path / name
            p.write_bytes(b"hello world this is text")
            assert _should_skip_file(p) is None, name

    def test_covered_by_probe(self, tmp_path):
        # 无后缀但内容是 SerializedFile（v22+ 大端头）→ 内容探测排除
        p = tmp_path / "level0"
        head = bytearray(48)
        head[8:12] = (22).to_bytes(4, "big")     # version
        head[12:16] = (48).to_bytes(4, "big")    # data_offset(旧字段)
        head[20:24] = (10).to_bytes(4, "big")    # metadata_size
        head[24:32] = (2000).to_bytes(8, "big")  # file_size u64
        head[32:40] = (48).to_bytes(8, "big")    # data_offset u64
        p.write_bytes(bytes(head))
        assert _should_skip_file(p) == "covered:serialized"


class TestSweepGame:
    def test_end_to_end(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "data.dat").write_bytes(b"Secret message here\n")
        (tmp_path / "noise.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (tmp_path / "covered.json").write_bytes(b'{"k": "visible text"}')
        result = sweep_game(tmp_path)
        texts = [h.text for h in result.hits]
        assert "Secret message here" in texts
        assert "visible text" not in texts  # 已覆盖后缀不扫
        assert result.files_skipped.get("suffix:.png") == 1
        assert result.files_skipped.get("suffix:.json") == 1

    def test_chunk_boundary_run_integrity(self, tmp_path, monkeypatch):
        # 小块扫描下跨块长句必须产出一次完整命中（未闭合 run carry）
        import hanhua.core.census as census_mod
        monkeypatch.setattr(census_mod, "_CHUNK_BYTES", 8)
        sentence = b"The quick brown fox jumps over the lazy dog\n"
        (tmp_path / "data.bin").write_bytes(sentence)
        result = sweep_game(tmp_path)
        assert [h.text for h in result.hits] == [
            "The quick brown fox jumps over the lazy dog"]

    def test_chunk_boundary_multibyte(self, tmp_path, monkeypatch):
        # 多字节序列跨块边界不丢失、不重复
        import hanhua.core.census as census_mod
        monkeypatch.setattr(census_mod, "_CHUNK_BYTES", 5)
        content = "任务提示说明文字".encode("utf-8")
        (tmp_path / "data.bin").write_bytes(content)
        result = sweep_game(tmp_path)
        assert [h.text for h in result.hits] == ["任务提示说明文字"]
