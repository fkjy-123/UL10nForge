"""v2 Mono 程序集提取：dnfile 读取 .NET #US 字符串堆（C# 字符串字面量）。"""
from __future__ import annotations
from pathlib import Path
import re
from typing import Callable

from hanhua.core.extractor import ParsedFile, looks_like_noise_file
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.paths import (UnsafeRelativePathError, ensure_trusted_root,
                               resolve_relative_under)
from hanhua.core.placeholders import is_code_identifier, is_hard_structural
from hanhua.core.engine_strings import (is_engine_string as _is_engine_string,
                                        is_strong_interaction_prompt)
from hanhua.core.tooling.player_layout import (
    PlayerLayoutError,
    discover_application_assemblies,
)

# 代码拼接 UI 文本证据：4+ 字符全大写词（BEST/LEFT/DRIFT），诊断日志通常无
_UI_UPPERCASE_WORD = re.compile(r"(?<![A-Za-z0-9_])[A-Z]{4,}(?![A-Za-z0-9_])")


def _safe_resolve_discovery_path(game_root: Path, candidate: Path) -> Path | None:
    """Resolve a discovered path after rejecting any reparse point in its chain."""
    try:
        relative = candidate.absolute().relative_to(game_root)
        return resolve_relative_under(game_root, relative)
    except (OSError, ValueError):
        return None


def find_dll_files(game_dir: str | Path) -> list[Path]:
    """Discover application assemblies using the shared player-layout rules."""
    try:
        game_dir = ensure_trusted_root(game_dir)
    except UnsafeRelativePathError:
        return []
    found: dict[str, Path] = {}
    pending = [game_dir]
    while pending:
        current = pending.pop()
        try:
            assemblies = discover_application_assemblies(game_dir, current)
        except PlayerLayoutError:
            return []
        for assembly in assemblies:
            found[str(assembly).casefold()] = assembly
        try:
            children = sorted(current.iterdir(), key=lambda path: (
                path.name.casefold(), path.name))
        except OSError:
            continue
        for child in reversed(children):
            candidate = _safe_resolve_discovery_path(game_dir, child)
            if candidate is not None and candidate.is_dir():
                pending.append(candidate)
    return sorted(found.values(), key=lambda path: (
        path.relative_to(game_dir).as_posix().casefold(),
        path.relative_to(game_dir).as_posix(),
    ))


def _walk_us_heap(data: bytes) -> list[tuple[int, bytes]]:
    """遍历 #US 堆 → [(字节偏移, 原始 UTF-16 字节)]。偏移 0 为占位。"""
    return [(data_offset, raw)
            for _, data_offset, raw in _walk_us_heap_records(data)]


def read_us_record_at(data: bytes, offset: int) -> tuple[int, bytes] | None:
    """按 token 偏移定位读取单条 #US 记录（与 CLR 语义一致，自包含）。

    记录 = 压缩长度前缀 + UTF-16 数据 + 1 字节尾部标志；读取不依赖前后
    记录（#US 堆无需紧凑，写回后残留字节不影响）。返回 (数据区位置,
    含尾部 flag 的原始字节)；偏移非法/记录越界返回 None。
    """
    if offset < 0 or offset >= len(data):
        return None
    compressed = _read_compressed_uint(data, offset)
    if compressed is None:
        return None
    ln, prefix_size = compressed
    data_start = offset + prefix_size
    if ln <= 0 or data_start + ln > len(data):
        return None
    return data_start, bytes(data[data_start:data_start + ln])


def _read_compressed_uint(data: bytes, offset: int) -> tuple[int, int] | None:
    """Read an ECMA-335 compressed unsigned integer as (value, byte count)."""
    if offset >= len(data):
        return None
    first = data[offset]
    if first & 0x80 == 0:
        return first, 1
    if first & 0xC0 == 0x80:
        if offset + 1 >= len(data):
            return None
        value = ((first & 0x3F) << 8) | data[offset + 1]
        return (value, 2) if value >= 0x80 else None
    if first & 0xE0 == 0xC0:
        if offset + 3 >= len(data):
            return None
        value = ((first & 0x1F) << 24) | (data[offset + 1] << 16)
        value |= (data[offset + 2] << 8) | data[offset + 3]
        return (value, 4) if value >= 0x4000 else None
    return None


