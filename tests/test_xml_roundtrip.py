from hanhua.core.formats import xml_format
from hanhua.core.formats.xml_format import extract_xml, apply_xml

FIXTURE = "tests/fixtures/dialogues.xml"


def test_extract_xml():
    entries = extract_xml(FIXTURE)
    orig = {e.key_path: e.original for e in entries}
    assert orig["/root/dialogue[0]/speaker"] == "Aria"
    assert orig["/root/dialogue[0]/text"] == "The night is long."
    assert orig["/root/item[0]/@name"] == "Health Potion"
    assert orig["/root/item[0]/description"] == "Restores 50 HP"
    # id 风格的属性值不提取（choice 的 name="accept"）
    assert "/root/dialogue[0]/choice/@name" not in orig
    # 同名兄弟加索引（文本节点的 key_path 即元素路径）
    assert orig["/root/dialogue[1]/text"] == "We must not linger here."
    assert orig["/root/dialogue[1]/speaker"] == "Orin"


def test_apply_xml_roundtrip():
    entries = extract_xml(FIXTURE)
    for e in entries:
        if e.original == "The night is long.":
            e.translation = "夜很长。"
        if e.original == "Health Potion":
            e.translation = "生命药水"
    out = apply_xml(entries, open(FIXTURE, encoding="utf-8").read())
    assert "夜很长。" in out
    assert 'name="生命药水"' in out
    assert "Accept the quest" in out
    assert '<?xml version="1.0" encoding="utf-8"?>' in out
    # 结构保留：重新解析后元素数量一致
    import xml.etree.ElementTree as ET
    src_root = ET.fromstring(open(FIXTURE, encoding="utf-8").read())
    out_root = ET.fromstring(out)
    assert len(list(src_root.iter())) == len(list(out_root.iter()))


def test_apply_no_translation_unchanged():
    entries = extract_xml(FIXTURE)
    out = apply_xml(entries, open(FIXTURE, encoding="utf-8").read())
    assert out == open(FIXTURE, encoding="utf-8").read()


def test_extract_xml_assigns_sibling_paths_in_linear_work(tmp_path, monkeypatch):
    child_count = 300
    xml_path = tmp_path / "large-map.xml"
    xml_path.write_text(
        "<map><layer>"
        "<tile><label>Tile 0</label></tile>"
        "<object><label>Interleaved object</label></object>"
        + "".join(
            f"<tile><label>Tile {index}</label></tile>"
            for index in range(1, child_count)
        )
        + "</layer><object><label>Only object</label></object></map>",
        encoding="utf-8",
    )
    xpath_calls = 0
    original_xpath = xml_format._xpath

    def counted_xpath(*args, **kwargs):
        nonlocal xpath_calls
        xpath_calls += 1
        return original_xpath(*args, **kwargs)

    monkeypatch.setattr(xml_format, "_xpath", counted_xpath)

    entries = extract_xml(xml_path)
    originals = {entry.original: entry.key_path for entry in entries}

    assert originals["Tile 0"] == "/map/layer[0]/tile[0]/label"
    assert originals["Tile 299"] == "/map/layer[0]/tile[299]/label"
    assert originals["Interleaved object"] == "/map/layer[0]/object/label"
    assert originals["Only object"] == "/map/object[0]/label"
    assert xpath_calls <= child_count * 4
