import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from hanhua.core.memory_lifecycle import clear_all_project_records
from hanhua.core.settings import SettingsStore
from hanhua.ui.app_state import AppState
from hanhua.ui.main_window import MainWindow
from hanhua.ui.theme import apply_theme

APP_DIR = Path.home() / ".hanhua"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("汉化助手")
    app.setOrganizationName("hanhua")
    apply_theme(app)
    settings = SettingsStore(APP_DIR / "settings.json")
    settings.load()
    memory_cleanup = clear_all_project_records(APP_DIR)
    state = AppState(
        APP_DIR,
        settings,
        resource_dir=Path(__file__).resolve().parent,
        memory_cleanup=memory_cleanup,
    )
    app.aboutToQuit.connect(state.close)
    win = MainWindow(state)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
