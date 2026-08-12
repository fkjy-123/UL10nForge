"""Reranker-0.6B 语境匹配（任务一阶段 3）。

候选语境排序——「哪些候选真正符合当前语境」：启发式候选（语境库跨游戏
相似、术语、知识库）可能有噪声（跨游戏「相似指纹」语义未必相同），
Reranker 对 (查询原文, 候选原文) 排序后只注入高分 Top-3。

分数语义（阶段 0 冒烟实证）：llama.cpp /rerank 输出 raw logits
（e-06~e-07 量级，非 0-1 概率）——绝对值不可跨实例比较，排序本身有
语义。因此 gate 用 **softmax 相对概率**：高分候选概率集中，低分候选
概率接近 0；`min_prob` 阈值过滤「没有区分度」的候选（全部均分时都不
注入）。服务失败降级为不排序直取 Top-K（不阻断翻译链）。

服务管理（RerankService）：独立 rerank_runtime.json（端口 8082，
ctx 4096，固定 CPU，`--rerank` 标志），与翻译/审核实例互不干扰。
"""
from __future__ import annotations

import json
import math
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from .local_model import build_server_command, discover_server
from .model_registry import ModelRegistry, ModelSpec

_RUNTIME_STATE_FILENAME = "rerank_runtime.json"


