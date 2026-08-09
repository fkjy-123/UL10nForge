"""任务 #7 验证：真实本地翻译测速（cache-reuse + 并发 4 提效验证）。

用 LocalModelManager 启动 llama-server（带 --cache-reuse），并发翻译一批
英文句子，报告吞吐与质量抽查。不触碰任何游戏文件。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from hanhua.core.local_model import LocalModelManager
from hanhua.core.models import ApiConfig

SAMPLES = [
    "Hello there!",
    "Welcome to the village of Alvora.",
    "Press E to interact with the lever.",
    "The ancient sword glows with a faint blue light.",
    "You found a health potion (+25 HP).",
    "Quest completed: Defeat the Goblin Chief.",
    "Your inventory is full.",
    "Talk to the blacksmith to upgrade your weapon.",
    "The door is locked. Find the key.",
    "Loading the game world, please wait...",
    "Warning: enemies are approaching from the north.",
    "Settings",
    "Are you sure you want to delete this save file?",
    "Chapter 3: The Forgotten Temple",
    "This item cannot be equipped by your class.",
    "Multiplayer session has ended.",
    "Achievement unlocked: First Blood.",
    "The sun sets over the mountains.",
    "Follow the path to reach the town gates.",
    "An unexpected error occurred. Restart the game.",
]


def main() -> None:
    manager = LocalModelManager(APP_DIR, startup_timeout=180)
    config = ApiConfig(
        mode="local",
        local_gpu_layers=-1,
        local_concurrency=0,          # 自动 → GPU 4
        local_context_size=4096,
        local_keep_alive=True,
    )
    try:
        runtime = manager.ensure_running(config)
    except Exception as exc:
        print(f"[FAIL] 本地模型启动失败: {exc}")
        return 1
    print(f"[OK] runtime: {runtime.backend} parallel={runtime.parallel} "
          f"pid={runtime.pid}")
    print(f"     endpoint: {runtime.endpoint}")

    import httpx

    headers = {"Authorization": f"Bearer {runtime.api_key}"}
    texts = [s for s in SAMPLES for _ in range(3)]  # 60 条
    payload = {
        "model": runtime.model,
        "messages": [
            {"role": "system",
             "content": "You are a professional game localization engine. "
                        "Translate the user's text into Simplified Chinese. "
                        "Output ONLY the translation, no quotes, no notes."},
            {"role": "user", "content": f"Translate:\n{texts[0]}"},
        ],
        "temperature": 0.3,
        "max_tokens": 200,
    }
    # 预热一次（加载模型）
    t0 = time.monotonic()
    resp = httpx.post(runtime.endpoint + "/chat/completions",
                      json=payload, headers=headers, timeout=300)
    resp.raise_for_status()
    warmup = time.monotonic() - t0
    print(f"[预热] {warmup:.1f}s")

    # 并发打满（parallel=4），每条一个请求（与生产 _chat_each 一致）
    import concurrent.futures

    def one(text: str):
        p = {"model": runtime.model, "messages": [
            {"role": "system",
             "content": "You are a professional game localization engine. "
                        "Translate the user's text into Simplified Chinese. "
                        "Output ONLY the translation, no quotes, no notes."},
            {"role": "user", "content": f"Translate:\n{text}"},
        ], "temperature": 0.3, "max_tokens": 200}
        r = httpx.post(runtime.endpoint + "/chat/completions",
                       json=p, headers=headers, timeout=300)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=runtime.parallel) as pool:
        results = list(pool.map(one, texts))
    elapsed = time.monotonic() - t0
    print(f"[测速] {len(texts)} 条 / {elapsed:.1f}s = "
          f"{len(texts) / elapsed:.2f} 条/秒（并发 {runtime.parallel}）")
    print("--- 质量抽查（前 6 条） ---")
    for src, dst in list(zip(texts, results))[:6]:
        print(f"  EN: {src}")
        print(f"  ZH: {dst}")
    manager.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
