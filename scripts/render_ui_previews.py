"""Aurora Forge 视觉验收：离屏渲染四页并保存 PNG。

用法：
    python scripts/render_ui_previews.py --output .scratch/ui-previews \
        --sizes 1280x720 1920x1080

在 offscreen 平台创建演示项目状态，依次导航 概览/审校/运行/设置 四页，
逐张 grab().save()。用于检查溢出、空洞、对齐、层级与语义色。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("HANHUA_REDUCED_MOTION", "1")  # 渲染快照不追动画

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from hanhua.core.models import GameProfile
from hanhua.core.settings import SettingsStore
from hanhua.ui.app_state import AppState
from hanhua.ui.main_window import MainWindow
from hanhua.ui.theme import apply_theme


class _DemoProject:
    """演示项目桩：仅承载页面渲染所需的最小属性（避免对真实游戏目录
    做指纹检测，预览只关心 UI 呈现）。"""

    def __init__(self, store, game_dir: Path):
        self.store = store
        self.game_dir = game_dir
        profile = GameProfile()
        profile.game_name = "Aurora 极光试炼"
        profile.source_lang = "en"
        profile.target_lang = "zh-CN"
        self.profile = profile


def _make_demo_state(tmp_root: Path) -> AppState:
    """构造演示状态：假项目（store 注入演示条目）+ 已配置 API。"""
    settings = SettingsStore(tmp_root / "settings.json")
    settings.load()
    state = AppState(tmp_root, settings)
    from hanhua.core.memory import ProjectStore
    store = ProjectStore(tmp_root / "demo.db")
    store.init_schema()
    store.add_file(1, "Assets/Text/UI.txt", "txt", "utf-8", "lf")
    store.upsert_entries([
        {"file_id": 1, "key_path": "obj/quit", "original": "QUIT",
         "translation": "", "status": "pending", "locked": 0,
         "meta": {"confidence": "medium"}},
        {"file_id": 1, "key_path": "obj/play", "original": "PLAY",
         "translation": "开始游戏", "status": "translated", "locked": 1,
         "meta": {"quality_passed": True, "confidence": "high"}},
        {"file_id": 1, "key_path": "obj/settings", "original": "SETTINGS",
         "translation": "设置", "status": "translated", "locked": 0,
         "meta": {"quality_passed": False, "review_status": "flagged"}},
    ])
    project = _DemoProject(store, tmp_root / "demo-game")
    # 走正式切换路径（emit projectOpened → 首页切到项目态），而非直接
    # 赋值——否则 home.png 会渲染欢迎态而非项目态（M2）。
    state.switch_project(project)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=".scratch/ui-previews")
    parser.add_argument("--sizes", nargs="+", default=["1280x720"])
    args = parser.parse_args()

    app = QApplication([])
    apply_theme(app)
    state = _make_demo_state(Path(".scratch") / "preview-state")
    window = MainWindow(state)
    window.show()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    for size in args.sizes:
        w, h = (int(part) for part in size.lower().split("x"))
        window.resize(w, h)
        app.processEvents()
        for name in ("home", "review", "translate", "settings"):
            window.navigate(name)
            app.processEvents()
            app.processEvents()
            path = out / f"{size}-{name}.png"
            window.grab().save(str(path))
            print(f"已渲染 {path} ({window.width()}x{window.height()})")
    print(f"完成：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
