from __future__ import annotations
import json
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from dataclasses import replace
from typing import Callable

from hanhua.core.engine_strings import (PHYSICAL_KEY_NAMES_CASEFOLD,
                                        interaction_input_events,
                                        interaction_input_tokens)
from hanhua.core.placeholders import (DISPLAY_WORDS, SAFE_KEEPERS,
                                      self_heal_format_tags)
from hanhua.core.local_model import sanitize_exception
from hanhua.core.models import (TextEntry, TranslateStats, STATUS_FAILED,
                                STATUS_TRANSLATED, is_actionable_translation)
from hanhua.core.protected_spans import (protected_slot_parts,
                                         semantic_target_text)
from hanhua.core.prompts import build_batch_user_prompt
from hanhua.core.quality import (_CJK, has_independent_lower_word,
                                 is_camel_tech_abbreviation,
                                 is_lorem_ipsum_placeholder,
                                 source_term_applies,
                                 validate_translation_quality)
from hanhua.core.translator import (BUILTIN_UI_REFERENCES,
                                    BUILTIN_UI_SOURCE_TERMS, BaseClient,
                                    extract_json_array,
                                    extract_json_array_fallback,
                                    merge_translation_references)


# 译文残留英文检测（target_script_mismatch）：
# 连续短语 = 两个 3+ 字母英文词之间有非字母非中文的间隔（明确半翻）。
# 注意间隔必须「非空且非纯字母」——否则单词 Escape/YouTube 会被正则回溯
# 拆成 Esc+ape 假匹配。'Escape会退出游戏'（间隔只有中文）不算短语。
_ENGLISH_PHRASE = re.compile(
    r"[A-Za-z]{3,}[^A-Za-z㐀-鿿豈-﫿]+[A-Za-z]{3,}")
_ENGLISH_WORD = re.compile(r"[A-Za-z]{3,}")
_AT_USER = re.compile(r"@[\w.-]+")
# @用户名紧邻的 2-4 字母显示名（"fie (@zkfie" 末尾的 fie）→ 作者名豁免
_DISPLAY_NAME_BEFORE_AT = re.compile(r"[A-Za-z]{2,4}(?=\s*[\(\s,]*$)")
# UI 词典词（casefold）：模型保留这些词 = 半翻失败；大写专名（Windows/CBS）豁免
_DISPLAY_WORDS_CASEFOLD = {word.casefold() for word in DISPLAY_WORDS}
# 问候语：译文首行保留英文问候（Hello, there. / Hi!）是本地化惯例，
# 其余已译为中文时豁免（mimic-search/soul-delivery 真实样本）
_GREETING_WORDS = {"hello", "hi", "hey"}
# 内置 UI 术语（BUILTIN_UI_SOURCE_TERMS）：模型回显 = 未翻译（SFX/Quit/Volume…）
_BUILTIN_UI_TERMS_CASEFOLD = {
    str(term).casefold() for term in BUILTIN_UI_SOURCE_TERMS}
# 聊天/控制台命令（"/kick" 引号包裹 或 /give 独立词）：游戏命令保留原文是
# 正确行为（Slendergus 真实样本）→ 从英文残留判定中移除
_SLASH_COMMAND = re.compile(
    r"[\"']/[A-Za-z][A-Za-z0-9_/-]*[\"']"
    r"|(?:^|(?<=\s))/[A-Za-z][A-Za-z0-9_-]*")


def _entry_id(e: TextEntry) -> str:
    return f"{e.key_path}@{e.file_id}"


def _split_translation_segments(text: str) -> tuple[str, list[str], list[str]]:
    """拆分为可逐段翻译的片段（返回 (前缀, 片段, 分隔符)）。

    换行优先（保留换行符与字面 \\n）；无换行的长单段文本按句子边界拆
    （保留标点后空白）—— 长 prompt 超出 ctx 时模型回显原文是稳定行为
    （untranslated_text），短句回显概率极低，拆句逐段翻译后拼接。
    空段（空行/纯空白）并入**前一个**非空段的分隔符原位保留，不单独
    发请求；前导空白作为前缀返回（挂在译文开头）。
    """
    parts = re.split(r"(\\n|\r\n|\r|\n)", text)
    if len(parts) > 1:
        prefix = ""
        segments: list[str] = []
        separators: list[str] = []
        for i in range(0, len(parts) - 1, 2):
            piece, separator = parts[i], parts[i + 1]
            if piece.strip():
                segments.append(piece)
                separators.append(separator)
            elif segments:
                separators[-1] += piece + separator
            else:
                prefix += piece + separator
        if parts[-1].strip():
            segments.append(parts[-1])
            separators.append("")
        elif segments:
            separators[-1] += prefix + parts[-1]
        elif not segments:
            prefix += parts[-1]
        return prefix, segments, separators
    pieces = re.split(r"(?<=[.!?。！？])(\s+)", text)
    prefix = ""
    segments, separators = [], []
    for i in range(0, len(pieces), 2):
        piece = pieces[i]
        separator = pieces[i + 1] if i + 1 < len(pieces) else ""
        if piece.strip():
            segments.append(piece)
            separators.append(separator)
        else:
            prefix += piece + separator
    return prefix, segments, separators


def _auto_translatable(entry: TextEntry) -> bool:
    return is_actionable_translation(entry)


