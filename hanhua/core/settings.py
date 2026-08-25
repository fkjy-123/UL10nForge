from __future__ import annotations
import json
from pathlib import Path

from hanhua.core.models import ApiConfig, FontConfig


# 四模型运行方式可选值：auto（hardware_planner 决策）/ cpu / gpu
MODEL_RUNTIME_CHOICES = ("auto", "cpu", "gpu")
_MODEL_RUNTIME_KINDS = ("translate", "review", "rerank", "embed")

# 在线 API 模式需要云端配置的模型（2026-08-14：翻译与审核走云端
# 大模型各自独立配置。2026-08-22 用户指令：检索（embedding）也提供
# 在线 API 卡片——云端 embedding 端点与本地 0.6B 等价；重排恒本地）
_API_KINDS = ("translate", "review", "embed")

# ApiConfig 字段过滤集（load 时只收合法字段，防旧 JSON 脏字段）
_API_FIELDS = tuple(ApiConfig.__dataclass_fields__)


class SettingsStore:
    """全局设置（JSON）：四模型 API 配置 + 字体 + 运行方式 + 最近项目。

    api_configs：在线模式四模型各自的 ApiConfig（kind → 配置）。
    self.api 恒为 api_configs["translate"] 的同一对象——翻译消费链
    （main_window/translate_page/translator）全部走 self.api，零改动；
    兼容旧 JSON 的顶层 api 字段（迁移为 translate 配置）。
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.api = ApiConfig()
        self.font = FontConfig()
        self.recent: list[str] = []
        # 四模型运行方式（环境设置页）：kind → auto/cpu/gpu。
        # rerank/embed 固定 CPU（fixed_cpu 硬约束），写入被忽略。
        self.model_runtime: dict[str, str] = {}
        self.api_configs: dict[str, ApiConfig] = {
            "translate": self.api,
            "review": ApiConfig(),
            "embed": ApiConfig(),
        }

    def load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return
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
        # 在线 API 配置：per-kind 读取；translate 优先 api_configs 新字段，
        # 旧 JSON 只有顶层 api → 迁移为 translate 配置（兼容老版本）
        raw_cfgs = data.get("api_configs", {})
        if isinstance(raw_cfgs, dict) and isinstance(
                raw_cfgs.get("translate"), dict):
            translate_raw = raw_cfgs["translate"]
        else:
            translate_raw = data.get("api", {})
        if not isinstance(translate_raw, dict):
            translate_raw = {}
        self.api = ApiConfig(**{k: v for k, v in translate_raw.items()
                                if k in _API_FIELDS})
        self.api_configs = {"translate": self.api}
        for kind in _API_KINDS[1:]:
            raw = raw_cfgs.get(kind) if isinstance(raw_cfgs, dict) else None
            if isinstance(raw, dict):
                self.api_configs[kind] = ApiConfig(
                    **{k: v for k, v in raw.items() if k in _API_FIELDS})
            else:
                self.api_configs[kind] = ApiConfig()
        # 旧 JSON 里的 rerank 在线配置（已弃用：恒本地）直接忽略。
        # 兼容旧版本：全局 profile 字段直接忽略（已废弃为项目级）

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "api": self.api.__dict__,
            "api_configs": {kind: cfg.__dict__
                            for kind, cfg in self.api_configs.items()},
            "font": self.font.__dict__,
            "recent": self.recent[:10],
            "model_runtime": dict(self.model_runtime),
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def api_config(self, kind: str) -> ApiConfig:
        """kind 的在线 API 配置（未知 kind 返回空配置，不炸调用方）。"""
        return self.api_configs.get(kind, ApiConfig())

    def set_api_config(self, kind: str, **fields) -> None:
        """更新 kind 的在线 API 配置（只收合法字段）并落盘。"""
        cfg = self.api_configs.get(kind)
        if cfg is None:
            return
        for key, value in fields.items():
            if key in _API_FIELDS:
                setattr(cfg, key, value)
        self.save()

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
