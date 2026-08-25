from __future__ import annotations
import json
import re
from pathlib import Path
from hanhua.core.models import TextEntry, STATUS_SKIPPED
from hanhua.core.formats import read_text
from hanhua.core.placeholders import (is_hard_structural, is_vn_command_line,
                                       should_skip)

# key=value / key:value（delim 记录原样分隔符）。
# key 允许前导 tab/空格：tab 缩进的 JSON kv 行（`\t"docMTF":"Mobile Task
# Forces",`）此前 _KV（key 排除 tab）与 _TAB（key 不能以 tab 起）都匹配
# 失败 → 落 plain 被整行翻译 → 写回破坏 JSON（containment-breach-hd 实证）。
_KV = re.compile(r"^(?P<key>[^=:;\r\n]+?)\s*(?P<delim>[:=])\s*(?P<value>.*)$")
_TAB = re.compile(r"^(?P<key>[^\t\r\n]+)\t(?P<value>.*)$")
# NodeEditorFramework 对话脚本行（F51，shellcore 实证 900+ 条对话真
# 盲区）：Text("key", "对话内容")——key 是对话定位键（保留原文），
# 引号内 value 是玩家可见对话文本
_CORESCRIPT_TEXT = re.compile(
    r'^Text\("(?P<key>[^"]+)",\s*"(?P<value>.*)"\)\s*$')

# JSON 字符串值（含尾随逗号）："value" 或 "value",——JSON 语言的
# 值（itemStrings.subs 等 Unity .subs 语言包）。这种 kv 行写回必须
# 保留 JSON 语法（ASCII 引号 + 尾随逗号），否则文件整体 JSON 失效，
# 游戏启动读语言包崩溃卡死（containment-breach-hd 实证：txt 写回
# 用中文弯引号 + 丢逗号 → 汉化游戏卡开场）。
_JSON_VALUE = re.compile(r'^"(?:\\.|[^"\\])*"(?:,)?$')

# markdown 列表项/标题行（Changelog/OriginalGameCredits 等纯文本清单）：
# `*Programmers` / `  *Improved lighting` / `- Fixed` / `# Heading`。
# 行首 marker（*/-/+/数字./# + 缩进）是结构前缀，必须原样保留；只有
# marker 后的内容是玩家可见文本。整行翻译会把 `*Programmers` 变
# `程序员` 丢掉星号（写回破坏列表结构，写回审计确定性拦截）。
_MD_MARKER = re.compile(r"^(\s*)(?:([*+-])|(\d+[.)]))(\s*)(.*)$")
_MD_HEADING = re.compile(r"^(\s*#+\s*)(.*)$")


def _is_json_value(value: str) -> bool:
    """value 是否为完整 JSON 字符串（可带尾逗号）。"""
    if not _JSON_VALUE.match(value):
        return False
    inner = re.match(r'^"((?:\\.|[^"\\])*)"(,)?$', value)
    if not inner:
        return False
    # 转义校验：JSON 合法转义序列（\\、\"、\uXXXX、常见控制转义）。
    # 反斜杠+其它字符是非法 JSON 字符串 → 不是 JSON 值（如 Windows
    # 路径 'C:\foo' 裸反斜杠），走普通 txt 替换。
    s = inner.group(1)
    i = 0
    while i < len(s):
        if s[i] != "\\":
            i += 1
            continue
        if i + 1 >= len(s):
            return False
        nxt = s[i + 1]
        if nxt == "u":
            if i + 5 >= len(s):
                return False
            if not re.fullmatch(r"[0-9a-fA-F]{4}", s[i + 2:i + 6]):
                return False
            i += 6
        elif nxt in {'"', "\\", "/", "b", "f", "n", "r", "t"}:
            i += 2
        else:
            return False
    return True


def _rewrap_json(translation: str) -> str:
    """把译文包成 JSON 字符串字面量（ASCII 引号 + json.dumps 转义）。

    弯引号 “”→ 直引号 "，逗号/换行由 json.dumps 转义，保证文件级
    JSON 语法不破坏。
    """
    # 兼容模型偶尔输出的中文弯引号包裹（“xxx”）——剥成裸文本再 JSON 编码
    inner = translation
    if inner.startswith("“") and inner.endswith("”"):
        inner = inner[1:-1]            # “xxx”
    elif inner.startswith("“") and inner.endswith("，"):
        inner = inner[1:-2]            # “xxx”，弯引号+中文逗号回显
    return json.dumps(inner, ensure_ascii=False)


