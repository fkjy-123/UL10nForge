from __future__ import annotations
import re
from pathlib import Path
from hanhua.core.models import TextEntry, STATUS_SKIPPED
from hanhua.core.formats import read_text
from hanhua.core.placeholders import (is_hard_structural, is_vn_command_line,
                                       should_skip)

# key=value / key:value（delim 记录原样分隔符）
_KV = re.compile(r"^(?P<key>[^=:;\t\r\n]+?)\s*(?P<delim>[:=])\s*(?P<value>.*)$")
_TAB = re.compile(r"^(?P<key>[^\t\r\n]+)\t(?P<value>.*)$")


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
    """按行号重建。kv 行用 rfind 替换值部分，保留行内其它空白；跳过行原样输出。"""
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
                by_line[line_no] = _replace_tail(e.meta["raw"], e.original, e.translation)
            else:
                raw = e.meta["raw"]
                by_line[line_no] = _replace_tail(raw, e.original, e.translation)
        else:
            by_line[line_no] = e.meta["raw"]
    return "\n".join(by_line[i] for i in sorted(by_line))


def _replace_tail(raw: str, value: str, replacement: str) -> str:
    """把 raw 中最后一次出现的 value 替换为 replacement。"""
    idx = raw.rfind(value)
    if idx < 0:
        return raw
    return raw[:idx] + replacement + raw[idx + len(value):]
