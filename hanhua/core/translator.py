from __future__ import annotations
import json
import re
import time
from dataclasses import dataclass
from typing import Callable

import httpx

from hanhua.core.engine_strings import CORE_MENU_SOURCE_TERMS
from hanhua.core.models import ApiConfig

class _RetryableStatusError(RuntimeError):
    """瞬时状态码（429/500/503/504）→ 按指数退避重试。"""


class _FatalStatusError(RuntimeError):
    """服务端明确拒绝（4xx）或坏状态（502）→ 立即失败交给上层恢复。"""


MAX_RETRIES = 3
# 可重试的瞬时状态码。502 不在其中：本地 llama-server 返回 502 说明服务
# 已进入坏状态（CUDA OOM / 请求处理崩溃），重试只会排队叠加、雪崩更重 →
# 快速失败交给上层恢复循环（重启服务后重试）。
RETRY_STATUS = {429, 500, 503, 504}
BUILTIN_UI_REFERENCES = (
    ("Settings", "设置"),
    ("Quit", "退出"),
    ("Resolution", "分辨率"),
    ("SFX", "音效"),
    ("Volume", "音量"),
    ("Resume", "继续"),
    # 2026-08-14 用户实证：play 被译「播放」且多次报告——此前不在
    # 内置引用表，模型自由发挥最常见义「播放」；按钮/菜单语境下
    # Play 指「开始游戏」。入表后 prompt 注入 + Q1 语义门 + 主循环
    # 确定性替换三重生效（审核系统提示术语段同源：Start=开始）
    ("Play", "开始"),
    ("Controls", "控制"),
    # 高频回显词（真实语料：cell-machine/final-shot 'back'、faerie-afterlight
    # 'hello'、deepest-sword 'press any key'、hybrid-presence 'Default' 模型
    # 回显原文）→ 参考译文引导模型输出中文
    ("Back", "返回"),
    ("Hello", "你好"),
    ("Press any key", "按任意键"),
    ("Default", "默认"),
    # 独立游戏平台名 itch.io（backrooms 实证：'available at itch page'
    # 模型把 itch 当普通词直译「痒页面」；保留型引用引导模型保留平台名
    # → 'itch 页面'。上下文均为 "on/at itch (page/store/…)" 平台语境，
    # 普通词「痒」在游戏文本中几乎不出现，保留引用误伤风险可忽略）
    ("itch", "itch"),
    # Unity Input System 标准操作提示（containment 实证：'Interact hold'
    # 批量首译回显 + 词级补译跳过 TitleCase + 专名重译注入 (Interact,
    # Interact) 后模型把整条当术语回显）→ 短语级参考译文直接引导；
    # 单独 "Interact" 提示词由动作词排除（见 _retry_with_proper_name_
    # reference 的 _ACTION_VERB_ZH 过滤）避免专名引用陷阱
    ("Interact hold", "交互（长按）"),
    ("Interact", "交互"),
)
BUILTIN_UI_SOURCE_TERMS = CORE_MENU_SOURCE_TERMS


def merge_translation_references(glossary=()) -> tuple[tuple[str, str], ...]:
    """Combine built-in UI references with user terms; user terms win."""
    user_pairs: list[tuple[str, str]] = []
    for item in glossary:
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            source, target = item[0], item[1]
        elif isinstance(item, dict):
            source, target = item.get("term"), item.get("translation")
        else:
            source = getattr(item, "term", None)
            target = getattr(item, "translation", None)
        if (isinstance(source, str) and source.strip()
                and isinstance(target, str) and target.strip()):
            user_pairs.append((source, target))
    user_sources = {source.casefold() for source, _ in user_pairs}
    return tuple(
        pair for pair in BUILTIN_UI_REFERENCES
        if pair[0].casefold() not in user_sources
    ) + tuple(user_pairs)


@dataclass
class Usage:
    prompt: int = 0
    completion: int = 0


def normalize_base_url(base_url: str, provider: str) -> str:
    url = base_url.strip().rstrip("/")
    if provider == "anthropic":
        if url.endswith("/messages"):
            return url
        return url + ("/messages" if url.endswith("/v1") else "/v1/messages")
    if url.endswith("/chat/completions"):
        return url
    return url + ("/chat/completions" if url.endswith("/v1") else "/v1/chat/completions")


