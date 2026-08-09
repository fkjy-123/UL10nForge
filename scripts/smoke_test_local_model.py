"""Real llama-server + Hy-MT2 smoke test used before shipping local mode."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import time

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from hanhua.core.batch_translator import BatchTranslator  # noqa: E402
from hanhua.core.local_model import LocalModelManager  # noqa: E402
from hanhua.core.models import ApiConfig, GameProfile, TextEntry  # noqa: E402
from hanhua.core.prompts import build_system_prompt  # noqa: E402
from hanhua.core.quality import validate_translation_quality  # noqa: E402
from hanhua.core.translator import create_client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server", default=str(PROJECT_ROOT / "runtime" / "llama" / "llama-server.exe"))
    parser.add_argument(
        "--model", default=str(PROJECT_ROOT / "models" / "Hy-MT2-1.8B-Q6_K.gguf"))
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()

    config = ApiConfig(
        mode="local", local_server_path=args.server,
        local_model_path=args.model, local_gpu_layers=0 if args.cpu else -1,
        local_context_size=4096, local_port=0, max_tokens=128,
    )
    manager = LocalModelManager(PROJECT_ROOT, startup_timeout=180)
    runtime = None
    started = time.monotonic()
    try:
        runtime = manager.ensure_running(config)
        elapsed = time.monotonic() - started
        print(
            f"READY backend={runtime.backend} port={runtime.port} "
            f"startup_seconds={elapsed:.2f}")
        runtime_config = ApiConfig(
            mode="local", provider="openai", base_url=runtime.endpoint,
            api_key=runtime.api_key, model=runtime.model, max_tokens=128,
        )
        client = create_client(runtime_config)
        entry = TextEntry(
            "smoke", "prompt/open", "Press E to open",
            meta={
                "role": "display", "reason": "interaction_prompt",
                "confidence": "high",
            },
        )
        stats = BatchTranslator(
            client, batch_size=1, concurrency=1, model=runtime.model,
            lang="en→zh-CN",
            system_prompt=build_system_prompt(GameProfile(), ""),
        ).run([entry])
        translation = entry.translation.strip()
        result = validate_translation_quality(entry, translation)
        if stats.done != 1 or stats.failed:
            raise RuntimeError(
                f"BatchTranslator failed: done={stats.done} failed={stats.failed} "
                f"reasons={entry.quality_reasons}")
        if "E" not in translation:
            raise RuntimeError(f"translation lost input token E: {translation!r}")
        if not any("\u3400" <= char <= "\u9fff" for char in translation):
            raise RuntimeError(f"translation contains no Chinese text: {translation!r}")
        if re.search(r"\b(?:press|open)\b", translation, re.I):
            raise RuntimeError(
                f"translation retained English action words: {translation!r}")
        if not result.passed:
            raise RuntimeError(
                f"translation failed quality gate {result.reasons}: {translation!r}")
        print(
            f"TRANSLATION {translation} "
            f"tokens={stats.input_tokens}/{stats.output_tokens} "
            f"requests={stats.requests}")
        return 0
    finally:
        endpoint = runtime.endpoint.removesuffix("/v1") if runtime else ""
        manager.stop()
        if endpoint:
            try:
                httpx.get(endpoint + "/health", timeout=1.0)
            except httpx.HTTPError:
                print("STOPPED health_unavailable=true")
            else:
                raise RuntimeError("owned llama-server is still reachable after stop")


if __name__ == "__main__":
    raise SystemExit(main())
