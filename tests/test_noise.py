"""噪音识别测试：文件名黑名单、标识符过滤、文件级判定、重扫收敛。"""
import tempfile
from pathlib import Path

from hanhua.core.extractor import looks_like_noise_file, parse_file
from hanhua.core.models import TextEntry
from hanhua.core.project import Project
from hanhua.core.scanner import discover


def test_looks_like_noise():
    # 空文件 → 噪音
    assert looks_like_noise_file([])
    # 全标识符 → 噪音
    assert looks_like_noise_file([
        TextEntry(file_id="f", key_path="a", original="NavMeshLink"),
        TextEntry(file_id="f", key_path="b", original="ClearTrackedList"),
        TextEntry(file_id="f", key_path="c", original="NavMeshModifier"),
    ])
    # 正常句子 → 非噪音
    assert not looks_like_noise_file([
        TextEntry(file_id="f", key_path="a", original="Hello there"),
        TextEntry(file_id="f", key_path="b", original="Start Game"),
    ])


def _noise_dir():
    d = Path(tempfile.mkdtemp())
    (d / "MonoBleedingEdge" / "etc" / "mono").mkdir(parents=True)
    (d / "MonoBleedingEdge" / "etc" / "mono" / "browscap.ini").write_text(
        "Ask=true\nTeoma=false\n", encoding="utf-8")
    (d / "x_Data").mkdir()
    (d / "x_Data" / "RuntimeInitializeOnLoads.json").write_text(
        '{"RuntimeInitializeOnLoads": ["NavMeshLink", "ClearTrackedList"]}', encoding="utf-8")
    (d / "x_Data" / "StreamingAssets").mkdir()
    (d / "x_Data" / "StreamingAssets" / "aa").mkdir()
    (d / "x_Data" / "StreamingAssets" / "aa" / "settings.json").write_text(
        '{"catalog": "AddressablesMainContentCatalog"}', encoding="utf-8")
    return d


def test_discover_skips_all_runtime_noise():
    d = _noise_dir()
    files = discover(d)
    # Mono 运行时文件与已知噪音文件绝不出现
    assert not any("MonoBleedingEdge" in p.parts for p in files)
    assert not any(p.name in ("browscap.ini", "RuntimeInitializeOnLoads.json") for p in files)
    # Addressables 配置目录可被发现，但内容为标识符 → 文件级判定为噪音不入库
    for p in files:
        assert p.name != "settings.json" or parse_file(p, "f").noise is True


def test_parse_file_flags_noise():
    d = _noise_dir()
    pf = parse_file(d / "x_Data" / "RuntimeInitializeOnLoads.json", "f1")
    assert pf.noise is True


def test_rescan_cleans_stale_entries():
    d = _noise_dir()
    # 先造一个"以前被当作本地化、现在被规则淘汰"的库
    app_dir = Path(tempfile.mkdtemp()) / "app"
    proj = Project.open_game_dir(d, app_dir)
    proj.store.init_schema()
    proj.store.add_file("stale.json", "stale.json", "json", "utf-8", "\n")
    proj.store.upsert_entries([{"file_id": "stale.json", "key_path": "a",
                                "original": "NavMeshLink", "status": "pending", "meta": {}}])
    assert proj.store.count("pending") == 1
    n = proj.scan()
    assert n == 0                       # 全是噪音，一个文件都没保留
    assert proj.store.get_files() == []  # 旧的噪音文件被清理
    assert proj.store.count("pending") == 0