class BaseClient:
    def __init__(self, config: ApiConfig, transport_factory: Callable | None = None):
        self.config = config
        provider = "openai" if config.mode == "local" else config.provider
        self.url = normalize_base_url(config.base_url, provider)
        self._factory = transport_factory or (lambda: httpx.Client(timeout=config.timeout))

    def _post(self, url: str, headers: dict, payload: dict) -> tuple[httpx.Response, Usage]:
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with self._factory() as client:
                    resp = client.post(url, headers=headers, json=payload)
                if resp.status_code in RETRY_STATUS:
                    raise _RetryableStatusError(
                        f"HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code >= 400:
                    # 4xx / 502：明确拒绝或服务坏状态 → 立即失败，不重试
                    raise _FatalStatusError(
                        f"HTTP {resp.status_code}: {resp.text[:300]}")
                return resp, self._parse_usage(resp.json())
            except _FatalStatusError:
                raise
            except Exception as e:  # noqa: BLE001 瞬时错误（含 _RetryableStatusError）
                last_err = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1.5 * (2 ** attempt))
        raise RuntimeError(f"请求失败（重试{MAX_RETRIES}次）：{last_err}")

    def _parse_usage(self, data: dict) -> Usage:
        raise NotImplementedError

    def chat(self, system: str, messages: list[dict]) -> tuple[str, Usage]:
        raise NotImplementedError


class OpenAIClient(BaseClient):
    def chat(self, system: str, messages: list[dict]) -> tuple[str, Usage]:
        payload = {
            "model": self.config.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        # 结构化输出：部分兼容端点不支持 response_format，失败时降级重试
        try:
            payload["response_format"] = {"type": "json_object"}
            resp, usage = self._post(self.url, headers, payload)
        except RuntimeError as e:
            if "response_format" not in str(e) and not any(
                    s in str(e) for s in ("400", "validation", "invalid_request")):
                raise
            del payload["response_format"]
            resp, usage = self._post(self.url, headers, payload)
        content = resp.json()["choices"][0]["message"]["content"]
        return content, usage

    def _parse_usage(self, data: dict) -> Usage:
        u = data.get("usage", {})
        return Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))