def _walk_us_heap_records(data: bytes) -> list[tuple[int, int, bytes]]:
    """Return (token offset, data offset, raw bytes) for each #US record.

    流式遍历假设堆紧凑（编译器产物成立）。写回后记录变短会在尾部残留
    旧字节，残留区会被误解析为非法记录——此时步进 1 继续（鲁棒模式），
    不丢弃残留区之后的真实记录；原始紧凑堆行为不变。垃圾短记录会被
    提取侧字符串级过滤淘汰，写回侧只按 offset 单记录定位，不受影响。
    """
    out: list[tuple[int, int, bytes]] = []
    i = 1
    while i < len(data):
        token_offset = i
        compressed = _read_compressed_uint(data, i)
        if compressed is None:
            i += 1
            continue
        ln, prefix_size = compressed
        if ln <= 0 or i + prefix_size + ln > len(data):
            i += 1
            continue
        i += prefix_size
        out.append((token_offset, i, bytes(data[i:i + ln])))
        i += ln
    return out


_UI_SETTER_TYPES = frozenset({
    "TMPro.TMP_Text", "TMPro.TextMeshPro", "TMPro.TextMeshProUGUI",
    "TMPro.TMP_InputField", "UnityEngine.UI.Text", "UnityEngine.UI.InputField",
    "UnityEngine.TextMesh", "UnityEngine.UIElements.TextElement",
    "UnityEngine.UIElements.Label", "UnityEngine.UIElements.TextField",
})
_IL_OPERAND_1 = frozenset({
    *range(0x0E, 0x14), 0x1F, *range(0x2B, 0x38), 0xDE,
})
_IL_OPERAND_4 = frozenset({
    0x20, 0x22, 0x27, 0x28, 0x29, *range(0x38, 0x45),
    0x6F, *range(0x70, 0x76), 0x79, *range(0x7B, 0x82),
    0x8C, 0x8D, 0x8F, 0xA3, 0xA4, 0xA5, 0xC2, 0xC6, 0xD0, 0xDD,
})
_IL_OPERAND_8 = frozenset({0x21, 0x23})
_IL_NO_OPERAND = frozenset({
    *range(0x00, 0x0E), *range(0x14, 0x1F), 0x25, 0x26, 0x2A,
    *range(0x46, 0x6F), 0x76, 0x7A, *range(0x82, 0x8C), 0x8E,
    *range(0x90, 0xA3), *range(0xB3, 0xBB), 0xC3,
    *range(0xD1, 0xDD), 0xDF, 0xE0,
})
_IL_FE_OPERANDS = {
    0x06: 4, 0x07: 4, 0x09: 2, 0x0A: 2, 0x0B: 2, 0x0C: 2,
    0x0D: 2, 0x0E: 2, 0x12: 1, 0x15: 4, 0x16: 4, 0x19: 1, 0x1C: 4,
}
_IL_FE_NO_OPERAND = frozenset({
    *range(0x00, 0x06), 0x0F, 0x11, 0x13, 0x14, 0x17, 0x18,
    0x1A, 0x1D, 0x1E,
})
_IL_CONTROL_FLOW_BOUNDARIES = frozenset({
    0x2A, *range(0x2B, 0x46), 0x7A, 0xDC, 0xDD, 0xDE,
})


