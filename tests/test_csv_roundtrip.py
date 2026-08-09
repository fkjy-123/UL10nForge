from hanhua.core.formats.csv_format import extract_csv, apply_csv, pick_target_col

I2 = "tests/fixtures/localization.csv"
SIMPLE = "tests/fixtures/simple.csv"


def test_i2_extract_and_new_target_col():
    entries, target_col = extract_csv(I2, target_lang="zh-CN")
    assert target_col is None  # 无中文列
    assert len(entries) == 3
    assert entries[0].original == "Start Game"
    for e in entries:
        if e.original == "Start Game":
            e.translation = "开始游戏"
        if e.original == "Aria":
            e.translation = "艾莉亚"
    data = apply_csv(entries, open(I2, encoding="utf-8").read(), ",",
                     target_lang="zh-CN", target_col=None)
    header = data.splitlines()[0]
    assert "ChineseSimplified" in header
    assert "menu_start,Text,Start Game,ゲーム開始,开始游戏" in data
    assert "艾莉亚" in data


def test_i2_existing_target_col():
    entries, target_col = extract_csv(I2, target_lang="Japanese")
    assert target_col == 3
    for e in entries:
        if e.original == "Start Game":
            e.translation = "スタート"
    data = apply_csv(entries, open(I2, encoding="utf-8").read(), ",",
                     target_lang="Japanese", target_col=3)
    row = [r for r in data.splitlines() if r.startswith("menu_start")][0]
    assert row.endswith("スタート")


def test_two_col_csv():
    entries, target_col = extract_csv(SIMPLE, target_lang="zh-CN")
    assert len(entries) == 2
    assert target_col is None
    for e in entries:
        e.translation = "你好" if e.original == "Hello there" else "再见"
    data = apply_csv(entries, open(SIMPLE, encoding="utf-8").read(), ",",
                     target_lang="zh-CN", target_col=None)
    assert "greeting,Hello there,你好" in data
    assert "farewell,Goodbye,再见" in data


def test_pick_target_col():
    header = ["Key", "Type", "English", "ChineseSimplified"]
    assert pick_target_col(header, "zh-CN") == 3
    assert pick_target_col(header, "Japanese") is None


# ── 阶段 3 升级：识别补强（faerie-afterlight / incremental-rts 实证） ──

def test_semicolon_delimited_csv_detected():
    """key;english;russian;german 分号分隔本地化表（incremental-rts 实证）。"""
    from hanhua.core.formats.csv_format import (
        extract_csv_text, looks_like_csv_text)
    text = ("key;english;russian;german\n"
            "menu.tap_to_start;Tap to start;Нажми для старта;Tippe zu\n"
            "menu.vibration;Vibration;Вибрация;Vibration\n\n")
    assert looks_like_csv_text(text)
    entries, target_col = extract_csv_text(text, "dbg")
    assert len(entries) == 2
    assert entries[0].original == "Tap to start"
    assert entries[1].original == "Vibration"


def test_csv_source_col_picks_most_filled_lang():
    """voice 列几乎全空时源列选 en（faerie-afterlight 实证：key,voice,en,...）。"""
    from hanhua.core.formats.csv_format import extract_csv_text
    text = ("key,voice,en,id,sp,fr,de,jp,cn,pt-br\n"
            ",,When Reaching Polar Solium,,Cuando,,,\n"
            ",,Wispy: Hello,,Wispy: Hola,,,\n")
    entries, target_col = extract_csv_text(text, "dbg")
    assert len(entries) == 2
    assert entries[0].original == "When Reaching Polar Solium"
    assert entries[1].original == "Wispy: Hello"
    # cn 列（index 8）被识别为目标列
    assert target_col == 8


def test_csv_detection_ignores_blank_rows():
    from hanhua.core.formats.csv_format import looks_like_csv_text
    text = "key,value\n\n\nhello,world\n\n"
    assert looks_like_csv_text(text)


def test_pick_target_col_cn_alias():
    header = ["key", "voice", "en", "cn"]
    assert pick_target_col(header, "zh-CN") == 3
