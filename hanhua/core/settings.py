from __future__ import annotations
import json
from pathlib import Path

from hanhua.core.models import ApiConfig, FontConfig


# 四模型运行方式可选值：auto（hardware_planner 决策）/ cpu / gpu
MODEL_RUNTIME_CHOICES = ("auto", "cpu", "gpu")
_MODEL_RUNTIME_KINDS = ("translate", "review", "rerank", "embed")


class SettingsStore:
    """全局设置（JSON）：API 配置 + 字体 + 四模型运行方式 + 最近项目。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.api = ApiConfig()
        self.font = FontConfig()
        self.recent: list[str] = []
        # 四模型运行方式（环境设置页）：kind → auto/cpu/gpu。
        # rerank/embed 固定 CPU（fixed_cpu 硬约束），写入被忽略。
        self.model_runtime: dict[str, str] = {}

    def load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return
        self.api = ApiConfig(**{k: v for k, v in data.get("api", {}).items()
                                if k in ApiConfig.__dataclass_fields__})
        self.font = FontConfig(**{k: v for k, v in data.get("font", {}).items()
                                  if k in FontConfig.__dataclass_fields__})
        self.recent = [r for r in data.get("recent", []) if isinstance(r, str)][:10]
        # 四模型运行方式：只收合法 kind/取值；固定 CPU 模型强制 auto
        runtime = data.get("model_runtime", {})
        self.model_runtime = {
            str(kind): str(choice)
            for kind, choice in runtime.items()
            if kind in _MODEL_RUNTIME_KINDS
            and str(choice) in MODEL_RUNTIME_CHOICES
        }
        # 兼容旧版本：全局 profile 字段直接忽略（已废弃为项目级）

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "api": self.api.__dict__,
            "font": self.font.__dict__,
            "recent": self.recent[:10],
            "model_runtime": dict(self.model_runtime),
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def model_runtime_choice(self, kind: str) -> str:
        """kind 的运行方式（缺省 auto）；固定 CPU 模型强制 auto。"""
        if kind in ("rerank", "embed"):
            return "auto"
        choice = self.model_runtime.get(kind, "auto")
        return choice if choice in MODEL_RUNTIME_CHOICES else "auto"

    def set_model_runtime(self, kind: str, choice: str) -> None:
        if kind not in _MODEL_RUNTIME_KINDS:
            return
        if choice not in MODEL_RUNTIME_CHOICES:
            return
        if kind in ("rerank", "embed"):
            return  # fixed_cpu 硬约束
        if choice == "auto":
            self.model_runtime.pop(kind, None)
        else:
            self.model_runtime[kind] = choice
        self.save()

    def add_recent(self, game_dir: str):
        if game_dir in self.recent:
            self.recent.remove(game_dir)
        self.recent.insert(0, game_dir)
        self.save()