def _simple_string_format_parameter_count(row) -> int | None:
    """Return arity only for String.Format overloads whose first arg is string."""
    signature = getattr(getattr(row, "Signature", None), "value", None)
    if not isinstance(signature, bytes) or len(signature) < 4:
        return None
    index = 1
    if signature[0] & 0x10:  # GENERIC: generic arity precedes parameter count.
        generic = _read_compressed_uint(signature, index)
        if generic is None:
            return None
        _, size = generic
        index += size
    parameter = _read_compressed_uint(signature, index)
    if parameter is None:
        return None
    parameter_count, size = parameter
    index += size
    # Supported String.Format overloads return string and take the format
    # string as their first parameter. Provider-first overloads are rejected.
    if (parameter_count <= 0 or index + 1 >= len(signature)
            or signature[index] != 0x0E
            or signature[index + 1] != 0x0E):
        return None
    return parameter_count


def _method_il(pe, rva: int) -> bytes | None:
    try:
        header = pe.get_data(rva, 12)
    except Exception:  # noqa: BLE001
        return None
    if not header:
        return None
    if header[0] & 3 == 2:
        header_size, code_size = 1, header[0] >> 2
    elif header[0] & 3 == 3 and len(header) >= 12:
        header_size = ((int.from_bytes(header[:2], "little") >> 12) & 0xF) * 4
        code_size = int.from_bytes(header[4:8], "little")
        if header_size < 12:
            return None
    else:
        return None
    try:
        body = pe.get_data(rva, header_size + code_size)
    except Exception:  # noqa: BLE001
        return None
    if len(body) < header_size + code_size:
        return None
    return body[header_size:header_size + code_size]


def _decode_il(code: bytes) -> list[tuple[int, int | None]] | None:
    instructions: list[tuple[int, int | None]] = []
    offset = 0
    while offset < len(code):
        opcode = code[offset]
        offset += 1
        operand_size = 0
        if opcode == 0xFE:
            if offset >= len(code):
                return None
            second = code[offset]
            offset += 1
            if second in _IL_FE_OPERANDS:
                operand_size = _IL_FE_OPERANDS[second]
            elif second not in _IL_FE_NO_OPERAND:
                return None
            opcode = 0xFE00 | second
        elif opcode == 0x45:
            if offset + 4 > len(code):
                return None
            count = int.from_bytes(code[offset:offset + 4], "little")
            operand_size = 4 + count * 4
        elif opcode in _IL_OPERAND_1:
            operand_size = 1
        elif opcode in _IL_OPERAND_4:
            operand_size = 4
        elif opcode in _IL_OPERAND_8:
            operand_size = 8
        elif opcode not in _IL_NO_OPERAND:
            return None
        if offset + operand_size > len(code):
            return None
        operand = (int.from_bytes(code[offset:offset + operand_size], "little")
                   if operand_size in (1, 2, 4, 8) else None)
        instructions.append((opcode, operand))
        offset += operand_size
    return instructions


_SIMPLE_ELEMENT_TYPES = frozenset({
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A,
    0x0B, 0x0C, 0x0D, 0x0E, 0x13, 0x16, 0x18, 0x19, 0x1B,
})
_FORMATTED_UI_MAX_INSTRUCTIONS = 24
_IL_FORMAT_VALUE_LOADS = frozenset({
    *range(0x02, 0x0A), 0x0E, 0x0F, 0x11, 0x12,
    *range(0x14, 0x20), 0x7E, 0x7F,
})


def _skip_compressed_uint(data: bytes, offset: int) -> int | None:
    """Skip one ECMA-335 compressed unsigned integer, returning the new offset."""
    encoded = _read_compressed_uint(data, offset)
    return offset + encoded[1] if encoded is not None else None