class BatchTranslator:
    """批量翻译引擎：记忆命中 → 分批并发 → 占位符校验 → 结果落库。

    容错：批量 JSON 解析失败时降级逐条并发重试（短超时），且每条完成即回调进度，
    避免"整批解析失败 → 串行 25 条 × 长超时"导致的长时间无进度卡死。
    """

    FALLBACK_TIMEOUT = 45.0   # 降级逐条时的单条超时

    def __init__(self, client: BaseClient, batch_size: int = 25, concurrency: int = 3,
                 memory=None, model: str = "", lang: str = "→zh-CN",
                 system_prompt: str = "", placeholder_check: bool = True,
                 glossary=(), cancellation_event=None):
        self.client = client
        self.batch_size = max(1, batch_size)
        self.concurrency = max(1, concurrency)
        self.memory = memory
        self.model = model
        self.lang = lang
        self.system_prompt = system_prompt
        self.placeholder_check = placeholder_check
        self.glossary = tuple(glossary)
        self.cancellation_event = cancellation_event
        self.references = merge_translation_references(self.glossary)
        self._stop = threading.Event()
        self._metrics_lock = threading.Lock()
        self._consistency_lock = threading.Lock()
        self._requests = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._consistent_translations: dict[tuple[str, str], str] = {}

    def stop(self):
        self._stop.set()
        if self.cancellation_event is not None:
            self.cancellation_event.set()

    def _is_cancelled(self) -> bool:
        return (self._stop.is_set()
                or (self.cancellation_event is not None
                    and self.cancellation_event.is_set()))

    def run(self, entries: list[TextEntry], progress_cb: Callable | None = None,
            context_window: int = 1) -> TranslateStats:
        self._stop.clear()
        cancelled = self.cancellation_event
        with self._metrics_lock:
            self._requests = 0
            self._input_tokens = 0
            self._output_tokens = 0
        with self._consistency_lock:
            self._consistent_translations.clear()
        run_scope = [entry for entry in entries if _auto_translatable(entry)]
        stats = TranslateStats(total=len(run_scope))
        started_at = time.perf_counter()

        def finalize_elapsed():
            """所有返回路径统一记录耗时（P3 吞吐统计）。"""
            stats.elapsed = time.perf_counter() - started_at
        changed: list[TextEntry] = []
        new_memory: list[tuple] = []

        def flush():
            if not self.memory:
                return
            self.memory.batch_update_translation_results(changed)
            changed.clear()
            self.memory.batch_add_memory(new_memory)
            new_memory.clear()

        def emit_stats():
            """降级逐条期间实时上报进度（重算当前计数）。"""
            stats.done = sum(
                1 for entry in run_scope
                if entry.status == STATUS_TRANSLATED)
            stats.failed = sum(
                1 for entry in run_scope if entry.status == STATUS_FAILED)
            with self._metrics_lock:
                stats.requests = self._requests
                stats.input_tokens = self._input_tokens
                stats.output_tokens = self._output_tokens
            if progress_cb:
                progress_cb(replace(stats))

        # 1) 翻译记忆命中
        if self.memory:
            pending = [e for e in entries if _auto_translatable(e)]
            hits = self.memory.get_memory_hits([e.original for e in pending], self.model, self.lang)
            for e in pending:
                if e.original in hits:
                    good = self._apply_quality(e, hits[e.original])
                    e.status = STATUS_TRANSLATED if good else STATUS_FAILED
                    if good:
                        e.status = STATUS_TRANSLATED
                        stats.done += 1
                        stats.from_memory += 1
                    else:
                        rejected = list(e.quality_reasons)
                        self.memory.remove_memory(e.original, self.model, self.lang)
                        e.translation = ""
                        e.status = "pending"
                        e.quality_reasons = ()
                        e.meta["memory_rejected_reasons"] = rejected
                        e.meta.pop("quality_passed", None)
                        e.meta.pop("quality_reasons", None)
                    changed.append(e)
            flush()
            if progress_cb:
                progress_cb(replace(stats))

        # 2) 分批并发翻译
        pending = [e for e in entries if _auto_translatable(e)]
        grouped: dict[tuple[str, str], list[TextEntry]] = {}
        for entry in pending:
            key = (entry.original, str(entry.meta.get("role", "display")))
            grouped.setdefault(key, []).append(entry)
        representatives = [group[0] for group in grouped.values()]
        group_by_representative = {
            id(group[0]): group for group in grouped.values()
        }
        if cancelled is not None and cancelled.is_set():
            finalize_elapsed()
            return stats
        native_client = callable(getattr(self.client, "translate_text", None))
        if native_client:
            completed_representatives = 0

            def consume_native_result(
                    result: tuple[TextEntry, str, bool]) -> None:
                nonlocal completed_representatives
                en, tr, good = result
                candidate = en.translation or tr
                for index, member in enumerate(
                        group_by_representative[id(en)]):
                    member_good = (
                        good if index == 0
                        else (self._apply_quality(member, candidate)
                              if candidate else False)
                    )
                    if not candidate and index > 0:
                        self._copy_failure_state(en, member)
                    if member_good and member.translation:
                        member.status = STATUS_TRANSLATED
                        stats.done += 1
                    else:
                        member.status = STATUS_FAILED
                        stats.failed += 1
                    changed.append(member)
                if good and en.translation and self.memory:
                    new_memory.append(
                        (en.original, en.translation, self.model, self.lang))
                completed_representatives += 1
                if completed_representatives % self.batch_size == 0:
                    flush()
                    emit_stats()

            self._chat_each(
                representatives, context_window,
                result_cb=consume_native_result,
            )
            flush()
            emit_stats()
            finalize_elapsed()
            return stats

        batches = [
            representatives[i:i + self.batch_size]
            for i in range(0, len(representatives), self.batch_size)
        ]
        pool = ThreadPoolExecutor(max_workers=self.concurrency)
        batch_iter = iter(batches)
        futures = {}
        try:
            for batch in batch_iter:
                futures[pool.submit(self._translate_batch, batch, context_window, emit_stats)] = batch
                if len(futures) >= self.concurrency:
                    break
            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                if self._stop.is_set() or (cancelled is not None and cancelled.is_set()):
                    for pending_future in futures:
                        pending_future.cancel()
                    break
                for fut in done:
                    b = futures.pop(fut)
                    if self._stop.is_set() or (cancelled is not None and cancelled.is_set()):
                        break
                    try:
                        per_batch = fut.result()
                    except Exception as exc:  # noqa: BLE001 单批失败隔离
                        for en in b:
                            for member in group_by_representative[id(en)]:
                                self._mark_request_failed(member, exc)
                                stats.failed += 1
                                changed.append(member)
                        flush()
                        emit_stats()
                        if not self._stop.is_set() and not (cancelled is not None and cancelled.is_set()):
                            try:
                                next_batch = next(batch_iter)
                            except StopIteration:
                                pass
                            else:
                                futures[pool.submit(self._translate_batch, next_batch, context_window, emit_stats)] = next_batch
                        continue
                    for en, tr, good in per_batch:
                        candidate = en.translation or tr
                        for index, member in enumerate(group_by_representative[id(en)]):
                            member_good = good if index == 0 else (self._apply_quality(member, candidate) if candidate else False)
                            if not candidate and index > 0:
                                self._copy_failure_state(en, member)
                            if member_good and member.translation:
                                member.status = STATUS_TRANSLATED
                                stats.done += 1
                            else:
                                member.status = STATUS_FAILED
                                stats.failed += 1
                            changed.append(member)
                        if good and en.translation and self.memory:
                            new_memory.append((en.original, en.translation, self.model, self.lang))
                    flush()
                    emit_stats()
                    if not self._stop.is_set() and not (cancelled is not None and cancelled.is_set()):
                        try:
                            next_batch = next(batch_iter)
                        except StopIteration:
                            pass
                        else:
                            futures[pool.submit(self._translate_batch, next_batch, context_window, emit_stats)] = next_batch
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
        emit_stats()
        finalize_elapsed()
        return stats

    def _translate_batch(self, batch: list[TextEntry], context_window: int,
                         per_item_cb: Callable[[], None] | None = None
                         ) -> list[tuple[TextEntry, str, bool]]:
        """批量翻译一条批次，含两级容错：
        1) 整批 JSON 解析失败 → 逐条降级重试（单条输出错乱概率低）
        2) 批内部分失败（缺条/占位符校验失败）→ 仅对失败子集逐条重试一次
        """
        if self._is_cancelled():
            return []
        if callable(getattr(self.client, "translate_text", None)):
            return self._chat_each(batch, context_window, per_item_cb)
        results = self._chat_batch(batch, context_window)
        if self._is_cancelled():
            return []
        segmented_attempts: set[int] = set()
        repaired_results: list[tuple[TextEntry, str, bool]] = []
        for entry, translation, good in results:
            if (not good and self._allows_fallback_retry(entry)
                    and self._needs_protected_repair(entry)):
                segmented_attempts.add(id(entry))
                repaired_results.append(
                    self._repair_protected_chat_translation(entry))
            elif (not good and self._allows_fallback_retry(entry)
                    and ({"newline_mismatch", "line_content_mismatch",
                          "untranslated_text"} & set(entry.quality_reasons))):
                segmented_attempts.add(id(entry))
                repaired_results.append(
                    self._repair_multiline_chat_translation(entry))
            else:
                repaired_results.append((entry, translation, good))
        results = repaired_results
        failed = [e for e, tr, good in results if not good]
        retryable = [
            e for e in failed
            if id(e) not in segmented_attempts and self._allows_fallback_retry(e)
        ]
        if retryable and len(retryable) == len(batch):
            # 整批解析失败 → 全部逐条降级
            return self._chat_each(retryable, context_window, per_item_cb)
        if retryable:
            # 部分失败 → 仅重试失败子集（逐条）
            sub = self._chat_each(retryable, context_window, per_item_cb)
            sub_map = {_entry_id(e): (tr, good) for e, tr, good in sub}
            merged: list[tuple[TextEntry, str, bool]] = []
            for e, tr, good in results:
                if not good:
                    tr, good = sub_map.get(_entry_id(e), (tr, good))
                merged.append((e, tr, good))
            return merged
        return results

    @staticmethod
    def _allows_fallback_retry(entry: TextEntry) -> bool:
        role = str(entry.meta.get("role", "display"))
        disposition = str(entry.meta.get("disposition", ""))
        return (role not in {"proper_name", "structural", "code", "key"}
                and disposition not in {
                    "preserve", "proper_name", "structural", "code", "key",
                })

    @staticmethod
    def _needs_protected_repair(entry: TextEntry) -> bool:
        reasons = set(entry.quality_reasons)
        has_protected_slot = any(
            protected for protected, _part in protected_slot_parts(entry.original))
        return bool(
            {"rich_text_mismatch", "input_token_mismatch"} & reasons
            or ("placeholder_mismatch" in reasons
                and not ({"newline_mismatch", "line_content_mismatch"}
                         & reasons))
            or (has_protected_slot
                and {"target_script_mismatch", "untranslated_text"} & reasons)
        )

    def _chat_batch(self, batch: list[TextEntry], context_window: int
                    ) -> list[tuple[TextEntry, str, bool]]:
        if self._is_cancelled():
            return []
        items = [self._build_item(batch, i, context_window) for i in range(len(batch))]
        user = self._build_chat_user_prompt(items)
        try:
            content, usage = self.client.chat(
                self.system_prompt, [{"role": "user", "content": user}])
        except Exception:
            self._record_usage(None)
            raise
        self._record_usage(usage)
        if self._is_cancelled():
            return []
        arr = self._response_array(content, batch[0] if len(batch) == 1 else None)
        if arr is None:
            for entry in batch:
                self._mark_failed(entry, "invalid_response", raw_output=content)
            return [(e, "", False) for e in batch]
        return self._validate(batch, arr)

    def _chat_each(self, batch: list[TextEntry], context_window: int,
                   per_item_cb: Callable[[], None] | None = None,
                   result_cb: Callable[
                       [tuple[TextEntry, str, bool]], None] | None = None,
                   ) -> list[tuple[TextEntry, str, bool]]:
        """逐条降级翻译：并发执行 + 短超时 + 每条完成回调（UI 实时进度）。"""
        if not batch:
            return []
        config = getattr(self.client, "config", None)   # 测试 client 可能无 config
        old_timeout = getattr(config, "timeout", None) if config else None
        if old_timeout:
            config.timeout = min(old_timeout, self.FALLBACK_TIMEOUT)

        def work(i: int) -> tuple[TextEntry, str, bool]:
            e = batch[i]
            original_state = (
                e.translation, e.status, e.quality_reasons, dict(e.meta))

            def restore_original_state() -> None:
                (e.translation, e.status, e.quality_reasons, e.meta) = original_state
            if self._is_cancelled():
                return e, "", False
            try:
                native_translate = getattr(self.client, "translate_text", None)
                if callable(native_translate):
                    target_lang = self.lang.rsplit("→", 1)[-1] or "zh-CN"
                    content, usage = native_translate(
                        e.original, target_lang, self.references)
                else:
                    user = self._build_chat_user_prompt([
                        self._build_item(batch, i, context_window, single=True)])
                    content, usage = self.client.chat(
                        self.system_prompt, [{"role": "user", "content": user}])
            except Exception as exc:  # noqa: BLE001
                self._record_usage(None)
                self._mark_request_failed(e, exc)
                return e, "", False
            self._record_usage(usage)
            if self._is_cancelled():
                return e, "", False
            if callable(getattr(self.client, "translate_text", None)):
                arr = [{"id": _entry_id(e), "translation": content}]
            else:
                arr = self._response_array(content, e)
            if arr is None:
                self._mark_failed(e, "invalid_response", raw_output=content)
                return e, "", False
            sub = self._validate([e], arr)
            if (callable(getattr(self.client, "translate_text", None))
                    and not sub[0][2]
                    and self._allows_fallback_retry(e)
                    and self._needs_protected_repair(e)):
                repaired = self._repair_protected_translation(
                    e, native_translate, target_lang, previous=sub[0][1])
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                if repaired is not None and repaired[2]:
                    return repaired
            if (callable(getattr(self.client, "translate_text", None))
                    and not sub[0][2]
                    and self._allows_fallback_retry(e)
                    and ({"newline_mismatch", "line_content_mismatch",
                          "untranslated_text"} & set(e.quality_reasons))):
                repaired = self._repair_multiline_translation(
                    e, native_translate, target_lang)
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                if repaired is not None:
                    return repaired
            if (callable(getattr(self.client, "translate_text", None))
                    and not sub[0][2]
                    and self._is_actionable_ui_retry(e)):
                if self._is_cancelled():
                    return e, "", False
                try:
                    retry_content, retry_usage = native_translate(
                        e.original, target_lang, self.references)
                except Exception as exc:  # noqa: BLE001
                    self._record_usage(None)
                    self._mark_request_failed(e, exc)
                    return e, "", False
                self._record_usage(retry_usage)
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                if isinstance(retry_content, str):
                    retry_good = self._apply_quality(e, retry_content)
                    return e, retry_content, retry_good
                self._mark_failed(e, "invalid_response",
                                  raw_output=str(retry_content))
                return e, "", False
            return sub[0]

        try:
            results: list[tuple[TextEntry, str, bool]] = [None] * len(batch)  # type: ignore[list-item]
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                futures = {pool.submit(work, i): i for i in range(len(batch))}
                for fut in as_completed(futures):
                    if self._stop.is_set() or (self.cancellation_event is not None and self.cancellation_event.is_set()):
                        break
                    idx = futures[fut]
                    try:
                        results[idx] = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        self._mark_request_failed(batch[idx], exc)
                        results[idx] = (batch[idx], "", False)
                    if result_cb:
                        result_cb(results[idx])
                    elif per_item_cb:
                        per_item_cb()
            return [r for r in results if r is not None]
        finally:
            if old_timeout and config:
                config.timeout = old_timeout

    @staticmethod
    def _is_actionable_ui_retry(entry: TextEntry) -> bool:
        if not ({"untranslated_text", "target_script_mismatch",
                 "input_token_mismatch"}
                & set(entry.quality_reasons)):
            return False
        role = str(entry.meta.get("role", "display"))
        disposition = str(entry.meta.get("disposition", ""))
        if role not in {"ui", "display"}:
            return False
        if disposition in {
                "preserve", "structural", "proper_name", "code", "key"}:
            return False
        return (role == "ui" or disposition == "translate"
                or entry.original.strip().casefold() in BUILTIN_UI_SOURCE_TERMS)

    def _build_chat_user_prompt(self, items: list[dict]) -> str:
        # P1：术语按命中注入——references 段只保留内置 UI 术语（恒定小
        # 集合，跨批一致性锚点）+ 批内命中的用户术语；未命中术语不注入
        # （术语表数百条时全量注入会稀释注意力、膨胀上下文）。
        # 与 [术语命中] 行（强制语气）互补：references 是参考，命中行是硬约束。
        batch_sources = " ".join(str(it.get("text", "")) for it in items)
        builtin_sources_cf = {s.casefold() for s, _ in BUILTIN_UI_REFERENCES}
        reference_lines = ["Reference the following translations:"]
        reference_lines.extend(
            f"{source} translates to {target}"
            for source, target in self.references
            if (str(source).casefold() in builtin_sources_cf
                or source_term_applies(str(source), batch_sources))
        )
        return "\n".join(reference_lines) + "\n\n" + build_batch_user_prompt(items)

    def _repair_multiline_chat_translation(
            self, entry: TextEntry) -> tuple[TextEntry, str, bool]:
        """Repair one chat translation by requesting each source segment once."""
        prefix, segments, separators = _split_translation_segments(
            entry.original)
        rebuilt: list[str] = [prefix]
        for index, part in enumerate(segments):
            segment_entry = replace(
                entry, original=part, translation="", quality_reasons=())
            user = self._build_chat_user_prompt([
                self._build_item([segment_entry], 0, 0, single=True)])
            if self._is_cancelled():
                return entry, "", False
            try:
                content, usage = self.client.chat(
                    self.system_prompt, [{"role": "user", "content": user}])
            except Exception as exc:  # noqa: BLE001
                self._record_usage(None)
                self._mark_request_failed(entry, exc)
                return entry, "", False
            self._record_usage(usage)
            if self._is_cancelled():
                return entry, "", False
            arr = self._response_array(content, segment_entry)
            translations = [
                item.get("translation")
                for item in (arr or [])
                if isinstance(item, dict)
                and item.get("id") == _entry_id(segment_entry)
                and isinstance(item.get("translation"), str)
            ]
            if len(translations) != 1:
                self._mark_failed(entry, "invalid_response", raw_output=content)
                return entry, "", False
            translated = translations[0].strip()
            if not translated:
                self._mark_failed(entry, "line_content_mismatch")
                return entry, "", False
            rebuilt.append(translated)
            if index < len(separators):
                rebuilt.append(separators[index])
        candidate = "".join(rebuilt)
        return entry, candidate, self._apply_quality(entry, candidate)

    def _repair_protected_chat_translation(
            self, entry: TextEntry) -> tuple[TextEntry, str, bool]:
        """Repair semantic fragments through the single-item chat contract."""
        parts = protected_slot_parts(entry.original)
        rebuilt: list[str] = []
        translated_any = False
        for protected, part in parts:
            if protected or not any(char.isalpha() for char in part):
                rebuilt.append(part)
                continue
            match = re.fullmatch(r"(\s*)(.*?)(\s*)", part, re.DOTALL)
            if match is None or not match.group(2):
                rebuilt.append(part)
                continue
            if self._is_cancelled():
                return entry, "", False
            segment_entry = replace(
                entry, original=match.group(2), translation="",
                quality_reasons=())
            user = self._build_chat_user_prompt([
                self._build_item([segment_entry], 0, 0, single=True)])
            try:
                content, usage = self.client.chat(
                    self.system_prompt, [{"role": "user", "content": user}])
            except Exception as exc:  # noqa: BLE001
                self._record_usage(None)
                self._mark_request_failed(entry, exc)
                return entry, "", False
            self._record_usage(usage)
            if self._is_cancelled():
                return entry, "", False
            arr = self._response_array(content, segment_entry)
            translations = [
                item.get("translation")
                for item in (arr or [])
                if isinstance(item, dict)
                and item.get("id") == _entry_id(segment_entry)
                and isinstance(item.get("translation"), str)
            ]
            if len(translations) != 1 or not translations[0].strip():
                self._mark_failed(entry, "invalid_response", raw_output=content)
                return entry, "", False
            rebuilt.extend((match.group(1), translations[0].strip(),
                            match.group(3)))
            translated_any = True
        if not translated_any:
            return entry, "", False
        candidate = "".join(rebuilt)
        return entry, candidate, self._apply_quality(entry, candidate)

    def _repair_protected_translation(
            self, entry: TextEntry, native_translate, target_lang: str,
            previous: str = "",
            ) -> tuple[TextEntry, str, bool] | None:
        """Retry semantic source fragments while preserving structural slots."""
        parts = protected_slot_parts(entry.original)
        if not any(protected for protected, _part in parts):
            return None
        rebuilt: list[str] = []
        translated_any = False
        semantic_cjk = False
        for protected, part in parts:
            if protected or not any(char.isalpha() for char in part):
                rebuilt.append(part)
                continue
            match = re.fullmatch(r"(\s*)(.*?)(\s*)", part, re.DOTALL)
            if match is None or not match.group(2):
                rebuilt.append(part)
                continue
            if self._is_cancelled():
                return entry, "", False
            body = match.group(2)
            try:
                translated, usage = native_translate(
                    body, target_lang, self.references)
            except Exception as exc:  # noqa: BLE001
                self._record_usage(None)
                self._mark_request_failed(entry, exc)
                return entry, "", False
            self._record_usage(usage)
            if self._is_cancelled():
                return entry, "", False
            if not isinstance(translated, str) or not translated.strip():
                self._mark_failed(entry, "line_content_mismatch")
                return entry, "", False
            if _CJK.search(translated):
                semantic_cjk = True
            rebuilt.extend((match.group(1), translated.strip(), match.group(3)))
            translated_any = True
        if not translated_any:
            return None
        candidate = "".join(rebuilt)
        good = self._apply_quality(entry, candidate)
        if not good and not semantic_cjk and previous:
            # 剥离段整体未翻出中文（模型对短片段回显/截断，deadbeat 真实样本：
            # ': config' → 'config'）→ 整段译文通常语义已正确，只是丢了
            # protected 段（按键/标签）→ 把整段译文中缺失的 protected 段回填
            # 到开头（整段译文已含按键时跳过，避免 'Enter 回车：配置' 重复）
            missing = "".join(
                part for protected, part in parts
                if protected and part.casefold() not in previous.casefold())
            if missing:
                candidate = missing + " " + previous.strip()
                good = self._apply_quality(entry, candidate)
        return entry, candidate, good

    def _repair_multiline_translation(
            self, entry: TextEntry, native_translate, target_lang: str,
            ) -> tuple[TextEntry, str, bool] | None:
        """Retry one malformed result by translating source segments — lines
        first, then sentences for long single-paragraph text (which echoes
        the source as untranslated_text when the prompt exceeds the context)."""
        prefix, segments, separators = _split_translation_segments(
            entry.original)
        if len(segments) < 2:
            return None
        rebuilt: list[str] = [prefix]
        for index, part in enumerate(segments):
            if self._is_cancelled():
                return entry, "", False
            try:
                translated, usage = native_translate(
                    part, target_lang, self.references)
            except Exception as exc:  # noqa: BLE001
                self._record_usage(None)
                self._mark_request_failed(entry, exc)
                return entry, "", False
            self._record_usage(usage)
            if self._is_cancelled():
                return entry, "", False
            if not isinstance(translated, str) or not translated.strip():
                self._mark_failed(entry, "line_content_mismatch")
                return entry, "", False
            rebuilt.append(translated.strip())
            if index < len(separators):
                rebuilt.append(separators[index])
        candidate = "".join(rebuilt)
        return entry, candidate, self._apply_quality(entry, candidate)

    def _response_array(self, content: str, entry: TextEntry | None) -> list[dict] | None:
        arr = extract_json_array(content) or extract_json_array_fallback(content)
        if arr is not None:
            if entry is None:
                return arr
            requested_id = _entry_id(entry)
            if any(isinstance(item, dict) and item.get("id") == requested_id
                   for item in arr):
                return arr
        if (entry is not None
                and getattr(self.client, "accepts_plain_single", False)
                and isinstance(content, str) and content.strip()):
            item_id = _entry_id(entry)
            prefix = json.dumps(item_id, ensure_ascii=False) + ":"
            echoed_values = [
                line.strip()[len(prefix):].strip()
                for line in content.splitlines()
                if line.strip().startswith(prefix)
                and line.strip()[len(prefix):].strip()
            ]
            translation = echoed_values[0] if len(echoed_values) == 1 else content.strip()
            return [{"id": item_id, "translation": translation}]
        return None

    def _build_item(self, batch: list[TextEntry], i: int, context_window: int,
                    single: bool = False) -> dict:
        e = batch[i]
        ctx_parts = []
        if e.meta.get("context_before"):
            ctx_parts.append("prev: " + str(e.meta["context_before"])[:80])
        if e.meta.get("context_after"):
            ctx_parts.append("next: " + str(e.meta["context_after"])[:80])
        for off in range(1, context_window + 1):
            if i - off >= 0:
                ctx_parts.append("prev: " + batch[i - off].original[:80])
            if i + off < len(batch):
                ctx_parts.append("next: " + batch[i + off].original[:80])
        # 字数预算：中文 1 字 ≈ 3 字节（UTF-8），译文 ≤ 预算字 → 字节 ≈ 预算×3 ≤ 容量
        explicit_budget = e.meta.get("max_chars")
        budget = (explicit_budget if type(explicit_budget) is int and explicit_budget > 0
                  else max(2, len(e.original.encode("utf-8")) // 3))
        # P1：术语按条目命中注入——只把本条原文真正命中的术语带进 prompt
        # （术语表可数百条，全部注入会稀释注意力并膨胀上下文；命中注入
        #  让模型在翻译本条时聚焦正确译名）
        glossary_hits = [
            (source, target)
            for source, target in self.glossary
            if source_term_applies(str(source), e.original)
            and str(target).strip()
        ]
        return {"id": _entry_id(e), "text": e.original,
                "file": e.file_id, "key_path": e.key_path,
                "role": str(e.meta.get("role", "display")),
                "reason": str(e.meta.get("reason", "")),
                "confidence": e.confidence,
                "context": " | ".join(ctx_parts) if ctx_parts else "",
                "short": len(e.original) <= 12, "budget": budget,
                "input_tokens": list(interaction_input_tokens(e.original)),
                "glossary_hits": glossary_hits}

    def _validate(self, batch: list[TextEntry], arr: list[dict]
                  ) -> list[tuple[TextEntry, str, bool]]:
        by_id: dict[str, str] = {}
        invalid_ids: set[str] = set()
        for item in arr:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            translation = item.get("translation")
            if not isinstance(item_id, str):
                continue
            if item_id in by_id or item_id in invalid_ids or not isinstance(translation, str):
                by_id.pop(item_id, None)
                invalid_ids.add(item_id)
                continue
            by_id[item_id] = translation
        results: list[tuple[TextEntry, str, bool]] = []
        for e in batch:
            item_id = _entry_id(e)
            if item_id in invalid_ids or item_id not in by_id:
                self._mark_failed(e, "invalid_response")
                results.append((e, "", False))
                continue
            tr = by_id[item_id]
            good = self._apply_quality(e, tr)
            results.append((e, tr, good))
        return results

    def _apply_quality(self, entry: TextEntry, translation: str) -> bool:
        # P0-3 证据留存：保存模型原始输出（自愈/修复前的原文样），
        # 供质量门审校与复盘；修复后的归一化输出存 normalized_output
        # （两者相同则省略，避免冗余）。写回只允许 quality_passed=True
        # 的条目，raw 证据不参与写回判断。
        raw_output = translation
        # 标签自愈：译文语义正确但占位符缺失/闭合标签乱序（模型漏写标记是
        # 稳定行为）→ 确定性补全/重排后再判定（a-catfiends/the-keeper/
        # interdream 真实样本）。模型新增占位符/顺序破坏 → 原样，仍判失败
        translation = self_heal_format_tags(entry.original, translation)
        result = validate_translation_quality(
            entry, translation, self.glossary,
            check_placeholders=self.placeholder_check,
        )
        target = self.lang.rsplit("→", 1)[-1].strip().casefold()
        translation = result.normalized_translation
        is_simplified_chinese = target in {"zh", "zh-cn", "zh-hans"}
        contains_wrong_script = self._has_disallowed_chinese_target_letters(
            entry, translation)
        # 扣除品牌/署名/credit 保护术语后仍有字母才算「有可翻译语义」：
        # Playstation/Xbox 等纯品牌串模型保留原文是合理行为，不判失败
        # （第二个参数传原文自身：从原文中移除其保护术语）
        source_has_semantic_text = any(
            char.isalpha()
            for char in semantic_target_text(entry.original, entry.original))
        normalized = result.normalized_translation
        # P0-3：把质量门前后的输出作为证据写入 meta（raw 始终存；
        # 归一化后与 raw 相同时不重复存）。setdefault 保留**首次**调用
        # 捕获的输出：repair/自愈路径会对同一 entry 多次调用本方法，
        # 后续调用的参数是修复拼装结果而非模型原始输出，不得覆盖证据。
        entry.meta = dict(entry.meta)
        entry.meta.setdefault("raw_output", raw_output)
        if normalized != entry.meta["raw_output"]:
            entry.meta.setdefault("normalized_output", normalized)
        role = str(entry.meta.get("role", "display"))
        disposition = str(entry.meta.get("disposition", ""))
        proper_name = role == "proper_name" or disposition == "proper_name"
        contains_chinese = any(
            self._is_chinese_ideograph(char) for char in translation)
        # 纯专名/标签回显豁免：原文与译文扣除符号后的字母序列相同，
        # 且原文无小写普通词、无 UI 词典词（Crash Bandicoot / [ S K I P ] /
        # 3DI70R 2024 / AI / IMGUI 保留原文合理；'Hello world' 回显有小写词、
        # 'SFX'/'Continue' 回显在 UI 词典 → 仍判失败）
        letters_source = re.sub(r"[^A-Za-z]", "", entry.original).casefold()
        letters_target = re.sub(r"[^A-Za-z]", "", translation).casefold()
        # 英文词检查剥离专名载体（@_domeDev\ndomedev.itch.io 的 domedev 是域名，
        # 不算小写普通词）
        proper_name_words = _ENGLISH_WORD.findall(
            SAFE_KEEPERS.sub(" ", entry.original))
        # 小写词用独立词检查：'Stefánsson' 的 ASCII 碎片 nsson 不算小写普通词
        # （zero-deaths 'Sir Stefán Karl Stefánsson' 专名回显真实样本）
        proper_name_echo = (
            letters_source
            and letters_source == letters_target
            and not has_independent_lower_word(entry.original)
            and not any(
                word.casefold() in _DISPLAY_WORDS_CASEFOLD
                or word.casefold() in _BUILTIN_UI_TERMS_CASEFOLD
                for word in proper_name_words))
        # lorem ipsum 占位文本回显（无中文）是合理行为 → 豁免
        lorem_placeholder = is_lorem_ipsum_placeholder(entry.original)
        if (result.passed and is_simplified_chinese
                and ((contains_wrong_script and not proper_name_echo
                      and not lorem_placeholder)
                     or (source_has_semantic_text and not proper_name
                         and not contains_chinese and not proper_name_echo
                         and not lorem_placeholder))):
            entry.translation = result.normalized_translation
            entry.quality_reasons = ("target_script_mismatch",)
            entry.meta = dict(entry.meta)
            entry.meta["quality_passed"] = False
            entry.meta["quality_reasons"] = ["target_script_mismatch"]
            return False
        if result.passed:
            role = str(entry.meta.get("role", "display"))
            consistency_key = (entry.original, role)
            with self._consistency_lock:
                previous = self._consistent_translations.get(consistency_key)
                if previous is None:
                    self._consistent_translations[consistency_key] = (
                        result.normalized_translation)
                elif previous != result.normalized_translation:
                    entry.translation = result.normalized_translation
                    entry.quality_reasons = ("consistency_mismatch",)
                    entry.meta = dict(entry.meta)
                    entry.meta["quality_passed"] = False
                    entry.meta["quality_reasons"] = ["consistency_mismatch"]
                    return False
        entry.translation = result.normalized_translation
        entry.quality_reasons = result.reasons
        entry.meta = dict(entry.meta)
        entry.meta["quality_passed"] = result.passed
        entry.meta["quality_reasons"] = list(result.reasons)
        return result.passed

    def _has_disallowed_chinese_target_letters(
            self, entry: TextEntry, translation: str) -> bool:
        role = str(entry.meta.get("role", "display"))
        disposition = str(entry.meta.get("disposition", ""))
        allowed_terms = []
        if role == "proper_name" or disposition == "proper_name":
            allowed_terms.append(entry.original)
        allowed_terms.extend(
            str(target) for source, target in self.glossary
            if source_term_applies(str(source), entry.original)
            and str(target).strip()
        )
        # lorem ipsum 占位文本（开发者填充的假拉丁文本，无真实语义）→
        # 模型回显是合理行为（zero-deaths 'Loem iipsum solar' 真实样本）
        if is_lorem_ipsum_placeholder(entry.original):
            return False
        # 原文英文词集（casefold）：驼峰技术缩写豁免需原文也含该词
        # （防模型幻觉新词）
        source_terms_cf = {
            word.casefold()
            for word in _ENGLISH_WORD.findall(
                SAFE_KEEPERS.sub(" ", entry.original))}
        semantic = semantic_target_text(
            entry.original, translation, allowed_terms)
        # 原文交互按键词（Escape/P/X）在译文保留是正确行为 → 移除后判定
        for event in interaction_input_events(entry.original):
            if event.kind == "literal_glyph":
                semantic = semantic.replace(event.value, "", 1)
        # @用户名紧邻的显示名（"game by fie (@zkfie)" 的 fie 是作者名）→ 豁免
        display_names = set()
        for match in _AT_USER.finditer(semantic):
            head = semantic[max(0, match.start() - 12):match.start()]
            for word in _DISPLAY_NAME_BEFORE_AT.findall(head):
                display_names.add(word.casefold())
        # 模型正确保留的专名载体 → 移除后判定（不算英文残留）：
        # 3+ 段路径（User/Blah/Hey/HotelParadiseScreenshot）、域名（itch.io /
        # OpenGameArt.com）、@用户名（@zkfie / @SoftdevWu）、版本号（0.4.0beta）
        semantic = SAFE_KEEPERS.sub(" ", semantic)
        # 聊天/控制台命令（"/kick"、/give）→ 游戏命令保留原文是正确行为
        semantic = _SLASH_COMMAND.sub(" ", semantic)
        # 非 ASCII 字母（俄/日/韩/阿拉伯文…）→ 目标脚本错误，判失败
        # （中文目标不允许混入其他脚本字母；日文汉字与中文同码区不受影响）
        # 原文本身含该脚本字母（"Russian Localization - Алеся Апухтина" 的
        # 译者名）且译文已含中文翻译 → 模型保留人名合理，不算目标脚本错误
        # （纯日文回显 "ゲーム設定" 无中文翻译 → 仍判失败并重试）
        source_foreign = {
            char for char in entry.original
            if char.isalpha() and not char.isascii()
            and not self._is_chinese_ideograph(char)}
        # 原文自身的汉字（日文汉字同码区）→ 译文中出现它们可能是回显：
        # "ゲーム設定" → "ゲーム設定" 的 設定 不能证明译文含中文翻译
        source_ideographs = {
            char for char in entry.original
            if self._is_chinese_ideograph(char)}
        has_chinese = any(
            self._is_chinese_ideograph(char) and char not in source_ideographs
            for char in translation)
        if any(char.isalpha() and not char.isascii()
               and not self._is_chinese_ideograph(char)
               and not (char in source_foreign and has_chinese)
               for char in semantic):
            return True
        # 签名位豁免：原文破折号后的尾部小写名（"Turkish Localization -
        # yamur <3" 的 yamur 是译者署名）→ 译文保留是正确行为。
        # 要求译文已含中文翻译（纯回显 "Turkish Localization - yamur" 不豁免）
        signature_words: set[str] = set()
        parts = re.split(r"[-–—]\s+", entry.original)
        if len(parts) > 1:
            signature_words = {
                word.casefold()
                for word in _ENGLISH_WORD.findall(parts[-1])}
        # 问候行豁免：译文首行以问候语开头（Hello, there. / Hi!）且首行英文词
        # ≤2 个、译文已含中文 → 问候保留是本地化惯例（mimic-search 的
        # "Hello,\n\n\n几小时前…"、soul-delivery 的 "Hello, there.\n\n在过去的
        # 6个月里…"）。纯回显（无中文）不豁免。
        greeting_words: set[str] = set()
        first_line = translation.splitlines()[0] if translation.splitlines() else ""
        first_words = _ENGLISH_WORD.findall(first_line)
        if (first_words and has_chinese
                and first_words[0].casefold() in _GREETING_WORDS
                and len(first_words) <= 2):
            greeting_words = {word.casefold() for word in first_words}
        # rich-text 包裹的小写词（<color=#FFD700><b>lucd</b></color> 的作者名
        # 高亮、lucd#9569 Discord id）→ 译文保留是正确行为（slendergus 真实
        # 样本）；要求已含中文（纯回显 "<b>hello</b>" 不豁免）。
        # 注意：semantic 已剥离标签，须从带标签的原文译文提取
        rich_words: set[str] = set()
        if has_chinese:
            rich_words = {
                match.group(1).casefold()
                for match in re.finditer(r">([A-Za-z]{3,})<", translation)}
        # 连续英文短语（词间无中文间隔）→ 明确半翻，判失败；
        # 但短语中全为专名形态（TitleCase/全大写且非词典词，如 "Amitte Sukku"
        # 人名并列、Escape 按键名）不算英文残留
        phrase = _ENGLISH_PHRASE.search(semantic)
        if phrase:
            semantic_words = _ENGLISH_WORD.findall(semantic)
            # 短语覆盖的语义词索引（按在全文中的位置对齐 —— 邻居判断必须
            # 用全文：'Fun New' 中 New 的右邻 School 在短语外）
            p_indices = [
                i for i, m in enumerate(_ENGLISH_WORD.finditer(semantic))
                if phrase.start() <= m.start() and m.end() <= phrase.end()]
            for i in p_indices:
                word = semantic_words[i]
                if word.casefold() in PHYSICAL_KEY_NAMES_CASEFOLD:
                    continue
                if word.casefold() in display_names:
                    continue
                if (word.casefold() in signature_words and has_chinese):
                    continue
                if word.casefold() in greeting_words:
                    continue
                if (word.casefold() in rich_words and has_chinese):
                    continue
                # 驼峰技术缩写（VSync/MonoBehaviour）→ 界面标准术语，保留
                # 原文合理（vincent 'VSync: OFF' → 'VSync：关闭'）；形态要求
                # 首大写 + 内部混合大小写（全大写 SETTINGS/TitleCase Save
                # 仍按词典规则判定）且原文也含该词（防模型幻觉新词）
                if (is_camel_tech_abbreviation(word)
                        and word.casefold() in source_terms_cf):
                    continue
                # 小写词/UI 词典词夹在 TitleCase 专名词之间（《Baldi's Fun New
                # School Remastered》的 New、'Craftydelight the Asset Store' 的
                # the）→ 专名短语的一部分，豁免；孤立词（'按下 the button'、
                # 句首的 Open）仍判失败
                if word.islower() or word.casefold() in _DISPLAY_WORDS_CASEFOLD:
                    left_title = (i > 0
                                  and semantic_words[i - 1][0].isupper()
                                  and semantic_words[i - 1][1:].islower())
                    right_title = (i + 1 < len(semantic_words)
                                   and semantic_words[i + 1][0].isupper()
                                   and semantic_words[i + 1][1:].islower())
                    if not (left_title and right_title):
                        return True
        # 单个残留词：小写普通词或 UI 词典词 → 半翻失败；
        # 物理按键名（Escape/Enter/F1…）、大写/TitleCase 专名（Windows/CBS/Orbit）、
        # @用户名显示名（fie）、破折号后署名（yamur）、首行问候（Hello）、
        # rich-text 包裹词（lucd）→ 豁免
        semantic_words = _ENGLISH_WORD.findall(semantic)
        for i, word in enumerate(semantic_words):
            if word.casefold() in PHYSICAL_KEY_NAMES_CASEFOLD:
                continue
            if word.casefold() in display_names:
                continue
            if (word.casefold() in signature_words and has_chinese):
                continue
            if word.casefold() in greeting_words:
                continue
            if (word.casefold() in rich_words and has_chinese):
                continue
            # 驼峰技术缩写（VSync/MonoBehaviour）→ 界面标准术语，保留
            # 原文合理（vincent 'VSync: OFF' → 'VSync：关闭'）；形态要求
            # 首大写 + 内部混合大小写（全大写 SETTINGS/TitleCase Save
            # 仍按词典规则判定）且原文也含该词（防模型幻觉新词）
            if (is_camel_tech_abbreviation(word)
                    and word.casefold() in source_terms_cf):
                continue
            # UI 词典词/小写冠词夹在 TitleCase 专名词之间
            # （《Baldi's Fun New School Remastered》的 New、'Craftydelight the
            # Asset Store' 的 the）→ 专名短语的一部分，豁免；
            # 孤立词（'Save 游戏'、'按下 the button'、句首的 Open）仍判失败
            if word.islower() or word.casefold() in _DISPLAY_WORDS_CASEFOLD:
                left_title = (i > 0 and semantic_words[i - 1][0].isupper()
                              and semantic_words[i - 1][1:].islower())
                right_title = (i + 1 < len(semantic_words)
                               and semantic_words[i + 1][0].isupper()
                               and semantic_words[i + 1][1:].islower())
                if not (left_title and right_title):
                    return True
        return False

    @staticmethod
    def _is_chinese_ideograph(char: str) -> bool:
        value = ord(char)
        return (0x3400 <= value <= 0x9FFF
                or 0xF900 <= value <= 0xFAFF
                or 0x20000 <= value <= 0x2FA1F)

    @staticmethod
    def _mark_failed(entry: TextEntry, reason: str,
                     raw_output: str = "") -> None:
        entry.status = STATUS_FAILED
        entry.quality_reasons = (reason,)
        entry.meta = dict(entry.meta)
        entry.meta["quality_passed"] = False
        entry.meta["quality_reasons"] = [reason]
        # P0-3：invalid_response 时模型返回的原始内容作为证据留存
        if raw_output:
            entry.meta["raw_output"] = raw_output

    def _mark_request_failed(self, entry: TextEntry, exc: Exception) -> None:
        self._mark_failed(entry, "request_error")
        secret = getattr(getattr(self.client, "config", None), "api_key", "")
        entry.meta["request_error_detail"] = json.dumps(
            sanitize_exception(exc, (secret,)), ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _copy_failure_state(source: TextEntry, target: TextEntry) -> None:
        target.translation = source.translation
        target.quality_reasons = source.quality_reasons
        target.meta = dict(target.meta)
        target.meta["quality_passed"] = False
        target.meta["quality_reasons"] = list(source.quality_reasons)
        if "request_error_detail" in source.meta:
            target.meta["request_error_detail"] = source.meta["request_error_detail"]
        if "raw_output" in source.meta:
            target.meta["raw_output"] = source.meta["raw_output"]

    def _record_usage(self, usage) -> None:
        with self._metrics_lock:
            self._requests += 1
            if usage is not None:
                self._input_tokens += max(0, int(getattr(usage, "prompt", 0)))
                self._output_tokens += max(0, int(getattr(usage, "completion", 0)))
