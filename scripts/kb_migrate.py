"""知识库体系升级迁移脚本（2026-08-11，§0.4 知识库体系搭建）。

把 2026-08-11 前的知识库升级到六库体系：
1. schema 升级：knowledge_items 加 source/game/created_at/updated_at 列
   （KnowledgeStore.init_schema 自带 ALTER，兼容旧库不重建）
2. fail_case 88 条：管道 note（FAIL-|键:值|）→ 结构化 JSON + fail_no 唯一化
3. text 25 条：补 action 字段（translate/keep）+ 溯源（note 前缀 manual:/
   auto: 拆到 source 列）
4. 输出六库统计验证

幂等：可重复执行，无副作用。
用法：python scripts/kb_migrate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hanhua.core.knowledge import KnowledgeBase  # noqa: E402

DB = Path.home() / ".hanhua" / "knowledge.db"

# text 域 kind → 默认 action（六库文本规则库 §0.4.3：action=translate/keep/skip）
_TEXT_KIND_ACTION = {
    # 形态 kind（有译名/须译中文 → translate）
    "spaced_action": "translate",      # * Y A W N * → * 哈欠 *
    "uppercase_action": "translate",   # TOSS TRASH → 丢垃圾
    "interaction_prompt": "translate", # Press E to open → 按 E 打开
    "multilingual_source": "translate",  # 日语/西语/俄语源须译中文
    "loaned_word": "translate",        # encore → 安可（音游借词）
    "platform_name": "keep",           # itch/discord 保留原文（专名）
    "proper_name": "keep",             # hiss pop collection 保留（署名专名）
}


def migrate_text_actions(kb: KnowledgeBase) -> tuple[int, int]:
    """text 域补齐 action 与溯源（幂等：已有 action 的跳过）。"""
    if kb.store is None:
        return 0, 0
    filled = skipped = 0
    with kb.store._lock:
        for r in kb.store.list_by_domain("text"):
            action = str(r.get("action") or "")
            source = str(r.get("source") or "")
            note = str(r["note"])
            # note 前缀溯源（manual:game:xxx / auto:game:xxx）拆到 source 列
            if not source:
                m = __import__("re").match(
                    r"^(manual|auto):([^:]+):", note)
                if m:
                    source = m.group(1)
            if not action:
                action = _TEXT_KIND_ACTION.get(r["kind"], "translate")
            if action != r.get("action") or source != r.get("source"):
                kb.store.conn.execute(
                    "UPDATE knowledge_items SET action=?, source=? WHERE id=?",
                    (action, source, r["id"]))
                filled += 1
            else:
                skipped += 1
        kb.store.conn.commit()
    return filled, skipped


def main() -> int:
    kb = KnowledgeBase(DB)
    # 1. schema 升级（ALTER 兼容旧库）
    kb.store.init_schema()
    # 2. fail_case 管道 → JSON + fail_no 唯一化
    migrated, already = kb.migrate_legacy_notes()
    renumbered = kb.renumber_cases()
    # 3. text 域 action + 溯源
    filled, skipped = migrate_text_actions(kb)
    # 4. 六库统计验证
    print(f"fail_case 迁移：管道→JSON {migrated} 条（原已 JSON {already}）"
          f" · fail_no 重编号 {renumbered} 条")
    print(f"text 域补齐：action/溯源 {filled} 条（已有 {skipped}）")
    print("\n六库统计（内置种子 + 持久库）：")
    for lib, st in kb.library_stats().items():
        print(f"  {lib:20s} {st['count']:3d} 条 · 累计命中 {st['hits']:4d}"
              f" · kind: {', '.join(f'{k}×{v}' for k, v in st['kinds'].items())}")
    kb.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