def _method_signature_string_params(sig: bytes) -> list[bool] | None:
    """解析方法签名 → 每个参数是否为 string（不含 receiver）；无法解析返回 None。

    仅识别常用 ELEMENT_TYPE；ARRAY/FNPTR/GENERICINST 等复杂编码保守返回 None，
    使该 helper 不参与传递验证（不会误放行，只是少验证一类）。
    """

    def skip_type(i: int) -> int | None:
        if i >= len(sig):
            return None
        element = sig[i]
        if element in _SIMPLE_ELEMENT_TYPES:
            return i + 1
        if element in (0x0F, 0x10, 0x1C):  # PTR / BYREF / SZARRAY：后跟一个类型
            return skip_type(i + 1)
        if element in (0x11, 0x12):  # VALUETYPE / CLASS：后跟 typeDefOrRef token
            return _skip_compressed_uint(sig, i + 1)
        if element in (0x1E, 0x1F):  # CMOD_REQD / CMOD_OPT：token + 类型
            after = _skip_compressed_uint(sig, i + 1)
            return skip_type(after) if after is not None else None
        return None

    if not sig or sig[0] in (0x00, 0xFF):
        return None
    index = 1
    if sig[0] & 0x10:  # GENERIC：泛型数在参数数之前
        generic = _read_compressed_uint(sig, index)
        if generic is None:
            return None
        _, size = generic
        index += size
    count = _read_compressed_uint(sig, index)
    if count is None:
        return None
    param_count, size = count
    index += size
    return_type = skip_type(index)
    if return_type is None:
        return None
    index = return_type
    out: list[bool] = []
    for _ in range(param_count):
        if index >= len(sig):
            return None
        if sig[index] == 0x41:  # SENTINEL：vararg 分隔，其后仍可能是参数
            index += 1
            if index >= len(sig):
                return None
        out.append(sig[index] == 0x0E)
        next_type = skip_type(index)
        if next_type is None:
            return None
        index = next_type
    return out