class LocalOpenAIClient(OpenAIClient):
    """llama-server adapter following Hy-MT2's no-system-prompt contract."""

    accepts_plain_single = True

    _TARGET_LANGUAGE_NAMES = {
        "zh-cn": "Simplified Chinese",
        "zh-hans": "Simplified Chinese",
        "zh-tw": "Traditional Chinese",
        "zh-hant": "Traditional Chinese",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "ru": "Russian",
    }

    # 单用户消息源文本长度上限（字符）：llama-server 槽位 1024 tokens，
    # 英文约 3 字符/token——3183 字符歌词 = 1099 tokens 超限被拒
    # （deadbeat 实证：request_error）。700 字符 ≈ 230 tokens，留足
    # prompt 引导与术语引用空间
    _MAX_PROMPT_SOURCE_CHARS = 700

    def translate_text(
            self, source_text: str, target_lang: str,
            glossary=()) -> tuple[str, Usage]:
        """Translate one segment with Hy-MT2's official single-user prompt."""
        if len(source_text) > self._MAX_PROMPT_SOURCE_CHARS:
            return self._translate_chunked(
                source_text, target_lang, glossary)
        return self._translate_single(source_text, target_lang, glossary)

    def _translate_single(
            self, source_text: str, target_lang: str,
            glossary=()) -> tuple[str, Usage]:
        language_name = self._TARGET_LANGUAGE_NAMES.get(
            str(target_lang).strip().casefold(), str(target_lang).strip())
        lines: list[str] = []
        terms = [
            (str(source), str(target))
            for source, target in glossary
            if str(source).strip() and str(target).strip()
            and str(source).casefold() in source_text.casefold()
        ]
        if terms:
            lines.append("Reference the following translations:")
            lines.extend(
                f"{source} translates to {target}"
                for source, target in terms
            )
            lines.append("")
        lines.extend([
            f"Translate the following text into {language_name}. "
            "Note that you should only output the translated result without "
            "any additional explanation:",
            "",
            source_text,
        ])
        return self.chat("", [{"role": "user", "content": "\n".join(lines)}])

    def _translate_chunked(
            self, source_text: str, target_lang: str,
            glossary=()) -> tuple[str, Usage]:
        """超长文本按行分块翻译后拼接（deadbeat 歌词 3183 字符实证：
        单条请求 1099 tokens 超槽位被拒；逐块请求每块在槽位内）。

        分块边界优先换行（歌词/长文天然分行）；无换行按词切。块间以
        \n 拼接保持行结构近似。逐块串行（llama-server 槽位共享）。"""
        chunks, joiner = self._chunk_source(source_text)
        parts: list[str] = []
        total = Usage(0, 0)
        for chunk in chunks:
            out, usage = self._translate_single(
                chunk, target_lang, glossary)
            parts.append(out)
            total = Usage(
                total.prompt + usage.prompt,
                total.completion + usage.completion)
        return joiner.join(parts), total

    def translate_lyrics(
            self, source_text: str, target_lang: str,
            glossary=()) -> tuple[str, Usage]:
        """歌词/韵律行专用翻译：中文引导 + 输出限长 + 高重复惩罚。

        1.8B 模型对纯英文歌词句稳定续写英文而非翻译（deadbeat
        'Tonight, the moon has rose...' 2677 字符歌词实证：常规 prompt
        输出英文续写被质量门拒绝）——中文引导显式声明「歌词翻译」触发
        翻译意愿；repeat_penalty 1.35 抑制循环续写；max_tokens 按源句
        长缩放，在续写垃圾出现前截断译文。逐句调用（multiline repair
        已拆句）。

        超长歌词（> _MAX_PROMPT_SOURCE_CHARS）分块翻译：1.8B 对超长
        歌词的单次输出上限约 700 字符（deadbeat 'Modern-day killers'
        3183 字符歌词实证：max_tokens 放大后模型 ~430 tokens 主动 EOS，
        输出 700 字符摘要式译文——开头+结尾、中间 2/3 丢失）→ 分块后
        每块 ≤700 字符，模型对每块输出完整译文，拼接恢复全歌。"""
        if len(source_text) > self._MAX_PROMPT_SOURCE_CHARS:
            chunks, joiner = self._chunk_source(source_text)
            parts: list[str] = []
            total = Usage(0, 0)
            for chunk in chunks:
                out, usage = self._translate_lyrics_single(
                    chunk, target_lang, glossary)
                parts.append(str(out).strip())
                total = Usage(
                    total.prompt + usage.prompt,
                    total.completion + usage.completion)
            return joiner.join(parts), total
        return self._translate_lyrics_single(
            source_text, target_lang, glossary)

    def _translate_lyrics_single(
            self, source_text: str, target_lang: str,
            glossary=()) -> tuple[str, Usage]:
        """单块歌词翻译（translate_lyrics 内部实现；分块路径逐块复用）。"""
        language_name = self._TARGET_LANGUAGE_NAMES.get(
            str(target_lang).strip().casefold(), str(target_lang).strip())
        lines: list[str] = []
        terms = [
            (str(source), str(target))
            for source, target in glossary
            if str(source).strip() and str(target).strip()
            and str(source).casefold() in source_text.casefold()
        ]
        if terms:
            lines.append("Reference the following translations:")
            lines.extend(
                f"{source} translates to {target}"
                for source, target in terms
            )
            lines.append("")
        lines.extend([
            f"这是一段歌词，翻译成{language_name}。只输出翻译后的歌词文本，",
            "不要解释，不要续写原文，不要输出任何英文或原文。",
            "",
            source_text,
        ])
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": "\n".join(lines)}],
            "temperature": 0.7,
            "top_p": 0.6,
            "top_k": 20,
            "repeat_penalty": 1.35,
            # 歌词多为中英日混写，译文中文 1 字符 ≈ 1.2 token——旧缩放
            # len//3+32 按英语假设（3 字符/token）给预算，3183 字符歌词
            # 只给 1093 tokens → 中文翻译 ~1200 字符后预算耗尽，模型
            # 续写原文英文回显被判 target_script_mismatch（deadbeat
            # 'Modern-day killers' 歌词 3 条实证）。按 1 字符 ≈ 1 token
            # 缩放 + 余量，配合 llama-server ctx 6144（prompt ~1100 +
            # 完整译文 ~3100 tokens 装得下）。
            "max_tokens": min(self.config.max_tokens,
                              len(source_text) + 128),
        }
        response, usage = self._post(
            self.url,
            {"Authorization": f"Bearer {self.config.api_key}"}, payload,
        )
        content = response.json()["choices"][0]["message"]["content"]
        return content, usage

    @classmethod
    def _chunk_source(cls, text: str) -> tuple[list[str], str]:
        """按行切 ≤_MAX_PROMPT_SOURCE_CHARS 块（无换行按词切）。

        返回 (块列表, 拼接分隔符)——分隔符与切分单位一致（\n 或空格），
        块译文按同分隔符拼接保持原文结构无损。"""
        limit = cls._MAX_PROMPT_SOURCE_CHARS
        if "\n" in text:
            chunks: list[str] = []
            cur = ""
            for line in text.split("\n"):
                if cur and len(cur) + 1 + len(line) > limit:
                    chunks.append(cur)
                    cur = line
                else:
                    cur = f"{cur}\n{line}" if cur else line
            if cur:
                chunks.append(cur)
            return chunks, "\n"
        chunks = []
        cur = ""
        for word in text.split(" "):
            if cur and len(cur) + 1 + len(word) > limit:
                chunks.append(cur)
                cur = word
            else:
                cur = f"{cur} {word}" if cur else word
        if cur:
            chunks.append(cur)
        return chunks, " "

    def chat(self, system: str, messages: list[dict]) -> tuple[str, Usage]:
        merged = "\n\n".join(
            part for part in [system.strip()] + [
                str(message.get("content", "")).strip() for message in messages
            ] if part
        )
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": merged}],
            "temperature": 0.7,
            "top_p": 0.6,
            "top_k": 20,
            "repeat_penalty": 1.05,
            "max_tokens": self.config.max_tokens,
        }
        response, usage = self._post(
            self.url,
            {"Authorization": f"Bearer {self.config.api_key}"}, payload,
        )
        content = response.json()["choices"][0]["message"]["content"]
        return content, usage