def _spawn(cmd: list[str], log_path: Path) -> subprocess.Popen:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                         | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    handle = log_path.open("a", encoding="utf-8", errors="replace")
    return subprocess.Popen(
        cmd, cwd=str(Path(cmd[0]).parent), stdout=handle,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", creationflags=creationflags)


def softmax_scores(logits: list[float]) -> list[float]:
    """raw logits → 相对概率（数值稳定：减最大值）。"""
    if not logits:
        return []
    mx = max(logits)
    exp = [math.exp(x - mx) for x in logits]
    total = sum(exp)
    return [e / total for e in exp]


class RerankService:
    """Reranker 本地服务：跨实例复用 + 按需启动（仿 ReviewModelService）。

    端口 8082（ModelRegistry rerank spec），`--rerank` 标志，固定 CPU。
    """

    def __init__(self, app_dir: str | Path, *,
                 process_factory=None, probe=None, sleep=None,
                 token_factory=None, startup_timeout: float = 180.0):
        self.app_dir = Path(app_dir).resolve()
        self._process_factory = process_factory or subprocess.Popen
        self._probe = probe or self._http_probe
        self._sleep = sleep or time.sleep
        self._token_factory = token_factory or (
            lambda: secrets.token_urlsafe(24))
        self.startup_timeout = max(10.0, float(startup_timeout))
        self._process: subprocess.Popen | None = None
        self._runtime: dict | None = None
        self._lock = threading.RLock()

    @property
    def _state_file(self) -> Path:
        return self.app_dir / _RUNTIME_STATE_FILENAME

    def _save_state(self, port: int, api_key: str, model: str,
                    signature: tuple) -> None:
        try:
            self._state_file.write_text(
                json.dumps({
                    "port": int(port), "api_key": api_key,
                    "model": str(model),
                    "signature": [str(item) for item in signature],
                }, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _load_state(self) -> dict | None:
        try:
            if not self._state_file.is_file():
                return None
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("port"), int):
                return None
            return data
        except (OSError, ValueError):
            return None

    @staticmethod
    def _http_probe(base: str, api_key: str, expected_model: str) -> bool:
        try:
            health = httpx.get(base + "/health", timeout=2)
            if health.status_code != 200:
                return False
            models = httpx.get(base + "/v1/models", timeout=2)
            if models.status_code != 200:
                return False
            ids = [str(m.get("id", ""))
                   for m in models.json().get("data", [])]
            return any(expected_model.casefold() in i.casefold()
                       for i in ids)
        except httpx.HTTPError:
            return False

    def _spec(self) -> ModelSpec:
        return ModelRegistry(self.app_dir).by_kind("rerank")

    def ensure_running(self, cancellation_event=None,
                       context_size: int | None = None) -> dict:
        spec = self._spec()
        if not spec.is_available:
            raise RuntimeError(
                f"Reranker 模型缺失：{spec.path}"
                f"（models/ 目录无 Qwen3-Reranker-0.6B GGUF）")
        server = discover_server("", self.app_dir)
        ctx = context_size or spec.default_ctx
        signature = (server, spec.path, spec.port, ctx, -1, 1)
        with self._lock:
            if (self._process is not None
                    and self._process.poll() is None
                    and self._runtime is not None):
                return dict(self._runtime)
        state = self._load_state()
        if state is not None and tuple(state.get("signature", ())) == tuple(
                str(item) for item in signature):
            base = f"http://127.0.0.1:{int(state['port'])}"
            if self._probe(base, str(state.get("api_key", "")),
                           spec.path.stem):
                with self._lock:
                    self._runtime = {
                        "base_url": base + "/v1",
                        "api_key": str(state.get("api_key", "")),
                        "port": int(state["port"]),
                    }
                    return dict(self._runtime)
        if cancellation_event is not None and cancellation_event.is_set():
            raise RuntimeError("Reranker 服务启动已取消")
        api_key = self._token_factory()
        cmd = build_server_command(
            server, spec.path, port=spec.port, api_key=api_key,
            context_size=ctx, gpu_layers=-1, parallel=1,
            cache_reuse=512)
        cmd.extend(("--rerank",))
        cmd.extend(spec.server_args)
        self._stop_locked()
        log_path = self.app_dir / "logs" / "rerank-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            proc = self._process_factory(
                cmd, cwd=str(Path(cmd[0]).parent), stdout=log_path.open(
                    "a", encoding="utf-8", errors="replace"),
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", creationflags=(
                    getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                if sys.platform == "win32" else 0)
        except OSError as exc:
            raise RuntimeError(f"Reranker 服务启动失败：{exc}") from exc
        with self._lock:
            self._process = proc
        deadline = time.monotonic() + self.startup_timeout
        base = f"http://127.0.0.1:{spec.port}"
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                tail = self._log_tail(log_path)
                raise RuntimeError(f"Reranker 服务异常退出（{proc.returncode}）："
                                   f"{tail[-400:]}")
            if cancellation_event is not None and cancellation_event.is_set():
                raise RuntimeError("Reranker 服务启动已取消")
            if self._probe(base, api_key, spec.path.stem):
                self._save_state(spec.port, api_key, spec.path, signature)
                with self._lock:
                    self._runtime = {
                        "base_url": base + "/v1", "api_key": api_key,
                        "port": spec.port,
                    }
                    return dict(self._runtime)
            self._sleep(2.0)
        tail = self._log_tail(log_path)
        raise RuntimeError(f"Reranker 服务启动超时（{self.startup_timeout}s）："
                           f"{tail[-400:]}")

    @staticmethod
    def _log_tail(path: Path, limit: int = 2000) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[-limit:]
        except OSError:
            return "（无日志）"

    def _stop_locked(self) -> None:
        with self._lock:
            proc = self._process
            self._process = None
            self._runtime = None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    # ── 重排 ─────────────────────────────────────────────────────
    def rerank(self, query: str, documents: list[str], *,
               timeout: float = 60.0) -> list[dict]:
        """真实调用 /rerank，返回 [{index, relevance_score(原始 logit)}]。"""
        info = self.ensure_running()
        resp = httpx.post(
            info["base_url"].rstrip("/") + "/rerank",
            headers={"Authorization": f"Bearer {info['api_key']}"},
            json={"model": "local", "query": query,
                  "documents": list(documents)},
            timeout=timeout,
        )
        resp.raise_for_status()
        return list(resp.json().get("results", []))

    def release(self) -> None:
        with self._lock:
            self._process = None
            self._runtime = None

    def stop(self) -> None:
        self._stop_locked()


class RerankGate:
    """候选排序门：raw logits → softmax 相对概率 → Top-K 注入。

    - candidates: list[tuple[candidate, score]]（score 初始可 None——
      服务失败时保持调用方顺序，退化启发式）
    - select_top(query, candidates, top_k=3, min_prob=0.05)：
      softmax 后概率 ≥ min_prob 的 Top-K（封顶注入，不随库增长）
    """

    def __init__(self, service: RerankService | None = None,
                 top_k: int = 3, min_prob: float = 0.05,
                 max_candidates: int = 20):
        self.service = service
        self.top_k = max(1, int(top_k))
        self.min_prob = float(min_prob)
        self.max_candidates = max(1, int(max_candidates))

    @property
    def usable(self) -> bool:
        return self.service is not None

    def select_top(self, query: str, candidates: list,
                   top_k: int | None = None,
                   min_prob: float | None = None) -> list[tuple[object, float]]:
        """排序候选，返回 [(candidate, softmax_prob), ...] Top-K 封顶。

        服务不可用/调用失败 → 原序取 Top-K（prob=0.0，退化不阻断）。
        """
        k = top_k or self.top_k
        if not candidates:
            return []
        candidates = candidates[:self.max_candidates]
        if self.service is None:
            return [(c, 0.0) for c in candidates[:k]]
        try:
            documents = [getattr(c, "source_text", str(c)) for c in candidates]
            results = self.service.rerank(query, documents)
        except (httpx.HTTPError, RuntimeError, KeyError, TypeError):
            # 服务失败降级：不排序直取 Top-K（翻译链不被 rerank 阻断）
            return [(c, 0.0) for c in candidates[:k]]
        by_index = {int(r.get("index", i)): float(r.get("relevance_score", 0.0))
                    for i, r in enumerate(results)}
        logits = [by_index.get(i, 0.0) for i in range(len(candidates))]
        probs = softmax_scores(logits)
        threshold = min_prob if min_prob is not None else self.min_prob
        ranked = sorted(
            ((c, p) for c, p in zip(candidates, probs) if p >= threshold),
            key=lambda item: item[1], reverse=True)
        if not ranked:
            # 全部低于阈值（候选无区分度/噪声）→ 不注入，宁缺毋滥
            return []
        return ranked[:k]


# ── 候选生成（T3-2 启发式融合，上限 20） ─────────────────────────

def generate_candidates(query: str, *,
                        context_store=None, game: str = "",
                        context_hits=None, glossary_rows=(),
                        knowledge_hits=(), limit: int = 20) -> list:
    """融合候选：语境库跨游戏相似 + 调用方预查结果 + 术语 + 知识库译例。

    返回候选对象列表（供 RerankGate.select_top 排序；对象需有
    source_text 属性或可 str()）。上限 limit（默认 20，封顶防库增长）。
    去重键按对象身份（id/fingerprint 区分同原文不同语境记录）。
    """
    candidates: list = []
    seen: set[tuple[str, object]] = set()

    def _key(item, text: str) -> tuple[str, object]:
        entry_id = getattr(item, "id", None)
        fp = getattr(item, "fingerprint", None)
        return (text, entry_id if entry_id is not None else fp)

    if context_hits:
        for item in context_hits:
            text = getattr(item, "source_text", str(item))
            key = _key(item, text)
            if key not in seen:
                seen.add(key)
                candidates.append(item)
    if context_store is not None:
        for entry in context_store.match_similar(
                game, query, limit=limit - len(candidates)):
            key = _key(entry, entry.source_text)
            if key not in seen:
                seen.add(key)
                candidates.append(entry)
    for source, target in glossary_rows:
        if source and str(source) not in {t for t, _ in seen}:
            seen.add((str(source), None))
            candidates.append(str(source))
    for hit in knowledge_hits:
        text = getattr(hit, "pattern", str(hit))
        key = _key(hit, text)
        if key not in seen:
            seen.add(key)
            candidates.append(hit)
    return candidates[:limit]
