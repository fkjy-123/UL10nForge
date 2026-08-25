from hanhua.core.formats.txt_format import extract_txt, apply_txt
from hanhua.core.models import STATUS_SKIPPED, STATUS_TRANSLATED
from hanhua.core.formats.txt_format import _is_json_value, _replace_json_value

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


def test_extract_txt_empty_kv_value_is_skipped(tmp_path):
    # Morfosi boot.config 实证：'nolog=' 空值 kv 行此前落入 plain 分支成为
    # 可译条目，模型回显 → untranslated_text 恒败。现在标记 kv_empty 跳过。
    source = "wait-for-preload=1\nnolog=\nTitle=Hello world\nkey\t\n"
    p = tmp_path / "boot.txt"
    p.write_text(source, encoding="utf-8")
    entries = extract_txt(p, "boot.txt")
    by_line = {e.meta["line_no"]: e for e in entries}
    assert by_line[0].meta["kind"] == "kv_structural"  # 数字值（原行为，跳过）
    assert by_line[2].status != STATUS_SKIPPED   # Title=Hello world 可翻译
    nolog = by_line[1]
    assert nolog.status == STATUS_SKIPPED
    assert nolog.meta["kind"] == "kv_empty"
    assert nolog.original == ""
    tab_empty = by_line[3]
    assert tab_empty.status == STATUS_SKIPPED
    assert tab_empty.meta["kind"] == "kv_empty"
    assert tab_empty.meta["delim"] == "\t"
    # 写回原样输出（行保留，值区空）
    out = apply_txt(entries)
    assert "nolog=" in out
    assert "key\t" in out


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


# ── JSON 语言包写回保护（containment-breach-hd 实证）──────────────────
# 根因：.subs 语言包被 txt 格式处理，kv 值 `"9V Battery",` 用中文弯引号
# + 丢逗号整段替换 → 文件级 JSON 失效 → 游戏启动读语言包崩溃卡死。


def test_is_json_value_recognizes_json_strings():
    assert _is_json_value('"9V Battery",')
    assert _is_json_value('"9V Battery"')
    assert _is_json_value('"Strange Note"')
    assert _is_json_value('"Mobile Task Forces",')
    assert _is_json_value('"Dr. Allok\' Note",')   # 单引号无需转义
    assert not _is_json_value("9V Battery")            # 无引号 = 普通值
    assert not _is_json_value("C:\\foo")              # 裸反斜杠非 JSON 转义
    assert not _is_json_value('"bad\\escape",')       # \e 非法 JSON 转义


def test_replace_json_value_preserves_quotes_and_comma():
    raw = '    "bat_nor": "9V Battery",'
    out = _replace_json_value(raw, '"9V Battery",', "“9V电池”")
    assert out == '    "bat_nor": "9V电池",'          # 弯引号剥掉 + 逗号保留
    assert out.count('"') == 4                          # 键2+值2 引号配对
    assert out.endswith(",")


def test_replace_json_value_no_trailing_comma():
    raw = '    "docStrange": "Strange Note"'
    out = _replace_json_value(raw, '"Strange Note"', "奇怪的纸条")
    assert out == '    "docStrange": "奇怪的纸条"'
    assert not out.endswith(",")


def test_apply_txt_json_language_pack_roundtrip(tmp_path):
    # 模拟 itemStrings.subs：混合空格/tab 缩进、有无尾逗号、弯引号译文
    source = (
        '{\n'
        '    "bat_nor": "9V Battery",\n'
        '\t"docMTF":"Mobile Task Forces",\n'
        '\t"doc093rm": "SCP-093 Recovered Materials",\n'
        '\t"chara_lure": "Strange Note"\n'
        '}'
    )
    p = tmp_path / "itemStrings.subs"
    p.write_text(source, encoding="utf-8")
    entries = extract_txt(p, "itemStrings.subs")
    by_line = {e.meta["line_no"]: e for e in entries}
    # tab 缩进 kv 行此前匹配失败落 plain（整行翻译破坏 JSON）——现在按 kv 提取
    assert by_line[2].meta["kind"] == "kv"           # tab 缩进 + 无空格冒号
    assert by_line[3].meta["kind"] == "kv"
    assert by_line[4].meta["kind"] == "kv"           # tab 缩进、无尾逗号

    trans = {
        '"9V Battery",': "“9V电池”",
        '"Mobile Task Forces",': "“机动特遣队”，",
        '"SCP-093 Recovered Materials",': "SCP-093 回收的材料。",
        '"Strange Note"': "“奇怪的纸条”",
    }
    for e in entries:
        if e.original in trans:
            e.translation = trans[e.original]
            e.status = STATUS_TRANSLATED
    out = apply_txt(entries)

    assert '    "bat_nor": "9V电池",' in out
    assert '\t"docMTF":"机动特遣队",' in out
    assert '\t"doc093rm": "SCP-093 回收的材料。",' in out
    assert '\t"chara_lure": "奇怪的纸条"' in out
    # 结构守恒：行数（源不含尾换行时 apply_txt 逐行重建亦无尾换行）
    # + 每行 ASCII 引号成对 + 逗号结构不变
    assert out.count("\n") == source.count("\n")
    assert out.count("\n") == source.rstrip("\n").count("\n")
    for line in out.splitlines():
        if '"' in line:
            assert line.count('"') % 2 == 0, line
    # 逗号结构：原文件带逗号的行写回后仍带逗号
    src_lines = source.splitlines()
    out_lines = out.splitlines()
    for a, b in zip(src_lines, out_lines):
        assert a.rstrip().endswith(",") == b.rstrip().endswith(","), (a, b)
