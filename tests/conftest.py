"""共享测试工具。"""

import os
import sys

import time

# 允许测试文件 `from conftest import await_reload`（pytest 的 prepend
# 模式不保证把 tests/ 插入 sys.path——conftest 在收集前加载，这里显式注入）
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtTest import QTest


# #2 后台化页面各自的 in-flight 标志：ReviewPage._loading /
# TranslatePage._chips_loading / HomePage._dashboard_loading
_LOADING_FLAGS = ("_loading", "_chips_loading", "_dashboard_loading")


def await_reload(page, timeout_ms=8000):
    """#2：reload/计数刷新/数据带统计已后台化——轮询等待页面空闲。

    QTest.qWait 泵主线程事件循环，让 worker 的 finished 信号回主线程
    执行回调（模型填充/统计渲染发生在回调里，测试断言前必须等）。
    """
    deadline = time.monotonic() + timeout_ms / 1000.0
    busy = lambda: any(getattr(page, flag, False) for flag in _LOADING_FLAGS)
    while busy() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert not busy(), f"后台任务超时（{timeout_ms}ms）"
