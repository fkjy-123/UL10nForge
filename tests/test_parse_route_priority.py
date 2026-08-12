"""识别 D6 测试：parse_file 内容路由优先级钉死（评估报告升级机会 6）。

现有 19 个规则交互用例只覆盖 rawstr 分类链——内容路由的优先级
（zip > sqlite > JSON > XML > txt）此前无测试钉死：伪装扩展名容器
（.bytes 里的 zip）或未知扩展名文本（.subs 里的 JSON）按内容判定，
优先级顺序变化会静默改变格式归属（写回路径随 format 变，风险高）。
"""
import gzip
import struct
from pathlib import Path

from hanhua.core.extractor import parse_file


def _write(tmp_path, name: str, raw: bytes) -> Path:
    p = Path(tmp_path) / name
    p.write_bytes(raw)
    return p


def _txt(s: str) -> bytes:
    return s.encode("utf-8")


def test_content_route_zip_over_text(tmp_path):
    """伪装扩展名（.bytes 的 zip 容器）→ 内容路由判 zip（魔数优先）。"""
    p = _write(tmp_path, "data.bytes", b"PK\x03\x04" + b"\x00" * 16)
    assert parse_file(p).format == "zip"


def test_content_route_sqlite_over_text(tmp_path):
    """.dat 的 SQLite 文件 → 内容路由判 sqlite。"""
    p = _write(tmp_path, "data.dat", b"SQLite format 3\x00" + b"\x00" * 16)
    assert parse_file(p).format == "sqlite"


def test_content_route_json_over_xml_over_txt(tmp_path):
    """.dat 文本 → JSON 探测（{ 开头）优先于 XML；XML 次之；纯文本兜底。"""
    p = _write(tmp_path, "data.dat", _txt('{"key": "value"}'))
    assert parse_file(p).format == "json"
    p2 = _write(tmp_path, "data2.dat",
                _txt("<root><entry>你好</entry></root>"))
    assert parse_file(p2).format == "xml"
    p3 = _write(tmp_path, "data3.dat", _txt("just plain text\nline two"))
    assert parse_file(p3).format == "txt"


def test_content_route_json_probe_fallback_on_bad_json(tmp_path):
    """JSON 探测失败（{ 开头但非法）→ 回退 txt（不崩、不误判格式）。"""
    p = _write(tmp_path, "data.dat", _txt("{ invalid json"))
    pf = parse_file(p)
    assert pf.format == "txt"


def test_unknown_suffix_routed_by_content(tmp_path):
    """.subs/.custom 等未知扩展名 → 按内容路由（JSON → json 格式）。"""
    p = _write(tmp_path, "strings.subs", _txt('{"Title": "你好"}'))
    assert parse_file(p).format == "json"
    p2 = _write(tmp_path, "misc.custom",
                _txt("<resx><data>你好</data></resx>"))
    assert parse_file(p2).format == "xml"


def test_gzip_decompressed_then_content_routed(tmp_path):
    """.gz 先解压再按内容路由（JSON 包 → json；文本包 → txt）。"""
    payload = gzip.compress(_txt('{"a": 1}'))
    p = _write(tmp_path, "pack.gz", payload)
    assert parse_file(p).format == "json"
    p2 = _write(tmp_path, "note.gz", gzip.compress(_txt("hello world")))
    assert parse_file(p2).format == "txt"


def test_gzip_corrupt_falls_back_txt(tmp_path):
    """损坏 gz（不可解压）→ txt 空结果（不崩）。"""
    p = _write(tmp_path, "bad.gz", b"\x1f\x8b\x08\x00not-gzip-at-all")
    assert parse_file(p).format == "txt"


def test_extension_route_for_known_formats(tmp_path):
    """白名单扩展名正常路由（各格式归属钉死，写回路径随 format 变化）。"""
    cases = {
        "a.json": (b'{"k": "v"}', "json"),
        "a.csv": (_txt("k,v\n1,2\n"), "csv"),
        "a.yaml": (_txt("k: v\n"), "yaml"),
        "a.srt": (_txt("1\n00:00:01,000 --> 00:00:02,000\nHi\n"), "subtitle"),
        "a.po": (_txt('msgid "Hi"\nmsgstr ""\n'), "po"),
        "a.ink": (_txt("Hello\n-> END\n"), "ink_yarn"),
    }
    for name, (raw, fmt) in cases.items():
        assert parse_file(_write(tmp_path, name, raw)).format == fmt


def test_gz_json_roundtrip_keypaths_stable(tmp_path):
    """gz 内 JSON 与裸 JSON 的条目 key_path 同形（写回 locator 不受
    外层容器影响）。"""
    raw = '{"Title": "你好"}'.encode("utf-8")
    plain = _write(tmp_path, "a.json", raw)
    packed = _write(tmp_path, "a.json.gz", gzip.compress(raw))
    kp = {e.key_path for e in parse_file(plain).entries}
    assert {e.key_path for e in parse_file(packed).entries} == kp
