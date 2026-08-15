"""视觉小说脚本命令行规则测试（Yarn/Naninovel/Ink 源脚本通用）。"""
from __future__ import annotations

from hanhua.core.formats.txt_format import extract_txt
from hanhua.core.placeholders import is_vn_command_line


class TestCommandDetection:
    def test_yarn_commands(self):
        assert is_vn_command_line("<<if $visited>>") is True
        assert is_vn_command_line("<<set $gold = 5>>") is True
        assert is_vn_command_line("<<jump Start>>") is True

    def test_ink_headers(self):
        assert is_vn_command_line("=== forest === ") is True

    def test_naninovel_bare_commands(self):
        assert is_vn_command_line("@stop") is True
        assert is_vn_command_line("@goto Main") is True

    def test_yarn_option_line_not_command(self):
        # -> 选项行是显示文本（选项文字玩家可见）
        assert is_vn_command_line("-> Go left") is False

    def test_quoted_dialogue_not_command(self):
        assert is_vn_command_line('@speak Naru: "Hello there"') is False

    def test_plain_text_not_command(self):
        assert is_vn_command_line("Hello world") is False
        assert is_vn_command_line("Speaker: Dialogue text") is False


class TestTxtExtraction:
    def test_command_lines_skipped(self, tmp_path):
        p = tmp_path / "script.yarn"
        p.write_text(
            "<<if $visited>>\n"
            "title: Start\n"
            "Hello there!\n"
            "-> Go left\n",
            encoding="utf-8")
        entries = extract_txt(p, "script.yarn")
        kinds = {e.key_path: e.meta.get("kind") for e in entries}
        assert kinds["line/0"] == "vn_command"
        assert kinds["plain/2"] == "plain"
        assert kinds["plain/3"] == "plain"   # 选项行是显示文本
        # title: Start 是 Yarn 节点头（跳转目标），按名引用不翻译
        assert kinds["kv/title/1"] == "yarn_title"