class AnthropicClient(BaseClient):
    def chat(self, system: str, messages: list[dict]) -> tuple[str, Usage]:
        payload = {
            "model": self.config.model,
            "system": system,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        resp, usage = self._post(self.url, {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
        }, payload)
        content = "".join(b.get("text", "") for b in resp.json().get("content", [])
                          if b.get("type") == "text")
        return content, usage

    def _parse_usage(self, data: dict) -> Usage:
        u = data.get("usage", {})
        return Usage(u.get("input_tokens", 0), u.get("output_tokens", 0))


def create_client(config: ApiConfig, transport_factory: Callable | None = None) -> BaseClient:
    if config.mode == "local":
        return LocalOpenAIClient(config, transport_factory)
    if config.provider == "anthropic":
        return AnthropicClient(config, transport_factory)
    return OpenAIClient(config, transport_factory)


def extract_json_array(text: str) -> list[dict] | None:
    """宽容 JSON 提取：去代码块围栏 → 平衡括号解析 → 支持 {"translations": [...]} 包装与单对象。"""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip()).strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        start = t.find(opener)
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(t)):
            if t[i] == opener:
                depth += 1
            elif t[i] == closer:
                depth -= 1
                if depth == 0:
                    chunk = t[start:i + 1]
                    try:
                        data = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict) and isinstance(data.get("translations"), list):
                        return data["translations"]
                    if isinstance(data, dict) and "id" in data and "translation" in data:
                        return [data]                       # 单条对象 {"id":..., "translation":...}
    return None


_ID_PAT = re.compile(r'"id"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')
_TRANSLATION_PAT = re.compile(
    r'"translation"\s*:\s*("(?:[^"\\]|\\.)*")', re.S)


def extract_json_array_fallback(text: str) -> list[dict] | None:
    """行级兜底：模型输出不是合法 JSON 时，逐条提取 "id" 与 "translation" 字段。
    适用于译文含未转义引号/换行导致整体解析失败的情况。"""
    ids = _ID_PAT.findall(text)
    trs = _TRANSLATION_PAT.findall(text)
    if not ids or len(ids) != len(trs):
        return None
    out: list[dict] = []
    for i, _ in enumerate(ids):
        try:
            out.append({"id": json.loads(f'"{ids[i]}"'), "translation": json.loads(trs[i])})
        except json.JSONDecodeError:
            return None
    return out