def _verified_ui_user_string_tokens(pe) -> set[int]:
    """Return #US token offsets proven to flow into verified UI setter calls.

    游戏常用自封装方法（SetTutorialText(text) 内部再 set_text），字面量先传给
    包装方法而非直接喂 setter——因此做传递式验证（cell-machine 真实样本）：
    1) 方法参数流入 UI setter / 已标记的包装方法 → 该参数标记为 UI 字符串参数；
    2) 任意方法内 ldstr 位于目标方法的 string 参数位 → token 验证通过；
    3) 逐轮传播直到不动点（包装链可多层）。
    未知调用 / 分支 / 未建模指令一律清空栈——Debug.Log、String.Concat 等
    非 UI 消费路径不会被误放行。
    """
    try:
        member_rows = pe.net.mdtables.MemberRef.rows
        method_rows = pe.net.mdtables.MethodDef.rows
    except AttributeError:
        return set()
    ui_setters: set[int] = set()
    string_formatters: dict[int, int] = {}
    safe_value_producers: set[int] = set()
    for index, row in enumerate(member_rows, 1):
        declaring = getattr(getattr(row, "Class", None), "row", None)
        full_type = ".".join(filter(None, (
            str(getattr(declaring, "TypeNamespace", "") or ""),
            str(getattr(declaring, "TypeName", "") or ""),
        )))
        method_name = str(getattr(row, "Name", "") or "")
        if full_type in _UI_SETTER_TYPES and method_name in {"set_text", "SetText"}:
            ui_setters.add(0x0A000000 | index)
        elif full_type == "System.String" and method_name == "Format":
            parameter_count = _simple_string_format_parameter_count(row)
            if parameter_count is not None:
                string_formatters[0x0A000000 | index] = parameter_count
        elif method_name.startswith("get_") and full_type != "System.String":
            safe_value_producers.add(0x0A000000 | index)
    for index, row in enumerate(method_rows, 1):
        if str(getattr(row, "Name", "") or "").startswith("get_"):
            safe_value_producers.add(0x06000000 | index)
    if not ui_setters:
        return set()

    # 每个方法签名的 string 参数位置（None = 无法解析，不参与传递验证）
    string_params: dict[int, list[bool] | None] = {}
    for index, row in enumerate(method_rows, 1):
        sig = getattr(getattr(row, "Signature", None), "value", None)
        string_params[0x06000000 | index] = (
            _method_signature_string_params(sig)
            if isinstance(sig, bytes) else None)

    # 方法 token → 已证明流入 UI 文本的参数索引
    ui_string_params: dict[int, set[int]] = {}
    verified: set[int] = set()
    for _round in range(16):  # 包装链深度上限（真实游戏通常 1-2 层）
        grew = False
        for index, row in enumerate(method_rows, 1):
            method_token = 0x06000000 | index
            rva = int(getattr(row, "Rva", 0) or 0)
            code = _method_il(pe, rva) if rva else None
            instructions = _decode_il(code) if code is not None else None
            if instructions is None:
                continue
            # 栈元素：("src", us_token) / ("arg", param_idx) / "other"
            stack: list[tuple[str, int] | str] = []
            gained: set[int] = set()
            for opcode, operand in instructions:
                if opcode == 0x72:  # ldstr
                    stack.append(("src", operand & 0x00FFFFFF))
                elif opcode in (0x02, 0x03, 0x04, 0x05):  # ldarg.0-3
                    stack.append(("arg", opcode - 0x02))
                elif opcode == 0x0E:  # ldarg.s
                    stack.append(("arg", operand))
                elif opcode in (0x06, 0x07, 0x08, 0x09, 0x11, 0x14,
                                *range(0x15, 0x20), 0x20, 0x21, 0x22,
                                0x23, 0x8E):
                    # ldloc.* / ldnull / ldc.i4.* / ldc.* / ldlen → 普通值
                    stack.append("other")
                elif opcode == 0x25:  # dup
                    if stack:
                        stack.append(stack[-1])
                elif opcode in (0x0A, 0x0B, 0x0C, 0x0D, 0x10, 0x13,
                                0x26, 0x30):
                    # stloc.* / starg.s / pop / starg → 消费栈顶
                    if stack:
                        stack.pop()
                elif opcode in (0x7D, 0x80):
                    # stfld / stind.* → 消费接收者+值，清空最稳
                    stack.clear()
                elif opcode in (0x0F, 0x12):
                    # ldarga.s / ldloca.s → 引用地址，普通值
                    stack.append("other")
                elif opcode in (0x7B, 0x7C, 0x7E, 0x74, 0x75, 0x8C, 0x79,
                                0xA2):
                    # ldfld / ldflda / castclass / isinst / box / unbox.*
                    # → 消费接收者，产出普通值
                    if stack:
                        stack.pop()
                    stack.append("other")
                elif opcode in (0x28, 0x6F):  # call / callvirt
                    if operand in ui_setters:
                        if stack:
                            top = stack[-1]
                            if isinstance(top, tuple) and top[0] in ("src", "fmt"):
                                verified.add(top[1])
                            elif isinstance(top, tuple) and top[0] == "arg":
                                gained.add(top[1])
                        stack.clear()
                    elif operand in string_formatters:
                        # 格式串来源暂存为 ("fmt", token)：只有真正流入
                        # setter / helper 才验证——格式化结果被丢弃（pop）时
                        # 该格式串不是显示文本（回归保护）。
                        arity = string_formatters[operand]
                        if len(stack) >= arity:
                            source = stack[-arity]
                            del stack[-arity:]
                            if isinstance(source, tuple) and source[0] in ("src", "fmt"):
                                stack.append(("fmt", source[1]))
                            else:
                                stack.append("other")
                        else:
                            stack.clear()
                            stack.append("other")
                    elif ui_string_params.get(operand):
                        params = string_params.get(operand)
                        if params is not None:
                            for k, is_string in enumerate(params):
                                if not is_string:
                                    continue
                                position = len(stack) - (len(params) - k)
                                if position < 0:
                                    continue
                                element = stack[position]
                                if isinstance(element, tuple):
                                    if element[0] in ("src", "fmt"):
                                        verified.add(element[1])
                                    elif element[0] == "arg":
                                        gained.add(element[1])
                        stack.clear()
                    elif operand in safe_value_producers:  # getter
                        if stack:
                            stack.pop()
                        stack.append("other")
                    else:
                        stack.clear()
                elif opcode in _IL_CONTROL_FLOW_BOUNDARIES:
                    stack.clear()
                else:
                    # 未建模指令可能消费/产出任意栈值 → 清空（保守）
                    stack.clear()
            if gained:
                existing = ui_string_params.get(method_token)
                if existing is None:
                    ui_string_params[method_token] = set(gained)
                    grew = True
                elif not gained <= existing:
                    existing |= gained
                    grew = True
        if not grew:
            break
    return verified


