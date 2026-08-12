"""四模型真实冒烟 + 审核成本基线（阶段 0 T0-3/T0-4）。

用法：python scripts/model_smoke.py [--all|--translate|--review|--rerank|--embed]
默认全量冒烟；--review 额外跑 100 条审核成本基线。

行为：
- 探测本机硬件 → 打印硬件智能分配方案（hardware_planner）
- 按方案启动对应 llama-server 实例（复用 build_server_command，
  rerank/embed 追加 --rerank/--embeddings 标志）
- 每模型真实调用一次，输出结果与耗时
- --review 基线：100 条短句逐条送审，记录总耗时/吞吐/级别分布
- 结束后停掉自己启动的服务（不动 model_runtime.json 复用的外部实例）
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hanhua.core.hardware_planner import (  # noqa: E402
    describe_plan,
    plan_allocation,
    probe_hardware,
)
from hanhua.core.local_model import (  # noqa: E402
    build_server_command,
    discover_server,
)
from hanhua.core.model_registry import ModelRegistry  # noqa: E402

# 冒烟样本：已知错译（PRESS→媒体，语义错译实证）与正确译文
_SMOKE_CASES = [
    {
        "original": "PRESS TO START",
        "translation": "按媒体开始",      # 语义错译：start 被译成「媒体」
    },
    {
        "original": "PRESS TO START",
        "translation": "按开始键开始",      # 语义正确
    },
    {
        "original": "Save the game",
        "translation": "保存游戏",
    },
    {
        "original": "I don't have enough mana.",
        "translation": "我的法力不足。",
    },
]

# 100 条成本基线样本（短句，模拟真实游戏文本分布）
_BASELINE_ORIGINALS = [
    "Press E to open the door.", "You found a rusty key.",
    "Save the game before you continue?", "Are you sure you want to quit?",
    "Loading...", "Health restored.", "You cannot carry more items.",
    "The cave is too dark to see.", "Quest completed: The Old Mill",
    "Do not go into the forest at night.", "Inventory is full.",
    "Talk to the blacksmith to repair your sword.",
    "This potion restores 50 HP.", "You are over-encumbered.",
    "The door is locked.", "Press Shift to run.", "New quest started.",
    "Your party has leveled up!", "The monster flees in terror.",
    "Options", "Volume", "Brightness", "Language", "Back", "Controls",
    "Sensitivity", "Graphics quality", "Window mode", "Fullscreen",
    "Apply", "Cancel", "Reset to defaults", "Are you sure?",
    "Delete save file?", "This action cannot be undone.",
    "Continue from last checkpoint?", "Checkpoint saved.",
    "You died. Retry?", "Respawn at the nearest shrine.",
    "Buy 10 arrows for 50 gold?", "Not enough gold.",
    "The merchant has new goods.", "Item sold.", "Equip this weapon?",
    "This weapon deals 12 damage.", "You are poisoned.",
    "Use an antidote?", "Your health is critically low.",
    "Run! They are coming!", "Find shelter before the storm.",
    "The village elder needs your help.", "What happened here?",
    "I must find my sister.", "Follow me.", "Stay close to me.",
    "The treasure is in the old well.", "Someone was here recently.",
    "These tracks lead into the hills.", "A wolf howls in the distance.",
    "The night grows colder.", "You feel a presence watching you.",
    "Behind you!", "The bridge is out.", "We need another way around.",
    "Can you swim?", "The water is freezing.", "Hurry!",
    "This way!", "The path splits here.", "Take the left path.",
    "The right path is safer.", "There is a campsite ahead.",
    "Who are you?", "My name is Eira.", "A pleasure to meet you.",
    "I have seen things you wouldn't believe.", "Trust no one.",
    "The prophecy speaks of you.", "You are the chosen one.",
    "I am not ready.", "You will be, in time.", "Train hard.",
    "Swordsmanship is an art.", "Watch your footing.",
    "The tower looms above the village.", "Legends say it is cursed.",
    "No one has returned from there.", "You are braver than most.",
    "Take this sword.", "It belonged to my father.",
    "May it serve you well.", "Goodbye, adventurer.",
    "Until we meet again.", "You saved us all!", "The village is safe now.",
    "A feast in your honor!", "To the hero!", "Cheers!",
    "The war is over.", "Peace has returned to the valley.",
    "What will you do now?", "I will rebuild my home.",
    "That sounds like a fine plan.", "The end.",
]


def _spawn_server(cmd: list[str], log_path: Path) -> subprocess.Popen:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                         | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    handle = log_path.open("a", encoding="utf-8", errors="replace")
    return subprocess.Popen(
        cmd, cwd=str(Path(cmd[0]).parent), stdout=handle, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", creationflags=creationflags)


def _wait_ready(base: str, token: str, model_stem: str, timeout: float = 180) -> bool:
    deadline = time.monotonic() + timeout
    headers = {"Authorization": f"Bearer {token}"}
    while time.monotonic() < deadline:
        try:
            health = httpx.get(base + "/health", headers=headers, timeout=2)
            if health.status_code != 200:
                time.sleep(2)
                continue
            models = httpx.get(base + "/v1/models", headers=headers, timeout=2)
            if models.status_code != 200:
                time.sleep(2)
                continue
            ids = [str(m.get("id", "")) for m in models.json().get("data", [])]
            if any(model_stem.casefold() in i.casefold() for i in ids):
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


def _chat(base: str, token: str, prompt: str, max_tokens: int = 1024) -> tuple[str, float]:
    start = time.monotonic()
    resp = httpx.post(
        base + "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "local", "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.2, "max_tokens": max_tokens},
        timeout=300,
    )
    resp.raise_for_status()
    elapsed = time.monotonic() - start
    return resp.json()["choices"][0]["message"]["content"], elapsed


def _review_prompt(original: str, translation: str) -> str:
    return (
        "你是游戏本地化质量审核员。审核以下译文，输出严格 JSON，不要输出其他文字：\n"
        '{"level": "PASS|MINOR|MAJOR|CRITICAL", "reason": "<中文理由>", '
        '"issues": [{"type": "<错误类型>", "detail": "<详情>", '
        '"suggestion": "<建议译文>"}]}\n'
        "级别定义：PASS 完全正确；MINOR 语义正确但有瑕疵；"
        "MAJOR 语义有偏差需修正；CRITICAL 语义错误不可用。\n"
        f"原文: {original}\n译文: {translation}"
    )


def smoke_translate(base: str, token: str) -> None:
    print("\n[translate] Hy-MT2-1.8B 冒烟（1 条翻译）")
    content, elapsed = _chat(
        base, token,
        "Translate the following text into Simplified Chinese. "
        "Only output the translated result without any explanation:\n\nPRESS TO START")
    print(f"  PRESS TO START → {content.strip()!r}  ({elapsed:.1f}s)")


def smoke_review(base: str, token: str) -> None:
    print("\n[review] Qwen3.5-4B 冒烟（4 条审核，含已知错译 PRESS→媒体）")
    for case in _SMOKE_CASES:
        content, elapsed = _chat(base, token, _review_prompt(
            case["original"], case["translation"]), max_tokens=512)
        try:
            data = json.loads(content.strip().lstrip("`").rstrip("`"))
            level = data.get("level", "?")
            reason = data.get("reason", "")[:80]
        except (json.JSONDecodeError, AttributeError):
            level, reason = "PARSE_FAIL", content[:80]
        print(f"  [{level:<8}] {case['original']!r} → {case['translation']!r}  "
              f"({elapsed:.1f}s) {reason}")


def _sigmoid(score: float) -> float:
    """rerank 原始分数归一化：llama.cpp 输出 raw logits（1e-6 量级），
    sigmoid 后映射到 (0,1) 便于比较/阈值（排序不变）。"""
    if score > 0:
        return 1.0 / (1.0 + __import__("math").exp(-score))
    exp = __import__("math").exp(score)
    return exp / (1.0 + exp)


def smoke_rerank(base: str, token: str) -> None:
    print("\n[rerank] Qwen3-Reranker-0.6B 冒烟（Resume 样本排序，"
          "分数经 sigmoid 归一化）")
    payload = {
        "model": "local",
        "query": "Resume the game from where you left off",
        "documents": [
            "Continue the previous game", "Restore health points",
            "回到主菜单", "继续游戏", "Load the latest save file",
        ],
    }
    start = time.monotonic()
    resp = httpx.post(
        base + "/rerank",
        headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=120)
    resp.raise_for_status()
    elapsed = time.monotonic() - start
    results = resp.json().get("results", [])
    ranked = sorted(results, key=lambda r: r.get("relevance_score", 0),
                    reverse=True)
    for item in ranked[:3]:
        raw = item.get("relevance_score", 0)
        print(f"  score={_sigmoid(raw):.4f} (raw {raw:.2e})  "
              f"index={item.get('index')}  ({elapsed:.1f}s)")


def smoke_embed(base: str, token: str) -> None:
    print("\n[embed] Qwen3-Embedding-0.6B 冒烟（1 条 512 维向量）")
    start = time.monotonic()
    resp = httpx.post(
        base + "/v1/embeddings",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "local", "input": "Resume the game"},
        timeout=120,
    )
    resp.raise_for_status()
    elapsed = time.monotonic() - start
    data = resp.json()["data"][0]["embedding"]
    print(f"  dim={len(data)}  first5={[round(v, 3) for v in data[:5]]}  "
          f"({elapsed:.1f}s)")


def run_review_baseline(base: str, token: str) -> None:
    print(f"\n[基线] 审核成本基线：{len(_BASELINE_ORIGINALS)} 条短句逐条送审")
    levels: dict[str, int] = {}
    times: list[float] = []
    fails = 0
    start = time.monotonic()
    for i, original in enumerate(_BASELINE_ORIGINALS):
        translation = f"（译文{i}）"   # 模拟含中文译文，审核只需稳定输出
        try:
            content, elapsed = _chat(base, token, _review_prompt(
                original, translation), max_tokens=256)
            times.append(elapsed)
            try:
                level = json.loads(content.strip().lstrip("`").rstrip("`")).get(
                    "level", "?")
            except (json.JSONDecodeError, AttributeError):
                level = "PARSE_FAIL"
                fails += 1
            levels[level] = levels.get(level, 0) + 1
        except httpx.HTTPError as exc:
            fails += 1
            levels["ERROR"] = levels.get("ERROR", 0) + 1
            if fails > 5:
                print(f"  连续失败 {fails} 次，中止基线：{exc}")
                break
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(_BASELINE_ORIGINALS)}  "
                  f"avg={sum(times[-20:]) / len(times[-20:]):.2f}s/条")
    total = time.monotonic() - start
    ok = len(times)
    print(f"\n基线结果：{ok} 条完成 / {fails} 条失败，总耗时 {total:.1f}s，"
          f"吞吐 {ok / total:.2f} 条/秒，平均 {total / max(1, ok):.2f}s/条")
    print(f"级别分布：{levels}")


def main() -> int:
    which = {arg.lstrip("-") for arg in sys.argv[1:] if arg.startswith("-")}
    if not which or "all" in which:
        which = {"translate", "review", "rerank", "embed"}
    include_baseline = "review" in which or "baseline" in which

    registry = ModelRegistry(ROOT)
    print(registry.describe())
    print(describe_plan(plan_allocation(probe_hardware(), registry)))
    missing = registry.missing
    if missing:
        print(f"\n缺少模型（跳过冒烟）：{', '.join(s.name for s in missing)}")
        return 1

    server = discover_server("", ROOT)
    token = "smoke-test-token"
    processes: list[subprocess.Popen] = []

    try:
        for kind in ("translate", "review", "rerank", "embed"):
            if kind not in which:
                continue
            spec = registry.by_kind(kind)
            extra = list(spec.server_args)
            if kind == "rerank":
                extra.append("--rerank")
            if kind == "embed":
                extra.append("--embeddings")
            cmd = build_server_command(
                server, spec.path, port=spec.port, api_key=token,
                context_size=spec.default_ctx, gpu_layers=-1,
                parallel=1, cache_reuse=512)
            cmd.extend(extra)
            log_path = ROOT / "logs" / f"smoke-{kind}.log"
            print(f"\n启动 [{kind}] {spec.display_name} → "
                  f"http://127.0.0.1:{spec.port} {extra or ''}")
            proc = _spawn_server(cmd, log_path)
            processes.append(proc)
            base = f"http://127.0.0.1:{spec.port}"
            if not _wait_ready(base, token, spec.path.stem):
                tail = log_path.read_text(encoding="utf-8", errors="replace")[-800:]
                print(f"  [失败] {kind} 未就绪：{tail}")
                return 1
            if kind == "translate":
                smoke_translate(base, token)
            elif kind == "review":
                smoke_review(base, token)
            elif kind == "rerank":
                smoke_rerank(base, token)
            else:
                smoke_embed(base, token)
        if include_baseline:
            run_review_baseline(f"http://127.0.0.1:{registry.by_kind('review').port}", token)
        print("\n冒烟完成。")
        return 0
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print(f"已停止 {len(processes)} 个冒烟进程（外部复用实例不受影响）。")


if __name__ == "__main__":
    sys.exit(main())