def extract_txt(path: str | Path, file_id: str | None = None) -> list[TextEntry]:
    p = Path(path)
    fid = file_id or p.name
    entries: list[TextEntry] = []
    for i, line in enumerate(read_text(p).splitlines()):
        stripped = line.strip()
        meta = {"line_no": i, "raw": line}
        if not stripped:
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "blank"}))
        elif stripped.startswith("#") or stripped.startswith(";"):
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "comment"}))
        elif (stripped.startswith("//")
              and (len(stripped) == 2 or stripped[2].isspace())):
            # C# 风格注释行（// 后跟空白；//host/path 协议相对 URL 无空白，
            # 已在 is_hard_structural 单独处理）。注释不是游戏文本——
            # 翻译必被质量门拦（baldis TextAsset 脚本注释行实证）。
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "comment"}))
        elif stripped.startswith("[") and stripped.endswith("]"):
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "section"}))
        elif is_vn_command_line(stripped):
            # Yarn <<命令>> / Naninovel @命令 / Ink ===节点头=== 行：
            # 控制流与按名引用结构，翻译破坏脚本解析（通用规则）
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "vn_command"}))
        elif is_hard_structural(stripped):
            # 整行结构值：URL（http://steamworks.github.io 被 _KV 误拆成 key=http 的真实案例）、
            # CLI 参数（Burst 命令记录 --platform=Windows）、协议相对 URL（//host/path）等
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "structural"}))
        elif (p.suffix.lower() == ".corescript"
              and _CORESCRIPT_TEXT.match(stripped)):
            # F51（shellcore 实证）：Text("key", "对话内容") 对话脚本行
            # ——key 是对话定位键（保留原文，写回按 key 行定位），引号
            # 内 value 是玩家可见对话文本
            m = _CORESCRIPT_TEXT.match(stripped)
            value = m.group("value")
            if should_skip(value):
                entries.append(TextEntry(
                    file_id=fid,
                    key_path=f"corescript/{m.group('key')}/{i}",
                    original=value, status=STATUS_SKIPPED,
                    meta={**meta, "kind": "corescript_structural",
                          "cs_key": m.group("key")}))
            else:
                entries.append(TextEntry(
                    file_id=fid,
                    key_path=f"corescript/{m.group('key')}/{i}",
                    original=value,
                    meta={**meta, "kind": "corescript",
                          "cs_key": m.group("key")}))
        else:
            m = _TAB.match(line) or _KV.match(line)
            if m:
                value = m.group("value").strip()
                # Yarn 节点头 title: Start——Start 是 <<jump Start>> 的
                # 跳转目标（按名引用），翻译断跳转；.ini 等配置文件的
                # title= 是显示标题不受影响（按扩展名限定）
                if (p.suffix.lower() == ".yarn"
                        and m.group("key").strip().casefold() == "title"
                        and value):
                    entries.append(TextEntry(
                        file_id=fid, key_path=f"kv/title/{i}",
                        original=value, status=STATUS_SKIPPED,
                        meta={**meta, "kind": "yarn_title",
                              "key": "title", "delim": m.group("delim")}))
                elif not value:
                    # 空值 kv 行（nolog= / key= 空参数）：配置项置空，不是文本。
                    # 此前落入 plain 分支作为可译行（Morfosi boot.config 实证：
                    # 'nolog=' 被模型回显 → untranslated_text 恒败）。写回原样输出。
                    entries.append(TextEntry(
                        file_id=fid, key_path=f"kv/{m.group('key').strip()}/{i}",
                        original=value, status=STATUS_SKIPPED,
                        meta={**meta, "kind": "kv_empty", "key": m.group("key"),
                              "delim": "\t" if m.re is _TAB else m.group("delim")}))
                elif should_skip(value):
                    # kv 值本身是结构/键（Assets/Plugins/x.dll、ui_newGame）不翻译
                    # 注意：_TAB 匹配无 delim 命名组（honorplusplus 实证）
                    entries.append(TextEntry(
                        file_id=fid, key_path=f"kv/{m.group('key').strip()}/{i}",
                        original=value, status=STATUS_SKIPPED,
                        meta={**meta, "kind": "kv_structural",
                              "key": m.group("key"),
                              "delim": "\t" if m.re is _TAB else m.group("delim")}))
                else:
                    delim = "\t" if m.re is _TAB else m.group("delim")
                    entries.append(TextEntry(
                        file_id=fid, key_path=f"kv/{m.group('key').strip()}/{i}",
                        original=value,
                        meta={**meta, "kind": "kv", "key": m.group("key"), "delim": delim}))
            else:
                entries.append(TextEntry(file_id=fid, key_path=f"plain/{i}",
                                         original=line.rstrip("\r"),
                                         meta={**meta, "kind": "plain"}))
    return entries


