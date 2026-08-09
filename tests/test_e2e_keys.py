"""E2E：Localization 键值保护全流程（需要 SEWER CALL 游戏目录，缺失时跳过）。

关键：键（ui_newGame 等，在 SharedTableData）绝不能翻译——游戏代码按键名查找；
值（NEW GAME 等，在 StringTable）才翻译。
"""
import glob
import os
import shutil
from pathlib import Path

import pytest

from hanhua.core.project import Project
from hanhua.core.unity.extractor import scan_strings

GAME = Path(os.environ.get(
    "HANHUA_SEWER_CALL_DIR",
    r"C:\Users\mingming\Downloads\SEWER CALL\SEWER CALL",
))
KEY = "ui_newGame"
VALUE = "NEW GAME"


@pytest.mark.skipif(not GAME.exists(), reason="需要 SEWER CALL 游戏目录")
def test_key_value_end_to_end(tmp_path):
    tmp = tmp_path
    isolated_game = tmp / "source" / GAME.name
    shutil.copytree(GAME, isolated_game)
    proj = Project.open_game_dir(isolated_game, tmp / "app")
    proj.scan()
    proj.scan_v2()
    store = proj.store
    # 键不应产生条目（被引擎过滤）
    key_entries = [e for e in store.get_entries() if e["original"] == KEY]
    assert key_entries == [], f"键 {KEY} 不应被提取为条目"
    # 翻译值位置
    n = 0
    for e in store.get_entries():
        if e["status"] == "pending" and e["original"] == VALUE:
            store.set_manual(e["file_id"], e["key_path"], "开始游戏")
            n += 1
    assert n >= 1
    # 重扫（幂等：键不产生条目、值译文保留）
    proj.scan()
    proj.scan_v2()
    val = [e for e in store.get_entries()
           if e["original"] == VALUE and e["translation"] == "开始游戏"]
    assert len(val) >= 1, "值译文应在重扫后保留"
    # 写回（重建副本；不启动冒烟，避免自动化环境弹窗/进程干扰）
    result = proj.write_all(smoke=False)
    v2 = result.get("v2")
    assert v2.files >= 1
    # 副本验证：键保持英文、值为中文
    from UnityPy import Environment
    from hanhua.core.unity.writer import _dispose_environment
    env = Environment()
    try:
        env.load(glob.glob(str(proj.out_dir) + r"/**/*.bundle", recursive=True))
        key_found = value_found = 0
        for obj in env.objects:
            if obj.type.name not in ("MonoBehaviour", "ScriptableObject"):
                continue
            try:
                raw = obj.get_raw_data()
            except Exception:  # noqa: BLE001
                continue
            if not raw:
                continue
            strs = [s for _, s in scan_strings(raw)]
            if KEY in strs:
                key_found += 1
            if "开始游戏" in strs:
                value_found += 1
    finally:
        _dispose_environment(env)
    assert key_found >= 1, "键必须保持英文（游戏查找正常）"
    assert value_found >= 1, "值必须是中文（显示汉化）"