def extract_dll_user_strings(path: str | Path, file_id: str | None = None,
                             progress_cb: Callable | None = None) -> ParsedFile:
    """提取 DLL #US 字符串 → ParsedFile。"""
    import dnfile
    p = Path(path)
    fid = file_id or str(p).replace("\\", "/")
    pe = dnfile.dnPE(str(p))
    try:
        us = pe.net.user_strings
        if us is None:
            return ParsedFile(
                fid, str(p), "v2_mono", [], "utf-8", "\n", {"kind": "mono"}, True)
        data = us.get_data_at_offset(0, us.sizeof())
        heap_file_offset = us.get_file_offset(0)
        entries: list[TextEntry] = []
        verified_ui_tokens = _verified_ui_user_string_tokens(pe)
        for token_offset, offset, raw in _walk_us_heap_records(data):
            # ECMA-335 #US blobs always end with a one-byte kind flag.  The
            # flag is zero for ordinary ASCII strings and one for strings that
            # need the special-character marker; it is not UTF-16 payload.
            if raw:
                raw = raw[:-1]
            try:
                s = raw.decode("utf-16-le")
            except UnicodeDecodeError:
                continue
            # 无 provenance 的 Bold/WASD/Move 等标识符按枚举名/绑定名保守排除。
            is_ui_text = token_offset in verified_ui_tokens
            interaction_prompt = is_strong_interaction_prompt(s)
            # 代码拼接的 UI 文本证据：含空格 + 全大写强调词（UI 标签/教程句）。
            # driftapocalypse 真实样本：'BEST SCORE: '、'Hold LEFT or RIGHT to
            # turn\n('、'SHOW ANUNCIO'——字符串拼接未进 ui setter 验证链。
            # 诊断/日志字符串通常无全大写词，保持保守跳过。
            uppercase_ui = (
                " " in s and bool(_UI_UPPERCASE_WORD.search(s)))
            if is_hard_structural(s):
                continue
            if (not is_ui_text and not interaction_prompt and not uppercase_ui
                    and (is_code_identifier(s) or _is_engine_string(s))):
                continue
            display_text = is_ui_text or interaction_prompt or uppercase_ui
            entries.append(TextEntry(
                file_id=fid, key_path=f"us#{offset}",
                original=s, status="pending" if display_text else STATUS_SKIPPED,
                meta={
                    "kind": "us",
                    # 记录起始 = 压缩前缀位置（写回端定位用，与 CLR token 语义一致）
                    "record_offset": heap_file_offset + token_offset,
                    # 数据区位置（前缀之后；旧字段，写回端仅向后兼容旧项目库）
                    "heap_offset": heap_file_offset + offset,
                    "flag_offset": heap_file_offset + offset + len(raw),
                    "utf16_len": len(raw),
                    "confidence": (
                        "high" if is_ui_text or interaction_prompt
                        else "medium" if uppercase_ui
                        else "low"),
                    "role": "display" if display_text else "structural",
                    "disposition": "translate" if display_text else "structural",
                    "reason": (
                        "mono_ui_setter" if is_ui_text
                        else "interaction_prompt" if interaction_prompt
                        else "user_string_uppercase_ui" if uppercase_ui
                        else "unverified_user_string"),
                }))
        for e in entries:
            if e.status == "pending" and is_hard_structural(e.original):
                e.status = STATUS_SKIPPED
        noise = looks_like_noise_file(entries)
        return ParsedFile(
            fid, str(p), "v2_mono", entries, "utf-8", "\n", {"kind": "mono"}, noise)
    finally:
        pe.close()
