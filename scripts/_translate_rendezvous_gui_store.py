# -*- coding: utf-8 -*-
"""复用 GUI 项目库翻译 Rendezvous 汉化版的 pending 条目（不重扫、不删库）。

与 GUI 完全同一套：Project.open_game_dir(汉化版目录, ~/.hanhua) 打开
GUI 库（200594be86），LocalModelManager + BatchTranslator 翻译 pending，
官方中文搬运，结果写回库（GUI 打开可见）。

用法：python scripts/_translate_rendezvous_gui_store.py
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from hanhua.core.project import Project  # noqa: E402
from hanhua.core.models import is_actionable_translation  # noqa: E402
from hanhua.core.local_model import LocalModelManager  # noqa: E402
from hanhua.core.batch_translator import BatchTranslator  # noqa: E402
from hanhua.core.glossary import GlossaryStore  # noqa: E402
from hanhua.core.knowledge import KnowledgeBase  # noqa: E402
from hanhua.core.agent_memory import AgentMemory  # noqa: E402
from hanhua.core.settings import SettingsStore  # noqa: E402
from hanhua.core.context_size import smart_context_size  # noqa: E402
from hanhua.core.prompts import build_system_prompt  # noqa: E402

REAL_USER_DIR = Path.home() / ".hanhua"
# 用户 GUI 打开的是桌面汉化版（库 ee2a8a224e）
GAME_DIR = Path(r"C:\Users\mingming\Desktop\Rendezvous.rar_汉化")
APP_DIR = REAL_USER_DIR


def main() -> int:
    print("═══ Rendezvous 桌面汉化版 GUI 库翻译 ═══")
    project = Project.open_game_dir(GAME_DIR, APP_DIR)
    print(f"游戏：{GAME_DIR}")
    print(f"项目库：{APP_DIR / 'projects'}")
    project.store.init_schema()

    settings = SettingsStore(REAL_USER_DIR / "settings.json")
    settings.load()
    api = settings.api

    manager = LocalModelManager(PROJECT_ROOT, startup_timeout=180)
    # 智能上下文（与 runner/GUI 同口径）
    if getattr(api, "local_context_auto", False):
        origins = [str(r.get("original") or "")
                   for r in project.store.get_entries()]
        _bs = max(1, int(api.local_batch_size))
        _ctx = smart_context_size(origins, batch_size=_bs,
                                  max_tokens=int(api.max_tokens))
        api = replace(api, local_context_size=_ctx)
        print(f"  [智能上下文] ctx={_ctx}（条目 {len(origins)} · 批量 {_bs}）")
    try:
        runtime = manager.ensure_running(api)
        api = replace(api, base_url=runtime.endpoint,
                      api_key=runtime.api_key, model=runtime.model)
        print(f"  服务就绪：{runtime.backend.upper()} · {runtime.endpoint}")
    except Exception as exc:
        print(f"[错误] 本地模型启动失败：{exc}")
        return 4

    from hanhua.core.prompts import collect_known_names
    from hanhua.core.translator import create_client

    glossary = GlossaryStore(REAL_USER_DIR / "glossary.db")
    glossary.init_schema()
    glossary_rows = glossary.list_all()
    knowledge = KnowledgeBase(REAL_USER_DIR / "knowledge.db")
    knowledge_pairs = knowledge.format_reference_pairs()
    agent_memory = AgentMemory(REAL_USER_DIR / "agent_memory.db")
    agent_memory.init_schema()
    agent_memory.session_reset()
    agent_pairs = agent_memory.reference_pairs()

    from hanhua.core.knowledge_retrieval import create_knowledge_retrieval
    knowledge_retrieval = create_knowledge_retrieval(REAL_USER_DIR, game="Rendezvous.rar_汉化")
    try:
        indexed0 = knowledge_retrieval.index_outbox()
    except Exception:
        indexed0 = 0

    from scripts.all_record_runner import _entry_from_row
    entries = [_entry_from_row(r) for r in project.store.get_entries()]
    profile = project.profile
    collected_names = collect_known_names(
        [str(e.original or "") for e in entries])
    system = build_system_prompt(profile, "")
    client = create_client(api)
    lang = f"{profile.source_lang or 'auto'}→{profile.target_lang or 'zh-CN'}"
    batch_size = max(1, int(api.local_batch_size))
    concurrency = runtime.parallel if api.mode == "local" else api.concurrency

    def _restart_translate_service() -> None:
        nonlocal runtime, client, api
        try:
            new_rt = manager.ensure_running(api)
            api = replace(api, base_url=new_rt.endpoint,
                          api_key=new_rt.api_key, model=new_rt.model)
            runtime = new_rt
            client = create_client(api)
            translator.client = client  # noqa: F821
            print(f"  [F42] 翻译服务已重启（{new_rt.endpoint}）", flush=True)
        except Exception as exc:
            print(f"  [F42] 翻译服务重启失败：{exc}", flush=True)

    translator = BatchTranslator(
        client, batch_size=batch_size, concurrency=concurrency,
        memory=project.store, model=api.model, lang=lang,
        system_prompt=system,
        service_restart=_restart_translate_service,
        glossary=[(row["term"], row["translation"])
                  for row in glossary_rows
                  if row.get("status", "active") == "active"]
                 + knowledge_pairs + agent_pairs,
        glossary_force=[(row["term"], row["translation"])
                        for row in glossary_rows
                        if row.get("status", "active") == "active"]
                       + knowledge_pairs,
        agent_memory=agent_memory, agent_game="Rendezvous.rar_汉化",
        context_store=knowledge_retrieval.context_store,
        context_game="Rendezvous.rar_汉化",
        vector_recall=knowledge_retrieval.vector_recall,
        knowledge=knowledge,
    )

    pending_count = sum(is_actionable_translation(e) for e in entries)
    print(f"  条目 {len(entries)} · 待翻译 {pending_count}"
          f" · 批量 {batch_size} · 并发 {concurrency}")
    stats = translator.run(entries, progress_cb=None)
    print(f"  完成：{stats.done} 条（记忆 {stats.from_memory}）"
          f" · 失败 {stats.failed} · 请求 {stats.requests}"
          f" · 耗时 {stats.elapsed:.1f}s")

    # 官方中文搬运（与 runner 同逻辑）
    from scripts.all_record_runner import (_apply_official_zh,
                                           _apply_ink_official_zh)
    try:
        moved = _apply_official_zh(entries)
        ink_moved = _apply_ink_official_zh(GAME_DIR, entries)
        if moved or ink_moved:
            project.store.batch_update_translation_results(entries)
            print(f"  官方中文搬运：CSV {moved} 条 · ink {ink_moved} 条",
                  flush=True)
    except Exception as exc:
        print(f"  [官方中文搬运] 失败：{exc}", flush=True)

    # 状态复核
    st = project.store.get_entries()
    from collections import Counter
    print("  最终状态:", dict(Counter(r["status"] for r in st)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
