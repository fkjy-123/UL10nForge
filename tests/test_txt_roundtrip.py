from hanhua.core.formats.txt_format import extract_txt, apply_txt
from hanhua.core.models import STATUS_SKIPPED

FIXTURE = "tests/fixtures/strings.txt"


def test_extract_txt():
    entries = extract_txt(FIXTURE)
    orig = {e.key_path: e.original for e in entries}
    assert orig["kv/title/1"] == "Valley of Echoes"
    assert orig["kv/subtitle/2"] == "A tale of two worlds"
    assert orig["kv/controls/3"] == "Move"
    assert orig["plain/4"] == "Press {key} to jump"
    kinds = {e.key_path: e.status for e in entries}
    assert kinds["line/0"] == STATUS_SKIPPED      # 注释
    assert kinds["line/5"] == STATUS_SKIPPED      # [section]


def test_apply_txt_roundtrip():
    entries = extract_txt(FIXTURE)
    for e in entries:
        if e.original == "Valley of Echoes":
            e.translation = "回响之谷"
        if e.original == "Press {key} to jump":
            e.translation = "按 {key} 键跳跃"
    out = apply_txt(entries)
    assert "title=回响之谷" in out
    assert "按 {key} 键跳跃" in out
    assert "# Main menu" in out
    assert "[warning]" in out
    assert "controls\tMove" in out
    assert out.count("\n") == 5


def test_apply_preserves_spacing_around_delim():
    entries = extract_txt(FIXTURE)
    e = [x for x in entries if x.key_path == "kv/subtitle/2"][0]
    e.translation = "双界物语"
    out = apply_txt(entries)
    assert "subtitle: 双界物语" in out


def test_extract_txt_skips_urls_cli_args_and_structural_values(tmp_path):
    source = (
        "Title=My Game\n"
        "http://steamworks.github.io\n"
        "--platform=Windows\n"
        "--linker-options=PdbAltPath=\"PanzerShoot_Data/Plugins/x86_64\"\n"
        "PluginDir=Assets/Plugins/x.dll\n"
        "Welcome=欢迎回来\n"
    )
    p = tmp_path / "config.txt"
    p.write_text(source, encoding="utf-8")
    entries = extract_txt(p, "config.txt")
    by_line = {e.meta["line_no"]: e for e in entries}
    assert by_line[0].status != STATUS_SKIPPED          # Title=My Game 可翻译
    assert by_line[5].status != STATUS_SKIPPED          # Welcome=欢迎回来 可翻译
    assert by_line[1].status == STATUS_SKIPPED          # 整行 URL
    assert by_line[2].status == STATUS_SKIPPED          # CLI 参数
    assert by_line[3].status == STATUS_SKIPPED          # CLI 参数（引号路径值）
    assert by_line[4].status == STATUS_SKIPPED          # 值本身是路径


def test_extract_txt_tab_delim_structural_value_has_no_delim_group(tmp_path):
    # honorplusplus 实证：_TAB 匹配无 delim 命名组，kv_structural 分支
    # 直接 m.group("delim") 会抛 IndexError 使整个扫描崩溃
    # 整行不是 hard structural（避免提前分支），值是键风格 → should_skip
    source = "boot_text\tui_newGame\n"
    p = tmp_path / "boot.txt"
    p.write_text(source, encoding="utf-8")
    entries = extract_txt(p, "boot.txt")
    assert len(entries) == 1
    e = entries[0]
    assert e.status == STATUS_SKIPPED
    assert e.meta["kind"] == "kv_structural"
    assert e.meta["delim"] == "\t"
