# -*- coding: utf-8 -*-
"""本地网络加固回归（2026-08-14 审核卡死实证的锁）。

背景：语义审核的 embedding 语境召回走 httpx 调用本机 llama-server，
httpx 默认 trust_env=True 读环境变量代理 → 本机 127.0.0.1 请求被路由
到代理 → 代理不可达挂起 25 分钟（runner 卡死在 _init_proxy_transport，
py-spy 实证）。修复：所有本地模型服务调用 trust_env=False +
verify=False（本地 http 无需 TLS，跳过 ssl.create_default_context）。
本测试设不可达代理 + 本地假 llama-server，验证请求直连快速完成——
防回归。
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class _FakeLlamaHandler(BaseHTTPRequestHandler):
    """极简假 llama-server：/embeddings 返回一维向量。"""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.path.rstrip("/").endswith("/embeddings"):
            payload = {
                "data": [{"index": 0, "embedding": [1.0, 2.0, 3.0]}],
            }
        else:  # /chat/completions
            payload = {
                "choices": [{"message": {"content": "ok"}}],
            }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_llama_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeLlamaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


def test_local_embed_bypasses_unreachable_proxy(monkeypatch, tmp_path,
                                               fake_llama_server):
    """设不可达代理 → 本地 embedding 请求仍直连快速完成（禁代理生效）。

    修复前：httpx 初始化代理 transport 连不可达代理 → 挂起超时。
    修复后：trust_env=False 直连 127.0.0.1，秒级返回。
    """
    from hanhua.core import vector_store as vs

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")    # 不可达
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")   # 不可达
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    svc = vs.EmbeddingService(tmp_path)
    svc.ensure_running = lambda: {  # noqa: E731 - stub 服务端点
        "base_url": f"http://127.0.0.1:{fake_llama_server}",
        "api_key": "k",
    }
    start = time.monotonic()
    vecs = svc.embed(["hello"])
    elapsed = time.monotonic() - start
    assert len(vecs) == 1 and len(vecs[0]) == 3
    assert elapsed < 10, f"本地请求被代理劫持/挂起：{elapsed:.1f}s"


def test_review_chat_bypasses_unreachable_proxy(monkeypatch, tmp_path,
                                                fake_llama_server):
    """同场景覆盖 review 服务 chat 路径（4B 直送也不被代理劫持）。"""
    from hanhua.core.review_server import ReviewModelService

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    svc = ReviewModelService(tmp_path)
    svc.ensure_running = lambda: {  # noqa: E731 - stub 服务端点
        "base_url": f"http://127.0.0.1:{fake_llama_server}",
        "api_key": "k",
    }
    # chat 走 /chat/completions——假服务返回 embeddings 结构也能 200，
    # 断言的是「不卡代理、能完成往返」
    start = time.monotonic()
    svc.chat("hello", max_tokens=8)
    elapsed = time.monotonic() - start
    assert elapsed < 10, f"审核请求被代理劫持/挂起：{elapsed:.1f}s"


# ── sha256 缓存（审核高频 ensure_running 重算 1.4GB 模型拖慢） ────

def test_sha256_cached_no_recompute(monkeypatch, tmp_path):
    """同文件同 stat → 第二次调用不重算（缓存命中）。"""
    import hashlib
    from hanhua.core.local_model import sha256_of

    model = tmp_path / "m.gguf"
    model.write_bytes(b"x" * (1 << 20))     # 1MB
    calls = []

    real_sha256 = hashlib.sha256
    def counting_sha256(*args, **kwargs):
        calls.append(1)
        return real_sha256(*args, **kwargs)

    monkeypatch.setattr(hashlib, "sha256", counting_sha256)
    first = sha256_of(model)
    assert len(calls) == 1
    second = sha256_of(model)                # 命中缓存，不重算
    assert len(calls) == 1
    assert first == second


def test_sha256_recomputed_on_change(tmp_path):
    """文件内容变化（size/mtime 变）→ 重算 → 签名变化。"""
    from hanhua.core.local_model import sha256_of

    model = tmp_path / "m.gguf"
    model.write_bytes(b"v1-content")
    h1 = sha256_of(model)
    model.write_bytes(b"v2-different-content")
    h2 = sha256_of(model)
    assert h1 != h2


def test_sha256_unreadable_returns_marker(tmp_path):
    from hanhua.core.local_model import sha256_of
    assert sha256_of(tmp_path / "missing.gguf") == "unreadable"
