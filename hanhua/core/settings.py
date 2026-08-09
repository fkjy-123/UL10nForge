from __future__ import annotations
import json
from pathlib import Path

from hanhua.core.models import ApiConfig, FontConfig


class SettingsStore:
    """全局设置（JSON）：仅 API 配置 + 最近项目。游戏档案属于各项目。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.api = ApiConfig()
        self.font = FontConfig()
        self.recent: list[str] = []

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
        # 兼容旧版本：全局 profile 字段直接忽略（已废弃为项目级）

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "api": self.api.__dict__,
            "font": self.font.__dict__,
            "recent": self.recent[:10],
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_recent(self, game_dir: str):
        if game_dir in self.recent:
            self.recent.remove(game_dir)
        self.recent.insert(0, game_dir)
        self.save()
