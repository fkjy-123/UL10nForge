"""extractor 路径与 txt_format 对齐测试。

backrooms 实证：boot.config 的 'nolog=' 曾走 extractor 内联版（缺
kv_empty 分支）→ 落 plain 被模型回显 → untranslated_text 恒败。
修复后 extractor 与 txt_format.extract_txt 三层 kv 分类一致。
"""
import tempfile
from pathlib import Path

from hanhua.core.extractor import parse_file
from hanhua.core.models import STATUS_SKIPPED


def test_kv_empty_lines_skipped_in_content_routed_txt():
    """空值 kv 行（nolog=）在 extractor 内容路由路径也跳过（kv_empty），
    不落入 plain 参与翻译。"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "boot.config"
        p.write_text(
            "wait-for-native-debugger=0\n"
            "hdr-display-enabled=0\n"
            "single-instance=\n"
            "nolog=\n"
            "build-guid=4195ad97e02d4ad8ac75aa14581a8be3\n",
            encoding="utf-8")
        parsed = parse_file(p)

    assert parsed.format == "txt"
    nolog = [e for e in parsed.entries
             if e.meta.get("kind") == "kv_empty"
             and e.meta.get("key") == "nolog"]
    assert nolog and nolog[0].status == STATUS_SKIPPED
    # 所有行均被结构/空值跳过，无一条落入待翻译
    pending = [e for e in parsed.entries if e.status == "pending"]
    assert not pending


def test_jsonc_suffix_parsed_as_json_with_comments():
    """.jsonc（JSON with Comments）后缀走 JSON 解析路径：注释剥离 +
    键值提取（containment 实证：Language/EN/subtitles.jsonc 曾因后缀
    不在列表被逐行提取，639 条 JSON 行文本落 plain 全失败）。"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "subtitles.jsonc"
        p.write_text(
            "{\n"
            "    // 字幕文件（Unity 本地化 jsonc 格式）\n"
            "    \"subs\": {\n"
            "        \"intro_line\": \"Welcome to the facility\",\n"
            "        \"door_hint\": \"The door is locked\",\n"
            "    },\n"
            "}\n",
            encoding="utf-8")
        parsed = parse_file(p)

    assert parsed.format == "json"
    texts = {e.original for e in parsed.entries}
    assert "Welcome to the facility" in texts
    assert "The door is locked" in texts
    assert all(e.status != STATUS_SKIPPED for e in parsed.entries)
