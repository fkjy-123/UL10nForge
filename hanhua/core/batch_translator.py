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
from hanhua.core.knowledge import (_is_multilingual_source, _is_spaced_action,
                                   _is_uppercase_action)
from hanhua.core.placeholders import (DISPLAY_WORDS, SAFE_KEEPERS,
                                      self_heal_format_tags)
from hanhua.core.local_model import sanitize_exception
from hanhua.core.models import (TextEntry, TranslateStats, STATUS_FAILED,
                                STATUS_TRANSLATED, is_actionable_translation)
from hanhua.core.protected_spans import (protected_slot_parts,
                                         semantic_target_text)
from hanhua.core.prompts import build_batch_user_prompt
from hanhua.core.quality import (_CJK, _ui_check_words,
                                 has_independent_lower_word,
                                 is_camel_tech_abbreviation,
                                 is_lorem_ipsum_placeholder,
                                 quoted_proper_terms,
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
# 原文引号内片段（内嵌引文/铭文/题词，如 "To the house of ..."）：译文
# 保留其原文是正确行为（alisa-demo 实证同一引文的三语言版译文都被误判
# 英文残留）→ 引号内容中的英文词在译文出现时豁免
_QUOTE_CONTENT = re.compile(
    r"[\"“”«»「」『』]([^\"“”«»「」『』]{1,80})[\"“”«»「」『』]")
_ENGLISH_WORD = re.compile(r"[A-Za-z]{3,}")
# 重音拉丁字母 → ASCII 一对一词符映射（长度不变，索引对齐保持）：
# _ENGLISH_WORD 是纯 ASCII 正则，带重音专名会被拆成碎片（"Pulsomètre" →
# "Pulsom"+"tre"），碎片 "tre" 是小写普通词 → 误判英文残留（alisa-demo
# 实证：法语设备名 Pulsomètre 保留在译文被判 target_script_mismatch）。
# 语义英文词提取前归一化 → 重音专名成完整词走 TitleCase 豁免；
# 非 ASCII 字母检查仍用归一化前的语义串（假名/西里尔残留照常拒绝）
_ACCENT_TO_ASCII = str.maketrans(
    "àáâãäåçèéêëìíîïñòóôõöùúûüýÿßøæœðþ"
    "ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝØÆŒÐÞ",
    "aaaaaaceeeeiiiinooooouuuuyyssaoet"
    "AAAAAACEEEEIIIINOOOOOUUUUYOAEDT")
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
# 英语功能词（冠词/介词/连词/代词/be 动词等）：原文 TitleCase 形态
# （句子开头 "The End is near" 的 The）不是专名——译文小写残留（"the End"）
# 是真实半翻，不得走小写化专名豁免（baldis 实证的是 Bossfight→bossfight
# 这种真专名，the/save 这类普通词残留必须仍判失败）
_ENGLISH_FUNCTION_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "nor", "so", "yet", "for",
    "of", "in", "on", "at", "to", "from", "by", "with", "without",
    "over", "under", "is", "are", "was", "were", "be", "been", "being",
    "am", "it", "its", "this", "that", "these", "those", "you", "your",
    "my", "our", "we", "they", "he", "she", "his", "her", "their",
    "i", "me", "us", "them", "him", "do", "does", "did", "not", "no",
    "off", "out", "up", "down", "if", "as", "than", "then", "into",
    "onto", "upon", "after", "before", "when", "where", "while", "who",
    "what", "which", "why", "how", "there", "here", "all", "any",
})
# 译文空段（\n\n 空行）：多行文本的段整体漏译证据——换行合并兜底只放行
# 「合并」不放行「段丢失」（测试实证：Second → 空行必须失败）
_EMPTY_SEGMENT = re.compile(r"\n[ \t]*\n")
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
        # 同对象（asset_file+obj）已成功译文：多语言打包游戏（同一对象存
        # 英/法/意/日四版文本）与对话序列对象中，兄弟条目的成功译文是
        # 重试时的译例来源（alisa-demo 实证：Clé en Fer 回显 → 注入同 obj
        # "Iron Key translates to 铁钥匙" → 模型输出「铁钥匙」）。
        self._obj_results: dict[str, list[tuple[str, str]]] = {}
        self._obj_lock = threading.Lock()

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
                        self._record_obj_result(member, member.translation)
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
                                self._record_obj_result(
                                    member, member.translation)
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
                          "untranslated_text", "action_word_residue"}
                         & set(entry.quality_reasons))
                    # 只对真多行条目逐段修复；单行失败（回显/动作词残留）
                    # 不在此修复——落到 retryable 走 native 降级
                    # （Hy-MT2 translate_text 带 references 译例，知识库
                    #  TOSS TRASH → 丢垃圾 靠该路径生效）
                    and len(_split_translation_segments(entry.original)[1]) >= 2):
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
                and (not ({"newline_mismatch", "line_content_mismatch"}
                          & reasons)
                     or has_protected_slot))
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

    @staticmethod
    def _obj_key(entry: TextEntry) -> str:
        """同对象标识：asset_file + obj（MonoBehaviour rawstr 数组 / TextAsset）。

        同对象内多个条目常是同一文本的不同语言版本（四语言打包）或同一
        对话流——兄弟条目的成功译文可作为重试译例。
        """
        af = entry.meta.get("asset_file")
        obj = entry.meta.get("obj")
        if af and obj is not None:
            return f"{af}#{obj}"
        return ""

    def _record_obj_result(self, entry: TextEntry, translation: str) -> None:
        """记录一条成功译文到同对象桶（重试时作译例）。"""
        key = self._obj_key(entry)
        if not key or not entry.original or not translation:
            return
        pair = (entry.original, translation)
        with self._obj_lock:
            bucket = self._obj_results.setdefault(key, [])
            if pair not in bucket:
                bucket.append(pair)

    def _obj_reference_pairs(self, entry: TextEntry) -> list[tuple[str, str]]:
        """同对象已成功条目的 (原文, 译文) 对照（最多 3 对）。"""
        key = self._obj_key(entry)
        if not key:
            return []
        with self._obj_lock:
            return list(self._obj_results.get(key, ()))[:3]

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
            e, tr, good = _work_body(i)
            # 成功译文在 worker 内立即入同对象桶：兄弟条目（四语言打包/
            # 同一对话流）的降级链在后续 work 里读译例。不能等 run() 主线程
            # 的 consume_native_result 回调——worker 完成当前条目后立即取
            # 下一个 work，record 与兄弟条目的读取形成竞态（alisa-demo
            # 实证：同批 Clé en Fer 偶发读不到 Iron Key 译例 → 回显失败；
            # -s 输出捕获的 IO 延迟掩盖了该竞态）。单 worker 下此处保证
            # 先 record 后读取；多 worker 由 _obj_lock 保证一致读。
            if good and tr:
                self._record_obj_result(e, tr)
            return e, tr, good

        def _work_body(i: int) -> tuple[TextEntry, str, bool]:
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
            # 首译失败状态快照：降级修复的内部复查会覆盖 entry 的
            # translation/quality_reasons/meta（_apply_quality 落盘）→
            # 修复失败后必须恢复首译状态，后续降级链（multiline/兜底/
            # 词级补译/专名重译）基于首译判定（baldis 实证：multiline
            # repair 首行回显英文 → reasons 被覆盖成 target_script_mismatch
            # → 换行合并兜底的「仅换行原因」判定失准，语义完整首译被卡死）。
            first_fail_state = (
                e.translation, e.status, e.quality_reasons, dict(e.meta))
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
                (e.translation, e.status, e.quality_reasons, e.meta) = (
                    first_fail_state)
            if (callable(getattr(self.client, "translate_text", None))
                    and not sub[0][2]
                    and self._allows_fallback_retry(e)
                    and ({"newline_mismatch", "line_content_mismatch",
                          "untranslated_text", "action_word_residue",
                          "target_script_mismatch"}
                         & set(e.quality_reasons))):
                repaired = self._repair_multiline_translation(
                    e, native_translate, target_lang)
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                # 修复成功才返回；失败（逐段仍残留英文等）恢复首译失败状态
                # 继续走后续降级链（兜底/词级补译/专名重译/双跳/同对象译例/
                # 普通重试），不截断（alisa-demo 实证：意语长句逐段修复时短段
                # 仍被译成英语，成功修复需段内双跳）。
                if repaired is not None and repaired[2]:
                    return repaired
                (e.translation, e.status, e.quality_reasons, e.meta) = (
                    first_fail_state)
            # 换行合并兜底：模型稳定把多行文本合并为单行（1.8B 长句输出
            # 倾向单行）——native 首译语义完整中文、仅因换行结构判失败，
            # multiline repair 重建也失败（逐行重译时首行被模型回显英文，
            # baldis 'Error please contact game owner\nand check log.' 实证）
            # → 放行首译（中文语义优先，Unity UI 自动换行兜底排版）。
            # 仅当换行相关是唯一失败原因、译文含中文、且无空段（\n\n 是
            # 段整体漏译证据，不得放行）时放行；放行证据 line_merged 记入
            # meta 供人工校对筛选。
            if (callable(getattr(self.client, "translate_text", None))
                    and not sub[0][2]
                    and self._allows_fallback_retry(e)
                    and sub[0][1]
                    and _CJK.search(sub[0][1])
                    and not _EMPTY_SEGMENT.search(sub[0][1])
                    and set(e.quality_reasons)
                    <= {"newline_mismatch", "line_content_mismatch"}):
                e.translation = sub[0][1]
                e.quality_reasons = ()
                e.meta = dict(e.meta)
                e.meta["quality_passed"] = True
                e.meta["quality_reasons"] = []
                e.meta["line_merged"] = True
                return e, sub[0][1], True
            # 词级补译：译文含中文但残留孤立小写英文短语（'itch page' 模型
            # 漏翻）→ 短语单独翻译替换回译文；模型补译输出仍保留的词
            # （'itch' 是 itch.io 专名）→ 记入本条 meta 豁免（要求原文也
            # 含该词，防幻觉），与模型保留 Gamejolt/Markiplier 同理。
            # backrooms 实证：'available at itch page' → 补译 → 'itch 页面'。
            # 纯回显场景（译文无中文 + untranslated_text，'outstanding
            # citizen' 全小写普通词回显，baldis 实证）：短语整词引用两跳
            # 直接译出（实测 裸→回显 / 引用→杰出公民）。
            if (callable(getattr(self.client, "translate_text", None))
                    and not sub[0][2]
                    and self._allows_fallback_retry(e)
                    and sub[0][1]
                    and ((_CJK.search(sub[0][1])
                          and "target_script_mismatch"
                          in set(e.quality_reasons))
                         or (not _CJK.search(sub[0][1])
                             and "untranslated_text"
                             in set(e.quality_reasons)))):
                repaired = self._repair_word_residue(
                    e, native_translate, target_lang, sub[0][1])
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                if repaired is not None and repaired[2]:
                    return repaired
            # 专名 references 重译：译文无中文（回显/半翻）+ 原文含 TitleCase
            # 专名 → 注入 (专名, 专名) 引用重译——模型把专名当术语保留、
            # 只译其余部分（backrooms 实证：'Markiplier was here' 回显 →
            # 注入 → 'Markiplier 曾来过这里'）。无中文可译部分时（纯专名
            # 'Shirt Decal' 被模型补成 'T-shirt Decal'）重译让模型按引用
            # 保留专名 → 回显经 proper_name_echo 放行（物品名保留合理）。
            if (callable(getattr(self.client, "translate_text", None))
                    and not sub[0][2]
                    and self._allows_fallback_retry(e)
                    and sub[0][1]
                    and not _CJK.search(sub[0][1])
                    and ({"untranslated_text", "target_script_mismatch"}
                         & set(e.quality_reasons))):
                retried = self._retry_with_proper_name_reference(
                    e, native_translate, target_lang, sub[0][1])
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                if retried is not None and retried[2]:
                    return retried
            # 多语言源双跳：模型对含假名/重音字母的原文（日语/意语/法语等）
            # 倾向输出**英语译文**（准确但目标语错误，质量门拒绝）→ 以英语
            # 译文为中间源再译一次中文（模型英译中强项，alisa-demo 实证
            # 日语 → Right-hand key → 右手钥匙）。失败继续落到同对象译例。
            if (callable(getattr(self.client, "translate_text", None))
                    and not sub[0][2]
                    and self._allows_fallback_retry(e)
                    and _is_multilingual_source(e.original)
                    and not _CJK.search(sub[0][1] or "")
                    and _ENGLISH_WORD.search(sub[0][1] or "")):
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                try:
                    via, via_usage = native_translate(
                        (sub[0][1] or "").strip(), target_lang,
                        self.references)
                except Exception as exc:  # noqa: BLE001
                    self._record_usage(None)
                    self._mark_request_failed(e, exc)
                    return e, "", False
                self._record_usage(via_usage)
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                if isinstance(via, str) and via.strip():
                    via_good = self._apply_quality(e, via)
                    if via_good:
                        return e, via, via_good
            # 同对象译例：失败条目的同 obj 兄弟条目已成功（多语言打包游戏
            # 同一对象存英/法/意/日四版文本；对话流对象相邻句子）→ 注入
            # 「同一物品/对话流的参考译文」重试（alisa-demo 实证：Clé en
            # Fer 回显 → 注入 Iron Key translates to 铁钥匙 → 输出铁钥匙）。
            if (not sub[0][2]
                    and self._allows_fallback_retry(e)
                    and self._obj_reference_pairs(e)):
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                try:
                    obj_refs = self._obj_reference_pairs(e)
                    lang_names = getattr(
                        self.client, "_TARGET_LANGUAGE_NAMES", {}) or {}
                    lang_name = lang_names.get(
                        target_lang.strip().casefold(), target_lang.strip())
                    lines = ["Reference translations from the same item:"]
                    lines.extend(
                        f"{src} translates to {tgt}"
                        for src, tgt in obj_refs)
                    lines.extend([
                        "",
                        f"Translate the following text into {lang_name} "
                        "(same item as above):",
                        "",
                        e.original,
                    ])
                    retry_content, retry_usage = self.client.chat(
                        "", [{"role": "user",
                              "content": "\n".join(lines)}])
                except Exception as exc:  # noqa: BLE001
                    self._record_usage(None)
                    self._mark_request_failed(e, exc)
                    return e, "", False
                self._record_usage(retry_usage)
                if self._is_cancelled():
                    restore_original_state()
                    return e, "", False
                if isinstance(retry_content, str) and retry_content.strip():
                    retry_good = self._apply_quality(e, retry_content)
                    return e, retry_content, retry_good
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
                 "input_token_mismatch", "action_word_residue"}
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
        if len(segments) < 2:
            # 单行失败不在此修复：返回失败走 _chat_each 的 native 降级
            # （Hy-MT2 translate_text 单段 prompt + references 译例——
            # 知识库 TOSS TRASH → 丢垃圾 靠该路径生效；chat 逐段修复
            # 无译例，曾把单行 action_word_residue 截胡导致重试失效）
            return entry, "", False
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

    def _repair_word_residue(
            self, entry: TextEntry, native_translate, target_lang: str,
            translation: str,
            ) -> tuple[TextEntry, str, bool] | None:
        """词级补译：译文已含中文但残留孤立小写英文短语（'itch page' 模型
        漏翻）→ 短语单独翻译后替换回译文。模型补译输出仍保留的词（'itch'
        是 itch.io 专名）→ 记入本条 meta 的 word_residue_exempt（要求原文
        也含该词，防模型幻觉），质量门据此豁免——与模型保留 Gamejolt /
        Markiplier 同理，专名保留是翻译规范（backrooms 实证）。复查失败时
        清除豁免标记，避免残留 meta 影响后续重试轮。"""
        residue_phrases: list[str] = []
        for match in _ENGLISH_PHRASE.finditer(translation):
            phrase = match.group(0)
            words = _ENGLISH_WORD.findall(phrase)
            if not words or len(words) > 2 or len(phrase) > 25:
                continue
            # 纯小写普通词短语才补译：TitleCase/全大写专名（Gamejolt）已走
            # 专名豁免、数字混合（4chan）已走数字邻接豁免——补译只针对
            # 模型漏翻的小写词（'itch page'）
            if not all(word[0].islower() and not word.isupper()
                       for word in words):
                continue
            residue_phrases.append(phrase)
        if not residue_phrases:
            return None
        source_terms_cf = {
            word.casefold()
            for word in _ENGLISH_WORD.findall(
                SAFE_KEEPERS.sub(" ", entry.original)
                .translate(_ACCENT_TO_ASCII))}
        repaired = translation
        confirmed: list[str] = []
        for phrase in residue_phrases:
            if self._is_cancelled():
                return entry, "", False
            try:
                out, usage = native_translate(
                    phrase, target_lang, self.references)
            except Exception as exc:  # noqa: BLE001
                self._record_usage(None)
                self._mark_request_failed(entry, exc)
                return None
            self._record_usage(usage)
            if not isinstance(out, str) or not out.strip():
                continue
            phrase_words = _ENGLISH_WORD.findall(phrase)
            if phrase_words and (
                    not _ENGLISH_WORD.search(out)
                    or not _CJK.search(out)):
                # 裸翻译输出非纯中文（可能直译误译：'itch page'→'痒页面'，
                # backrooms 实证；或纯英文回显：'outstanding citizen'→
                # 回显，baldis 实证）→ 逐词保留引用重试：模型确认的专名会
                # 保留原文（'itch 页面'），普通词引用后直译（'杰出公民'）。
                # 两种输出不一致 → 引用版可信（模型在裸 prompt 下把专名
                # 当普通词直译，引用后识别为专名保留）；一致（仍纯中文/
                # 仍回显）→ 词确可全译/保留，用第二意见
                try:
                    ref_out, ref_usage = native_translate(
                        phrase, target_lang,
                        tuple((w, w) for w in phrase_words))
                except Exception as exc:  # noqa: BLE001
                    self._record_usage(None)
                    self._mark_request_failed(entry, exc)
                    return None
                self._record_usage(ref_usage)
                if isinstance(ref_out, str) and ref_out.strip():
                    out = ref_out.strip()
            # 模型补译输出保留的英文词 = 模型确认的专名（itch）→ 豁免，
            # 但要求原文也含该词（防模型幻觉新词）；输出无英文 → 完全替换
            confirmed.extend(
                word.casefold() for word in _ENGLISH_WORD.findall(out)
                if word.casefold() in source_terms_cf)
            repaired = repaired.replace(phrase, out)
        if repaired == translation:
            return None
        entry.meta = dict(entry.meta)
        entry.meta["word_residue_exempt"] = confirmed
        good = self._apply_quality(entry, repaired)
        if not good and confirmed:
            # 复查失败：清除豁免标记，避免残留 meta 影响后续重试轮
            entry.meta = dict(entry.meta)
            entry.meta.pop("word_residue_exempt", None)
        return entry, repaired, good

    def _retry_with_proper_name_reference(
            self, entry: TextEntry, native_translate, target_lang: str,
            translation: str,
            ) -> tuple[TextEntry, str, bool] | None:
        """专名 references 重译：译文纯回显（untranslated_text）+ 原文含
        TitleCase 专名 + 其余部分可译（含小写普通词）→ 注入 (专名, 专名)
        引用重译整句——模型把专名当术语保留、只译其余部分（backrooms
        实证：'Markiplier was here' 回显 → 注入 Markiplier → 'Markiplier
        曾来过这里'）。纯专名回显（'Crash Bandicoot'）无小写可译部分 →
        不触发；UI 词典词（Save/Continue）不进专名引用（真漏翻仍失败）。
        """
        original = entry.original
        if not _ENGLISH_WORD.search(translation):
            return None
        proper_words = [
            word for word in _ENGLISH_WORD.findall(original)
            if word[0].isupper() and word[1:].islower()
            and word.casefold() not in _DISPLAY_WORDS_CASEFOLD
            and word.casefold() not in _BUILTIN_UI_TERMS_CASEFOLD]
        if not proper_words:
            return None
        references = self.references + tuple(
            (word, word) for word in proper_words)
        try:
            out, usage = native_translate(original, target_lang, references)
        except Exception as exc:  # noqa: BLE001
            self._record_usage(None)
            self._mark_request_failed(entry, exc)
            return entry, "", False
        self._record_usage(usage)
        if self._is_cancelled():
            return entry, "", False
        if not isinstance(out, str) or not out.strip():
            return None
        good = self._apply_quality(entry, out)
        return entry, out, good

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
            # 多语言源段双跳：模型对含假名/重音/罗曼功能词的段（意语
            # "Ve ne preghiamo" 等）倾向输出英语译文 → 以英语译文为中间源
            # 再译中文（alisa-demo 实证：长句逐段修复时短段被模型译成英语）
            if (_is_multilingual_source(part)
                    and not _CJK.search(translated)
                    and _ENGLISH_WORD.search(translated)):
                via, via_usage = native_translate(
                    translated.strip(), target_lang, self.references)
                self._record_usage(via_usage)
                if isinstance(via, str) and via.strip():
                    translated = via
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
        # 知识库特殊文本：全大写动作指令/间隔动作词是可翻译语义文本，
        # 不得当专名豁免（taxes 'TOSS TRASH' 实证：全大写无小写词、
        # 不在 UI 词典 → 曾回显被豁免放行）
        special_action = _is_uppercase_action(
            entry.original) or _is_spaced_action(entry.original)
        proper_name_echo = (
            letters_source
            and letters_source == letters_target
            and not has_independent_lower_word(entry.original)
            and not special_action
            # 多语言源（含假名/重音/罗曼功能词）回显默认仍可豁免（法语人名
            # Stefánsson、日文频道名 Korone Ch. 是专名）——仅当同 obj 已有
            # 成功译文（多语言打包数组/对话流对象，如 alisa-demo 的四语言
            # 物品名）时禁止豁免：Clé Pomme 与 Iron Key 同 obj，须翻译。
            and (not _is_multilingual_source(entry.original)
                 or proper_name
                 or not self._obj_reference_pairs(entry))
            # UI 词检查跳过末位版本词（"UCLA Gold" 的 Gold 是版本后缀，
            # 回显保留合理——见 quality._ui_check_words，baldis 实证）
            # 驼峰技术缩写（VSync）即使进 UI 词典也允许回显：界面标准术语
            # （butterflies 实证：'VSync' 回显被判 target_script_mismatch）
            and not any(
                (word.casefold() in _DISPLAY_WORDS_CASEFOLD
                 or word.casefold() in _BUILTIN_UI_TERMS_CASEFOLD)
                and not is_camel_tech_abbreviation(word)
                for word in _ui_check_words(proper_name_words)))
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
                SAFE_KEEPERS.sub(" ", entry.original)
                .translate(_ACCENT_TO_ASCII))}
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
        # 原文引号内片段的英文词：译文保留原文引文是正确行为（见模块级
        # _QUOTE_CONTENT 注释）——仅当译文已含中文翻译（纯回显不豁免）
        quote_words: set[str] = set()
        for match in _QUOTE_CONTENT.finditer(entry.original):
            quote_words.update(
                word.casefold()
                for word in _ENGLISH_WORD.findall(
                    match.group(1).translate(_ACCENT_TO_ASCII)))
        if any(char.isalpha() and not char.isascii()
               and not self._is_chinese_ideograph(char)
               and not (char in source_foreign and has_chinese)
               for char in semantic):
            return True
        # 重音归一化串：英文词提取专用（_ENGLISH_WORD 纯 ASCII 会拆碎
        # 带重音专名 → 小写碎片误判英文残留）。长度不变（一对一词符），
        # finditer 索引与 semantic 对齐；非 ASCII 字母检查已在上面用原串完成
        semantic_ascii = semantic.translate(_ACCENT_TO_ASCII)
        # 签名位豁免：原文破折号后的尾部小写名（"Turkish Localization -
        # yamur <3" 的 yamur 是译者署名）→ 译文保留是正确行为。
        # 要求译文已含中文翻译（纯回显 "Turkish Localization - yamur" 不豁免）
        signature_words: set[str] = set()
        parts = re.split(r"[-–—]\s+", entry.original)
        if len(parts) > 1:
            signature_words = {
                word.casefold()
                for word in _ENGLISH_WORD.findall(
                    parts[-1].translate(_ACCENT_TO_ASCII))}
        # 问候行豁免：译文首行以问候语开头（Hello, there. / Hi!）且首行英文词
        # ≤2 个、译文已含中文 → 问候保留是本地化惯例（mimic-search 的
        # "Hello,\n\n\n几小时前…"、soul-delivery 的 "Hello, there.\n\n在过去的
        # 6个月里…"）。纯回显（无中文）不豁免。
        greeting_words: set[str] = set()
        first_line = translation.splitlines()[0] if translation.splitlines() else ""
        first_words = _ENGLISH_WORD.findall(
            first_line.translate(_ACCENT_TO_ASCII))
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
                for match in re.finditer(
                    r">([A-Za-z]{3,})<",
                    translation.translate(_ACCENT_TO_ASCII))}
        # 连续英文短语（词间无中文间隔）→ 明确半翻，判失败；
        # 但短语中全为专名形态（TitleCase/全大写且非词典词，如 "Amitte Sukku"
        # 人名并列、Escape 按键名）不算英文残留
        # 数字邻接词（"4chan" 的 chan、"23andMe" 的 and）：数字+字母混合形态
        # 多为网站/用户名/版本号（backrooms 实证：译文保留 "4chan" 被拆出
        # 小写碎片 "chan" → 误判英文残留）；要求原文也含该词（防模型幻觉）
        digit_adjacent_words = {
            match.group(0).casefold()
            for match in _ENGLISH_WORD.finditer(semantic_ascii)
            if (match.start() > 0
                and semantic_ascii[match.start() - 1].isdigit())
            or (match.end() < len(semantic_ascii)
                and semantic_ascii[match.end()].isdigit())}
        # 词级补译确认的保留词（'itch page' 补译 → 模型输出保留 itch 专名）
        # → 仅本条生效的豁免（补译时已校验词在原文出现，防幻觉）
        word_residue_exempt = {
            str(word).casefold()
            for word in entry.meta.get("word_residue_exempt", [])}
        # 模型小写化专名：原文 TitleCase 词在译文以小写出现（Bossfight →
        # bossfight）→ 专名保留、大小写形态差异不算英文残留（baldis 实证：
        # 'Triangle Button: Pause (Quit In The Bossfight Gamemode)' 译文
        # '…bossfight 游戏模式…'）。UI 词典词除外（Save → save 是真漏翻）。
        title_in_source = {
            word.casefold()
            for word in _ENGLISH_WORD.findall(
                SAFE_KEEPERS.sub(" ", entry.original))
            if word[0].isupper()}
        lowercased_proper = {
            word.casefold() for word in title_in_source
            if word.casefold() not in _DISPLAY_WORDS_CASEFOLD
            and word.casefold() not in _BUILTIN_UI_TERMS_CASEFOLD
            and word.casefold() not in _ENGLISH_FUNCTION_WORDS}
        # 译文引号内的 TitleCase 短语：模型用引号包裹专名（游戏内按钮名/
        # 关卡名/成就名，如 按钮 "Jump During Playtime"）是稳定行为——
        # 引号是模型对专名的强调标记，保留原文合理（baldis 实证：Button
        # 类条目模型输出 按钮"Jump During Playtime" 被当英文短语误判）。
        # 每个词都须在原文出现（防误译放行：X Button 的 "Jump Along"——
        # Along 不在原文 → 是模型直译误译的专名，不得豁免）。
        # 公共实现见 quality.quoted_proper_terms（交互动作词检查共用）
        translated_quote_proper = quoted_proper_terms(
            translation.translate(_ACCENT_TO_ASCII),
            SAFE_KEEPERS.sub(" ", entry.original)
            .translate(_ACCENT_TO_ASCII)) if has_chinese else set()
        phrase = _ENGLISH_PHRASE.search(semantic_ascii)
        if phrase:
            semantic_words = _ENGLISH_WORD.findall(semantic_ascii)
            # 短语覆盖的语义词索引（按在全文中的位置对齐 —— 邻居判断必须
            # 用全文：'Fun New' 中 New 的右邻 School 在短语外）
            p_indices = [
                i for i, m in enumerate(_ENGLISH_WORD.finditer(semantic_ascii))
                if phrase.start() <= m.start() and m.end() <= phrase.end()]
            for i in p_indices:
                word = semantic_words[i]
                if word.casefold() in PHYSICAL_KEY_NAMES_CASEFOLD:
                    continue
                if word.casefold() in display_names:
                    continue
                if (word.casefold() in quote_words and has_chinese):
                    continue
                if (word.casefold() in signature_words and has_chinese):
                    continue
                if word.casefold() in greeting_words:
                    continue
                if (word.casefold() in rich_words and has_chinese):
                    continue
                if (word.casefold() in digit_adjacent_words
                        and word.casefold() in source_terms_cf):
                    continue
                if word.casefold() in word_residue_exempt:
                    continue
                if word.casefold() in translated_quote_proper:
                    continue
                # 模型小写化专名：原文 TitleCase 词在译文小写残留
                # （Bossfight → bossfight）→ 专名保留不是漏翻
                if word.islower() and word.casefold() in lowercased_proper:
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
        semantic_words = _ENGLISH_WORD.findall(semantic_ascii)
        for i, word in enumerate(semantic_words):
            if word.casefold() in PHYSICAL_KEY_NAMES_CASEFOLD:
                continue
            if word.casefold() in display_names:
                continue
            if (word.casefold() in quote_words and has_chinese):
                continue
            if (word.casefold() in signature_words and has_chinese):
                continue
            if word.casefold() in greeting_words:
                continue
            if (word.casefold() in rich_words and has_chinese):
                continue
            if (word.casefold() in digit_adjacent_words
                    and word.casefold() in source_terms_cf):
                continue
            if word.casefold() in word_residue_exempt:
                continue
            if word.casefold() in translated_quote_proper:
                continue
            # 模型小写化专名：原文 TitleCase 词在译文小写残留
            # （Bossfight → bossfight）→ 专名保留不是漏翻
            if word.islower() and word.casefold() in lowercased_proper:
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
