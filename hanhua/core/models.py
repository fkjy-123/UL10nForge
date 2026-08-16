from __future__ import annotations
import json
from dataclasses import dataclass, field

STATUS_PENDING = "pending"
STATUS_TRANSLATED = "translated"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_BLOCKED = "blocked"   # 语义审核终态：重译/再审未收敛，需人工复核


@dataclass
class TextEntry:
    file_id: str
    key_path: str          # 格式内定位路径：json 路径 a/b/3/text、xml /root/x、csv 行号、txt 行号
    original: str
    translation: str = ""
    status: str = STATUS_PENDING
    locked: bool = False
    id: int | None = None
    meta: dict = field(default_factory=dict)   # 格式相关写回元数据
    confidence: str = "medium"
    quality_reasons: tuple[str, ...] = ()


def is_actionable_translation(entry: TextEntry) -> bool:
    """Return whether this entry belongs to an automatic run scope.

    pending 与 failed 都算：翻译失败的条目不永久卡死，下次运行会重试
    （failed 卡死会让「质量门失败原因：untranslated_text N」统计残留）。
    """
    disposition = entry.meta.get("disposition")
    if disposition is not None:
        # Scanned provenance is authoritative.  Legacy rows without this field
        # retain the role-based compatibility path below.
        if str(disposition) != "translate":
            return False
        role = "display"
    else:
        role = str(entry.meta.get("role", "display"))
    confidence = str(entry.meta.get("confidence", entry.confidence))
    return (entry.status in (STATUS_PENDING, STATUS_FAILED)
            and not entry.locked
            and role not in {"structural", "code", "key"}
            and (confidence != "low"
                 or entry.meta.get("confidence_promoted") is True))


# 审核待处理终态（Phase A 统一落 review_outcome；C6 时代遗留
# review_issue 字段仍兼容）。审校页「待审核」胶囊与概览页「待人工」
# 统计共用此口径（2026-08-15 数字关系统一：此前两处各算各的，显示
# 互相矛盾）。
REVIEW_PENDING_OUTCOMES = frozenset(
    {"NEEDS_REVISION", "BLOCKED", "REVIEW_ERROR"})


def needs_review(meta: dict) -> bool:
    """待审核判定：review_outcome 终态未收敛，或遗留 review_issue。

    与审校页筛选「待审核」同源（入口统一在 models，两页共用）。"""
    return (meta.get("review_outcome") in REVIEW_PENDING_OUTCOMES
            or bool(meta.get("review_issue")))


def entry_from_row(row: dict) -> TextEntry:
    """DB 行 → TextEntry：首页/翻译页/审校页共用的单一口径。

    此前三页各自复制一份解析（meta 字符串/字典兼容），口径漂移是
    「待翻译计数不一致」的根源（#2/#8）：审校页曾用裸 status 计数，
    把 low 置信度留档条目（引擎消息/噪音，不可自动翻译）算进待翻译。
    """
    raw_meta = row.get("meta", {})
    if isinstance(raw_meta, str):
        try:
            meta = json.loads(raw_meta)
        except (json.JSONDecodeError, TypeError):
            meta = {}
    else:
        meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
    reasons = meta.get("quality_reasons", [])
    return TextEntry(
        file_id=row["file_id"], key_path=row["key_path"],
        original=row["original"], translation=row.get("translation", ""),
        status=row.get("status", "pending"), locked=bool(row.get("locked", 0)),
        id=row.get("id"), meta=meta,
        confidence=str(meta.get("confidence", "medium")),
        quality_reasons=tuple(str(reason) for reason in reasons)
        if isinstance(reasons, list) else (),
    )


@dataclass
class GameProfile:
    game_name: str = ""
    genre: str = ""
    world_setting: str = ""
    tone_notes: str = ""
    style_guide: str = ""
    # #10：Style/Personalization——用户自定义翻译风格要求（游戏本地化
    # 角色行为边界之外的个性化指令）。空 = 使用内置默认角色；非空 →
    # 以【个性化风格要求】块注入 system prompt 并优先于内置文风。
    prompt_style: str = ""
    source_lang: str = "auto"    # auto / English / 日本語 / 한국어 / ...
    target_lang: str = "zh-CN"


@dataclass
class ApiConfig:
    mode: str = "local"           # api / local（默认本地离线——发行版
    # 开箱即本地四模型，无需任何云端配置；在线 API 是可选模式）
    provider: str = "openai"     # openai 兼容 / anthropic 原生
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096
    concurrency: int = 6
    batch_size: int = 40
    timeout: float = 120.0
    local_model_path: str = ""
    local_server_path: str = ""
    local_gpu_layers: int = -1    # -1 = 尽可能全部卸载到 GPU，0 = CPU
    local_context_size: int = 8192
    local_context_auto: bool = False  # 智能上下文（按文本统计自动计算，2026-08-16 用户指令）
    local_port: int = 0           # 0 = 自动选择环回空闲端口
    local_keep_alive: bool = True
    local_concurrency: int = 0  # 0 = GPU 4 / CPU 1 automatic default
    local_batch_size: int = 8   # persistence/progress chunk, not nested workers
    ai_review_enabled: bool = True        # 翻译后自动语义审核（§68 开关）
    ai_review_strategy: str = "balanced"  # fast / balanced / strict → 送审率


@dataclass
class FontConfig:
    enabled: bool = True
    filename: str = "SimplifiedChinese/SourceHanSansSC-Regular.otf"
    #: TMP 替换字体的粗细档位：heavy（粗）/ medium（中）/ thin（细）
    weight: str = "medium"


@dataclass
class GlossaryEntry:
    term: str
    translation: str
    category: str = "术语"       # 人名/地名/专名/术语
    note: str = ""
    id: int | None = None


@dataclass
class TranslateStats:
    total: int = 0
    done: int = 0
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    failed: int = 0
    from_memory: int = 0
    elapsed: float = 0.0    # 本轮 run 耗时（秒），P3 吞吐统计

    @property
    def rate_per_minute(self) -> float:
        """吞吐：已完成条目数 × 60 / 耗时秒（耗时 0 或未完成时为 0）。"""
        if self.elapsed <= 0:
            return 0.0
        return self.done * 60.0 / self.elapsed


@dataclass(frozen=True)
class WriteRejection:
    """One write-ready locator that the writer explicitly declined."""

    locator: str
    reason: str


@dataclass(frozen=True)
class WriteOutcome:
    """Immutable, auditable accounting for one writer run."""

    attempted: int
    written: int
    rejected: tuple[WriteRejection, ...] = ()
    truncated: int = 0          # 写入成功但被固定容量截断的条目数
    logic_reverted: int = 0     # 逻辑审计主动回退（保留原文防断链）——
                                # 终态之一，不是写失败：不触发对象闸门阻断

    def __post_init__(self):
        if self.attempted != self.written + len(self.rejected) + self.logic_reverted:
            raise ValueError(
                "writer outcome must satisfy attempted = written + rejected"
                " + logic_reverted")
        if self.truncated < 0 or self.truncated > self.written:
            raise ValueError(
                "writer outcome truncated must be within [0, written]")
