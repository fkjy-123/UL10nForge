"""ctx 预算降级 / 知识命中注入测试。

2026-08-14 用户实证：--ctx-size 6144 实际 2048——llama-server 在 KV
显存不足时启动自动降级（--parallel 3 → 每槽 6144/3=2048），客户端按
配置组装 prompt 必超限被拒（request (2889 tokens) exceeds context）。

覆盖：
- probe_context_size：/props 探测实际 n_ctx，缓存一次，失败回退
- _prompt_over_budget：组装前估算超实际 ctx×0.7 → 整批逐条降级
- context_overflow：单条仍超限 → 明确失败原因（替代笼统 request_error）
- knowledge_hits：按原文 match_text 命中注入（不全量拼 system_prompt），
  形态规则/空 map_to 跳过，检索故障不阻断翻译
"""

from types import SimpleNamespace

from hanhua.core.batch_translator import BatchTranslator
from hanhua.core.models import TextEntry
from hanhua.core.translator import LocalOpenAIClient
from tests.test_batch_translator import FakeClient


class ProbeClient(FakeClient):
    """带 probe_context_size 且记录组装 prompt 的假客户端。"""

    def __init__(self, mapping=None, probe=8192):
        super().__init__(mapping)
        self._probe = probe
        self.prompts: list[str] = []

    def probe_context_size(self):
        return self._probe

    def chat(self, system, messages):
        self.prompts.append(system + "\n" + messages[0]["content"])
        return super().chat(system, messages)


class FakeKnowledge:
    """按原文返回命中规则的假知识库（结构对齐 KnowledgeBase.match_text）。"""

    def __init__(self, rules_by_text: dict):
        self.rules_by_text = rules_by_text

    def match_text(self, original: str):
        return list(self.rules_by_text.get(original, ()))


def _entry(original, **meta):
    return TextEntry("f", "k", original, meta={
        "role": "display", "disposition": "translate", "confidence": "high",
        **meta})


def test_probe_context_size_reads_props_once_and_caches():
    """探测 /props 拿实际 n_ctx；成功后缓存（同一实例不再请求）。"""

    class FakeTransport:
        def __init__(self):
            self.requests = 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, timeout=None, headers=None):
            self.requests += 1
            resp = SimpleNamespace(status_code=200)
            resp.json = lambda: {"default_generation_settings": {"n_ctx": 2048}}
            return resp

    cfg = SimpleNamespace(mode="local", provider="openai",
                          base_url="http://127.0.0.1:8080/v1",
                          api_key="k", timeout=30)
    transport = FakeTransport()
    client = LocalOpenAIClient(cfg, transport_factory=lambda: transport)
    client._probed_ctx = None
    assert client.probe_context_size() == 2048
    assert client.probe_context_size() == 2048   # 缓存命中，不再请求
    assert transport.requests == 1               # 只发过一次请求


def test_probe_context_size_failure_cached():
    """探测失败（非 200）→ None 且失败也缓存（_probed_ctx=-1 不再重试）。"""

    class FailTransport:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, timeout=None, headers=None):
            resp = SimpleNamespace(status_code=500)
            resp.json = lambda: {}
            return resp

    cfg = SimpleNamespace(mode="local", provider="openai",
                          base_url="http://127.0.0.1:8080/v1",
                          api_key="k", timeout=30)
    client = LocalOpenAIClient(cfg, transport_factory=lambda: FailTransport())
    client._probed_ctx = None
    assert client.probe_context_size() is None
    assert client._probed_ctx == -1              # 失败标记，不再重试
    assert client.probe_context_size() is None


def test_batch_over_budget_degrades_to_each_with_context_overflow():
    """实际 ctx 小（服务端降级 2048 场景）+ 大 system_prompt → 整批
    降级逐条；单条仍超预算 → 明确 context_overflow（替代笼统
    request_error），且一个请求都不发出。"""
    system = "翻译规则：" + "术语对照表条目" * 100   # 中文 ≈ 600+ token
    client = ProbeClient(mapping={"text1": "文本一", "text2": "文本二"},
                         probe=500)
    bt = BatchTranslator(client, batch_size=2, concurrency=1,
                         lang="en→zh-CN", system_prompt=system)
    entries = [_entry("text1"), _entry("text2")]
    stats = bt.run(entries)
    assert client.calls == 0                     # 组装前拦截，零请求
    assert all(e.status == "failed" for e in entries)
    assert all(e.quality_reasons == ("context_overflow",) for e in entries)
    assert all("request_error_detail" not in e.meta for e in entries)


def test_prompt_within_budget_stays_batched():
    """预算内正常批翻译，不降级。"""
    system = "翻译规则：" + "术语对照表条目" * 2
    client = ProbeClient(mapping={"text1": "文本一"}, probe=8192)
    bt = BatchTranslator(client, batch_size=2, concurrency=1,
                         lang="en→zh-CN", system_prompt=system)
    e = _entry("text1")
    stats = bt.run([e])
    assert client.calls == 1
    assert stats.done == 1 and e.translation == "文本一"


def test_no_probe_falls_back_to_config_ctx():
    """客户端无 probe（远程/旧客户端）→ 回退配置值，不做降级判断。"""
    client = FakeClient(mapping={"text1": "文本一"})   # 无 probe 方法
    bt = BatchTranslator(client, batch_size=2, concurrency=1,
                         lang="en→zh-CN")
    e = _entry("text1")
    stats = bt.run([e])
    assert stats.done == 1 and e.translation == "文本一"


def test_knowledge_hits_injected_only_on_match():
    """知识命中注入：原文命中 → prompt 带 [知识命中] 且只带命中的精确
    对照；形态规则/空 pattern 跳过；未命中条目无注入。"""
    rules = {
        "Reboot the machine": [
            {"pattern": "Reboot the machine", "map_to": "重启机器",
             "kind": "exact"},
            {"pattern": "Hold the button", "map_to": "按住按钮",
             "kind": "spaced_action"},
            {"pattern": "PLAY", "map_to": "播放",
             "kind": "uppercase_action"},
            {"pattern": "", "map_to": "空对照", "kind": "exact"},
        ],
    }
    client = ProbeClient(mapping={
        "Reboot the machine": "重启机器", "Just a line": "就是一行"})
    bt = BatchTranslator(
        client, batch_size=2, concurrency=1, lang="en→zh-CN",
        system_prompt="你是游戏本地化翻译。",
        knowledge=FakeKnowledge(rules))
    hit = _entry("Reboot the machine")
    miss = _entry("Just a line")
    bt.run([hit, miss])
    # 重试链可能多次请求（长度预算等），拼接全部组装 prompt 断言
    content = "\n".join(client.prompts)
    assert "[知识命中]" in content
    assert "“Reboot the machine”应译为“重启机器”" in content
    # 形态规则与空 pattern 被跳过，不注入
    assert "Hold the button" not in content
    assert "PLAY" not in content
    assert "空对照" not in content
    # 命中条目每次都注入（重试链多次组装），未命中条目无注入
    assert content.count("[知识命中]") >= 1


def test_knowledge_hit_exception_does_not_block_translation():
    """match_text 抛异常 → 检索故障不阻断翻译。"""

    class BoomKnowledge:
        def match_text(self, original):
            raise RuntimeError("检索故障")

    client = ProbeClient(mapping={"text1": "文本一"})
    bt = BatchTranslator(
        client, batch_size=2, concurrency=1, lang="en→zh-CN",
        system_prompt="你是游戏本地化翻译。", knowledge=BoomKnowledge())
    e = _entry("text1")
    stats = bt.run([e])
    assert stats.done == 1 and e.translation == "文本一"