def apply_txt(entries: list[TextEntry]) -> str:
    """按行号重建。kv 行用 rfind 替换值部分，保留行内其它空白；跳过行原样输出。

    JSON 字符串值（"value",）走 _replace_json_value——保留 ASCII 引号与
    尾随逗号，防 JSON 语言包整体失效（游戏启动读包崩溃）。
    """
    by_line: dict[int, str] = {}
    for e in entries:
        line_no = e.meta["line_no"]
        kind = e.meta.get("kind")
        if kind in ("blank", "comment", "section"):
            by_line[line_no] = e.meta["raw"]
        elif e.status == STATUS_SKIPPED:
            by_line[line_no] = e.meta["raw"]
        elif e.translation:
            if kind == "plain":
                by_line[line_no] = _replace_plain(
                    e.meta["raw"], e.original, e.translation)
            elif kind == "kv" and _is_json_value(e.original):
                by_line[line_no] = _replace_json_value(
                    e.meta["raw"], e.original, e.translation)
            else:
                raw = e.meta["raw"]
                by_line[line_no] = _replace_tail(raw, e.original, e.translation)
        else:
            by_line[line_no] = e.meta["raw"]
    return "\n".join(by_line[i] for i in sorted(by_line))


def _replace_json_value(raw: str, value: str, translation: str) -> str:
    """替换 JSON 字符串值，保留引号内文本之外的语法（引号 + 尾随逗号）。

    value 形如 `"9V Battery",`——原文含 ASCII 引号与逗号。译文重包成
    JSON 字符串字面量（ASCII 引号 + json.dumps 转义），尾随逗号原样保留。
    """
    trailing_comma = value.endswith(",")
    replacement = _rewrap_json(translation) + ("," if trailing_comma else "")
    return _replace_tail(raw, value, replacement)


def _replace_tail(raw: str, value: str, replacement: str) -> str:
    """把 raw 中最后一次出现的 value 替换为 replacement。"""
    idx = raw.rfind(value)
    if idx < 0:
        return raw
    return raw[:idx] + replacement + raw[idx + len(value):]


def _replace_plain(raw: str, value: str, translation: str) -> str:
    """plain 行写回：保留行首 markdown/列表结构 marker，只替换 marker 后内容。

    OriginalGameCredits.txt / Changelog.txt 等纯文本清单实证：`*Programmers`
    被整行翻译成 `程序员` 丢掉星号、` *Fixed crash` 被译成
    `已修复...`（丢前导缩进）——写回破坏列表结构。marker（缩进 + */-
    /+/数字./#）是结构前缀必须原样保留，只有其后的文本是玩家可见内容。
    """
    # plain 行 original == raw（整行），marker 前缀必然在 raw 里；
    # 直接无条件保留 marker，无需与 value 比较（original 含 marker，
    # rest 是去 marker 后文本，比较永不相等会误落 _replace_tail 丢 marker）。
    md = _MD_HEADING.match(raw)
    if md:
        return md.group(1) + translation
    m = _MD_MARKER.match(raw)
    if m:
        indent, sym, num, space, _rest = m.groups()
        marker = indent + (sym or num) + space
        text = translation
        # 译文可能把单字符 marker 当强调回显（`*修复...*`）或前缀回显
        # （`*改进...`）——marker 已由行首保留，译文里重复的 marker 必须
        # 剥掉，否则写成 `**修复...` / `*  *改进...` 双 marker 破坏列表
        # 结构（Changelog 实证）。
        if sym:
            t = text.lstrip()
            if len(t) >= 2 and t.startswith(sym) and t.endswith(sym):
                text = t[1:-1]                       # `*修复...*` 剥前后
            elif t.startswith(sym):
                text = t[1:].lstrip()                # `*改进...` 剥前缀
        return marker + text
    return _replace_tail(raw, value, translation)
