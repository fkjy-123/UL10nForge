"""ffs 补翻 pending（库重建后剩余：恢复导入判定失败 206 + 未覆盖条目）。

复用 runner 翻译链路（与 tmp_backfill_faerie.py 同骨架）。translated 条目
不在 actionable 范围不重翻；pending 全部重试（新判定：方向检查 + 清洗后
的术语库）。
"""
import sys
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from hanhua.core.glossary import GlossaryStore  # noqa: E402
from hanhua.core.knowledge import KnowledgeBase  # noqa: E402
from hanhua.core.local_model import LocalModelManager  # noqa: E402
from hanhua.core.project import Project  # noqa: E402
from hanhua.core.prompts import build_system_prompt, collect_known_names  # noqa: E402
from hanhua.core.settings import SettingsStore  # noqa: E402
from hanhua.core.translator import create_client  # noqa: E402
from hanhua.core.batch_translator import BatchTranslator  # noqa: E402

REAL_USER_DIR = Path.home() / ".hanhua"
GAME = Path(r"D:\游戏\ffs-full-game-demo")
APP = Path.home() / ".hanhua_sweep"

from hanhua.core.models import TextEntry  # noqa: E402


def _entry_from_row(row: dict) -> TextEntry:
    meta = row.get("meta")
    import json as _json
    if isinstance(meta, str):
        try:
            meta = _json.loads(meta or "{}")
        except (_json.JSONDecodeError, TypeError):
            meta = {}
    meta = meta or {}
    reasons = meta.get("quality_reasons", [])
    return TextEntry(
        file_id=row["file_id"], key_path=row["key_path"],
        original=row["original"], translation=row.get("translation", ""),
        status=row.get("status", "pending"),
        locked=bool(row.get("locked", 0)),
        id=row.get("id"), meta=meta,
        confidence=str(meta.get("confidence", "medium")),
        quality_reasons=tuple(str(r) for r in reasons)
        if isinstance(reasons, list) else (),
    )


p = Project.open_game_dir(GAME, APP)
entries = [_entry_from_row(r) for r in p.store.get_entries()]
failed = [e for e in entries if e.status == "pending"]
print(f"待补翻（pending）：{len(failed)} 条 / 总 {len(entries)}")
if not failed:
    print("无 pending，跳过")
    sys.exit(0)

profile = p.profile
settings = SettingsStore(REAL_USER_DIR / "settings.json")
settings.load()
api = settings.api
manager = LocalModelManager(PROJECT_ROOT, startup_timeout=180)
runtime = manager.ensure_running(api)
api = replace(api, base_url=runtime.endpoint, api_key=runtime.api_key,
              model=runtime.model)
print(f"服务：{runtime.backend.upper()} · {runtime.endpoint}")

glossary = GlossaryStore(REAL_USER_DIR / "glossary.db")
glossary.init_schema()
glossary_prompt = glossary.format_for_prompt()
glossary_rows = glossary.list_all()
knowledge = KnowledgeBase(REAL_USER_DIR / "knowledge.db")
knowledge_prompt = knowledge.format_for_prompt()
knowledge_pairs = knowledge.format_reference_pairs()
knowledge.close()

collected_names = collect_known_names([str(e.original or "") for e in entries])
system = build_system_prompt(
    profile, glossary_prompt,
    known_names=glossary.known_names_for(collected_names),
    knowledge_lines=knowledge_prompt)
client = create_client(api)
lang = f"{profile.source_lang or 'auto'}→{profile.target_lang or 'zh-CN'}"
batch_size = max(1, int(api.local_batch_size))
translator = BatchTranslator(
    client, batch_size=batch_size, concurrency=runtime.parallel,
    memory=p.store, model=api.model, lang=lang, system_prompt=system,
    glossary=[(row["term"], row["translation"]) for row in glossary_rows]
    + knowledge_pairs)
stats = translator.run(entries, progress_cb=None)
print(f"补翻完成：{stats.done} 成功 · {stats.failed} 失败 · {stats.elapsed:.1f}s")
from hanhua.core.memory import ProjectStore
store = ProjectStore(p.store.db)
print("库状态:", dict((s, store.count(s)) for s in
                     ("translated", "failed", "skipped", "pending")))
