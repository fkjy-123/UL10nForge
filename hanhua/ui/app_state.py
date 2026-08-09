"""应用状态：全局设置 + 当前项目，页面间通过信号协作。"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import threading

from PySide6.QtCore import QObject, Signal

from hanhua.core.local_model import LocalModelManager
from hanhua.core.memory_lifecycle import MemoryCleanupSummary
from hanhua.core.models import ApiConfig, GameProfile
from hanhua.core.project import Project
from hanhua.core.settings import SettingsStore


class AppState(QObject):
    projectAboutToChange = Signal(object)  # previous Project
    projectOpened = Signal(object)   # Project
    entriesChanged = Signal()        # 条目状态变化（审校/翻译后刷新）
    settingsChanged = Signal()       # 设置保存后（主窗口状态栏刷新）
    analysisChanged = Signal(object) # AnalysisReport

    def __init__(self, app_dir: Path, settings: SettingsStore,
                 resource_dir: Path | None = None,
                 memory_cleanup: MemoryCleanupSummary | None = None):
        super().__init__()
        self.app_dir = Path(app_dir)
        self.settings = settings
        self.resource_dir = Path(resource_dir or app_dir)
        self.memory_cleanup = memory_cleanup or MemoryCleanupSummary()
        self.local_model = LocalModelManager(
            self.resource_dir, state_dir=self.app_dir)
        self.project: Project | None = None
        self._project_generation = 0
        self._project_lock = threading.RLock()
        self._project_leases: dict[int, int] = {}
        self._pending_project_close: dict[int, Project] = {}
        self.analysis_report = None

    @property
    def project_generation(self) -> int:
        return self._project_generation

    def is_current_project(self, project, generation: int) -> bool:
        with self._project_lock:
            return (self.project is project
                    and self._project_generation == generation)

    @contextmanager
    def project_lease(self, project: Project, generation: int):
        key = id(project)
        with self._project_lock:
            acquired = (self.project is project
                        and self._project_generation == generation)
            if acquired:
                self._project_leases[key] = self._project_leases.get(key, 0) + 1
        try:
            yield acquired
        finally:
            close_project = None
            if acquired:
                with self._project_lock:
                    remaining = self._project_leases[key] - 1
                    if remaining:
                        self._project_leases[key] = remaining
                    else:
                        self._project_leases.pop(key, None)
                        close_project = self._pending_project_close.pop(
                            key, None)
            if close_project is not None:
                close_project.store.close()

    def _defer_or_take_close(self, project: Project | None):
        if project is None:
            return None
        key = id(project)
        if self._project_leases.get(key, 0):
            self._pending_project_close[key] = project
            return None
        return project

    def switch_project(self, project: Project, analysis_report=None) -> int:
        previous = self.project
        if previous is not None and previous is not project:
            self.projectAboutToChange.emit(previous)
        with self._project_lock:
            self._project_generation += 1
            self.project = project
            self.analysis_report = analysis_report
            self._pending_project_close.pop(id(project), None)
            close_project = self._defer_or_take_close(
                previous if previous is not project else None)
            generation = self._project_generation
        if close_project is not None:
            close_project.store.close()
        if analysis_report is not None:
            self.analysisChanged.emit(analysis_report)
        self.projectOpened.emit(project)
        return generation

    def set_analysis_report(self, report) -> None:
        self.analysis_report = report
        self.analysisChanged.emit(report)

    def close(self) -> None:
        previous = self.project
        if previous is not None:
            self.projectAboutToChange.emit(previous)
        self.local_model.stop()
        with self._project_lock:
            self._project_generation += 1
            self.project = None
            self.analysis_report = None
            close_project = self._defer_or_take_close(previous)
        if close_project is not None:
            close_project.store.close()

    @property
    def api(self) -> ApiConfig:
        return self.settings.api

    @property
    def profile(self) -> GameProfile:
        """当前项目的游戏档案（无项目时返回空档案）。"""
        if self.project is not None:
            return self.project.profile
        return GameProfile()
