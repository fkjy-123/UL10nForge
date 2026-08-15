"""分母普查：全量字节级文本清册（识别诊断通道，与提取管线完全解耦）。

动机（识别模块「看不见」问题的根治）：
提取器只读「认识的载体」（Unity 容器/DLL/metadata/文本文件），未知容器、
加密包、伪装扩展名里的文本整类不可见——识别率的分母因此不确定。本模块
提供一条**独立于载体知识的**字节扫描通道：遍历游戏目录每个文件，找可打印
文本 run（UTF-8 + UTF-16LE 双探测），产出 (文件, 偏移, 编码, 文本) 全量
清册。清册与提取池做差集 = 盲区清单（可排序、可归因、可关闭）。

设计约束：
- 只「看见」，不写回（写回仍由载体解析管线负责）；
- 已知二进制媒体（图像/音频/字体）按后缀/魔数排除——像素字节会过可打印
  启发式，纳入只会淹没报告（scan 历史：.rgb 位图误判为文本 3 游戏实证）；
- 代码二进制（.dll/.exe/.so）排除——其字符串全集由 #US 堆/证明链精确
  枚举（mono_dll.py），不需要字节级扫描兜底；
- 预算上限（每文件/每游戏 run 数 + 每文件字节数）防止 2GB TextAsset /
  il2cppOutput 类爆炸（backrooms 639 万条目实证），截断计数留档。

注意：GBK/Shift-JIS 等东亚编码的自定义容器文本本通道暂不覆盖（Unity
原生字符串是 UTF-8/UTF-16，覆盖游戏主路径；自定义编码容器留给注册表
新形态登记时接线）。
"""
from __future__ import annotations

from collections.abc import Iterator, Iterable
from dataclasses import dataclass
from pathlib import Path

from hanhua.core.scanner import (_is_runtime_file, _walk_files,
                                 TEXT_EXTENSIONS, probe_file_kind)

# 已由提取管线覆盖的容器种类（probe_file_kind 值）：Unity 容器由 asset
# 提取器读；zip/gzip/sqlite 由文本容器管线读。普查跳过——它的盲区价值
# 在「探测为 binary/unknown 或纯文本伪装」的文件。
_COVERED_KINDS = frozenset({
    "unity", "serialized", "webfile", "unitycn_encrypted",
    "zip", "sqlite", "gzip", "zstd", "lz4",
})

# 普查排除的后缀：已由提取管线精确覆盖的载体（它们不是盲区——普查的
# 独特价值是「没有提取器认领的文件」），加上纯噪音媒体。保留未知后缀
# 与伪装扩展名（.dat/.bin/.bytes/无后缀）——它们正是普查要覆盖的盲区。
_CENSUS_SKIP_SUFFIXES = frozenset({
    # 已覆盖：Unity 容器由 asset 提取器（typetree/raw scan）读；
    # 代码二进制由 #US/metadata 通道精确枚举（mono_dll/il2cpp）。
    # 注意 .pak 也在 ASSET_EXTENSIONS——UnityPy 解析失败的文件在提取器
    # 侧留档（skipped_reasons），普查不再重复扫。
    ".assets", ".ab", ".unity3d", ".bundle", ".pak",
    ".dll", ".exe", ".so", ".dylib", ".a", ".lib", ".pdb", ".mdb",
    ".ress", ".resource", ".resdata",
    # 已覆盖：松散文本格式由文本扫描管线读
    *TEXT_EXTENSIONS,
    # IL2CPP 生成源码（il2cppOutput 目录已剪，散落单文件再兜底）
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx", ".cs", ".java",
    # 图像/视频/音频/字体：像素与采样字节必过可打印启发式，纯噪音
    ".png", ".jpg", ".jpeg", ".gif", ".tga", ".bmp", ".psd", ".webp",
    ".ico", ".cur", ".dds", ".ktx", ".pvr", ".astc", ".hdr",
    ".rgb", ".iff", ".ilbm", ".sgi", ".exr", ".tif", ".tiff", ".pdf",
    ".wav", ".ogg", ".mp3", ".mp4", ".webm", ".avi", ".mov", ".wem",
    ".bank", ".bnk", ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # 已知引擎/工程数据（无文本语义）
    ".fbx", ".obj", ".blend", ".caw", ".ecm", ".sse", ".vis", ".pos",
    # Unity 编辑器元数据与版本控制副本（.png.meta / .meta~HEAD /
    # .meta~origin_*——GUID/导入设置，绝非显示文本。operation-ops
    # 53 文件、faerie-afterlight 7 文件假盲区实证）
    ".meta",
    # MSBuild 响应文件（编译参数，bird-builder/butterflies 实证假盲区）
    ".rsp",
    # 启动脚本（.bat 引用 exe 路径/窗口参数，electric-trains/outrun-clone
    # 实证假盲区——非游戏显示文本）
    ".bat", ".cmd",
})
# 普查跳过的文件/目录名（与 scanner.SKIP_FILES 同模式，普查专用）：
# Addressables 内容目录（catalog.bin=运行时键库按名引用、catalog.hash=
# 内容哈希——无显示文本，find_asset_files 已文档化；minato 274 条/
# cosl 284 条假盲区实证）；runner 工具作业残留目录（ivor_scan/soul_
# scan 实证：tooling/tool-jobs 内是 dumper 输入副本与日志，工具自身
# 工作区不是游戏内容）；Unity Profiler 连接配置。
_CENSUS_SKIP_FILES = frozenset({
    "catalog.bin", "catalog.hash",
    "playerconnectionconfigfile",
})
_CENSUS_SKIP_DIRS = frozenset({"tooling"})

_MIN_RUN_CHARS = 4        # run 最少字符数（低于此是随机噪声/单字节）
_MAX_RUNS_PER_FILE = 2000  # 每文件 run 上限（截断计数留档）
_MAX_RUNS_TOTAL = 200_000  # 每游戏 run 总上限
_MAX_FILE_BYTES = 256 * 1024 * 1024  # 每文件扫描字节上限
_CHUNK_BYTES = 4 * 1024 * 1024       # 分块扫描块大小
_MAX_CARRY_BYTES = 64 * 1024         # 未闭合 run 跨块 carry 上限

_ASCII_PRINTABLE = bytes(range(0x20, 0x7F))
_ASCII_ALLOWED = bytes((0x09, 0x0A, 0x0D))


@dataclass(frozen=True)
class CensusHit:
    rel_path: str   # game_dir 相对路径（/ 分隔）
    offset: int     # 文件内字节偏移
    encoding: str   # "utf-8" | "utf-16le"
    text: str


@dataclass
class CensusResult:
    hits: list[CensusHit]
    files_scanned: int = 0
    files_skipped: dict[str, int] = None  # 排除原因计数（哑信号可见化）
    runs_truncated_file: int = 0          # 每文件上限截断的 run 数
    runs_truncated_total: int = 0         # 全游戏上限截断的 run 数
    bytes_scanned: int = 0

    def __post_init__(self):
        if self.files_skipped is None:
            self.files_skipped = {}


def _is_utf8_continuation(b: int) -> bool:
    return 0x80 <= b <= 0xBF


def _utf8_seq_len(lead: int) -> int:
    if 0xC2 <= lead <= 0xDF:
        return 2
    if 0xE0 <= lead <= 0xEF:
        return 3
    if 0xF0 <= lead <= 0xF4:
        return 4
    return 0


def _is_printable_char(ch: str) -> bool:
    return ch in "\n\r\t" or (ch >= " " and ch.isprintable())


_STRIP_CHARS = " \t\r\n"


def _emit_run(data: bytes, base_offset: int, run_start: int, raw_end: int,
              encoding: str, *, require_ascii_letter: bool = False) -> CensusHit | None:
    """run 收尾：裁剪首尾空白，偏移指向裁剪后起点；不合格返回 None。

    裁剪是差集正确性的要求：提取池原文通常已 strip（TextAsset 行、
    raw scan 精确串），普查命中带首尾空白会与池匹配失败产生假缺口。
    require_ascii_letter（UTF-16LE 用）：随机二进制字节对解码为可打印
    Unicode（尤其 CJK）概率过半，必须含 ≥1 个 ASCII 字母才算命中——
    真实 UTF-16 拉丁文本 = (ASCII, 0x00) 交替对，随机撞出该形态概率
    ~0.15%；纯二进制乱码 CJK run 被整类排除。
    """
    try:
        text = data[run_start:raw_end].decode(encoding)
    except UnicodeDecodeError:
        return None
    stripped = text.strip(_STRIP_CHARS)
    if not stripped or len(stripped) < _MIN_RUN_CHARS:
        return None
    if require_ascii_letter:
        if not any(ch.isascii() and ch.isalpha() for ch in stripped):
            return None
    elif not any(ch.isalpha() for ch in stripped):
        return None
    lead = len(text) - len(text.lstrip(_STRIP_CHARS))
    offset = base_offset + run_start
    if lead:
        offset += len(text[:lead].encode(encoding, errors="replace"))
    return CensusHit("", offset, encoding, stripped)


def _scan_utf8_runs(data: bytes, base_offset: int, *,
                    final: bool = True) -> tuple[list[CensusHit], int | None]:
    """ASCII + 合法 UTF-8 多字节序列的连续可打印 run。

    返回 (hits, open_start)。final=True（默认，单元测试/文件尾）：数据
    末尾的未闭合 run 直接产出命中；final=False（分块扫描中间块）：未
    闭合 run 不产出、open_start 返回其起点——调用方整体 carry 到下一块
    重扫，保证跨块 run 只产出一次完整命中。无未闭合 run 时 open_start
    为 None。
    """
    hits: list[CensusHit] = []
    i = 0
    n = len(data)
    run_start = -1
    while i < n:
        b = data[i]
        if b in _ASCII_PRINTABLE or b in _ASCII_ALLOWED:
            if run_start < 0:
                run_start = i
            i += 1
            continue
        if b >= 0x80:
            seq = _utf8_seq_len(b)
            if seq and i + seq <= n and all(
                    _is_utf8_continuation(data[j])
                    for j in range(i + 1, i + seq)):
                try:
                    ch = data[i:i + seq].decode("utf-8")
                except UnicodeDecodeError:
                    ch = ""
                if ch and _is_printable_char(ch):
                    if run_start < 0:
                        run_start = i
                    i += seq
                    continue
            # 数据末尾的不完整多字节序列：序列在块边界被截断——run 保持
            # 打开（open_start 回传），整体 carry 到下一块补全。若在此
            # 断裂，第一块产出前缀命中、下一块重新起跑 → run 被拆碎。
            if (seq and i + seq > n
                    and all(_is_utf8_continuation(data[j])
                            for j in range(i + 1, n))):
                return hits, (run_start if run_start >= 0 else i)
        # run 断裂
        if run_start >= 0:
            hit = _emit_run(data, base_offset, run_start, i, "utf-8")
            if hit is not None:
                hits.append(hit)
            run_start = -1
        i += 1
    if run_start >= 0:
        if final:
            hit = _emit_run(data, base_offset, run_start, n, "utf-8")
            if hit is not None:
                hits.append(hit)
        return hits, run_start
    return hits, None


def _scan_utf16le_runs(data: bytes, base_offset: int, *,
                       final: bool = True) -> tuple[list[CensusHit], int | None]:
    """UTF-16LE 连续可打印 run（逐 2 字节解码，含代理对）。

    返回 (hits, open_start)：与 _scan_utf8_runs 同语义（final/跨块 carry）。
    假阳性防线（require_ascii_letter + 拉丁占比）：随机二进制字节对
    解码为可打印 Unicode（尤其 CJK）概率过半，且乱码 run 中零星夹着
    合法的 (ASCII, 0x00) 对（crash-back-in-time 自定义容器实证：'扏彪
    杅灹$H᐀' 类乱码混有 H/0x00）。真实 UTF-16 拉丁文本的码元几乎
    全部是「低字节 0x00 的可打印拉丁」形态——要求该占比 ≥50% 且含
    ≥1 个 ASCII 字母。纯 CJK UTF-16 文本（无拉丁字母）暂不覆盖
    （Unity 原生字符串为 UTF-8，此形态罕见）。
    """
    hits: list[CensusHit] = []
    i = 0
    n = len(data)
    run_start = -1
    units = 0
    latin_units = 0
    while i + 1 < n:
        unit = data[i] | (data[i + 1] << 8)
        if 0xD800 <= unit <= 0xDBFF and i + 3 < n:  # 高代理
            low = data[i + 2] | (data[i + 3] << 8)
            if 0xDC00 <= low <= 0xDFFF:
                try:
                    ch = data[i:i + 4].decode("utf-16-le")
                except UnicodeDecodeError:
                    ch = ""
                if ch and _is_printable_char(ch):
                    if run_start < 0:
                        run_start = i
                    units += 1
                    i += 4
                    continue
        elif 0xD800 <= unit <= 0xDBFF and i + 3 >= n:
            # 数据末尾的不完整代理对：与 UTF-8 同语义——run 保持打开
            # carry 到下一块补全（防跨块 run 被拆碎）
            return hits, (run_start if run_start >= 0 else i)
        else:
            try:
                ch = data[i:i + 2].decode("utf-16-le")
            except UnicodeDecodeError:
                ch = ""
            if ch and _is_printable_char(ch):
                if run_start < 0:
                    run_start = i
                units += 1
                if 0x20 <= unit <= 0x7E:
                    latin_units += 1
                i += 2
                continue
        if run_start >= 0:
            if (units >= _MIN_RUN_CHARS
                    and latin_units * 2 >= units):
                hit = _emit_run(data, base_offset, run_start, i, "utf-16-le",
                                require_ascii_letter=True)
                if hit is not None:
                    hits.append(hit)
            run_start = -1
            units = latin_units = 0
        i += 2
    if run_start >= 0:
        if final and units >= _MIN_RUN_CHARS and latin_units * 2 >= units:
            hit = _emit_run(data, base_offset, run_start, n - (n % 2),
                            "utf-16-le", require_ascii_letter=True)
            if hit is not None:
                hits.append(hit)
        return hits, run_start
    return hits, None


def _should_skip_file(p: Path) -> str | None:
    """返回排除原因；None = 纳入普查。

    排除顺序：后缀 → 文件名 → 内容探测。内容探测排除已由提取管线覆盖
    的容器（Unity 容器/zip/sqlite/gzip 等）——无后缀 level 场景、伪装
    扩展名的 SerializedFile 在此被正确识别并跳过（由 asset 提取器负责）。
    """
    if p.suffix.lower() in _CENSUS_SKIP_SUFFIXES:
        return f"suffix:{p.suffix.lower()}"
    name_low = p.name.casefold()
    # .meta 的版本控制副本变体（.meta~HEAD / .meta~origin_*——suffix
    # 会读到 .meta~HEAD 整段）
    if ".meta~" in name_low:
        return "suffix:.meta"
    if name_low in _CENSUS_SKIP_FILES:
        return f"file:{name_low}"
    try:
        kind = probe_file_kind(p)
    except OSError:
        return "probe_failed"
    if kind in _COVERED_KINDS:
        return f"covered:{kind}"
    return None


def sweep_game(
        game_dir: str | Path, *,
        exclude_roots: Iterable[str | Path] = ()) -> CensusResult:
    """全量字节普查：遍历游戏目录所有非运行时文件，扫文本 run。

    只读通道：不修改任何输入文件；hits 顺序为 (文件序, 偏移序)。
    """
    root = Path(game_dir)
    result = CensusResult(hits=[])
    for p in _walk_files(root, exclude_roots=exclude_roots):
        if _is_runtime_file(p, root):
            result.files_skipped["runtime_file"] = \
                result.files_skipped.get("runtime_file", 0) + 1
            continue
        rel_parts = p.relative_to(root).parts[:-1]
        if any(part.casefold() in _CENSUS_SKIP_DIRS
               for part in rel_parts):
            result.files_skipped["tooling_dir"] = \
                result.files_skipped.get("tooling_dir", 0) + 1
            continue
        skip = _should_skip_file(p)
        if skip is not None:
            result.files_skipped[skip] = \
                result.files_skipped.get(skip, 0) + 1
            continue
        try:
            size = p.stat().st_size
        except OSError:
            result.files_skipped["stat_failed"] = \
                result.files_skipped.get("stat_failed", 0) + 1
            continue
        if size > _MAX_FILE_BYTES:
            result.files_skipped["too_large"] = \
                result.files_skipped.get("too_large", 0) + 1
            continue
        if size == 0:
            result.files_skipped["empty"] = \
                result.files_skipped.get("empty", 0) + 1
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        file_hits: list[CensusHit] = []
        try:
            with p.open("rb") as stream:
                scanned = 0
                # 双通道独立 carry：UTF-8 与 UTF-16LE 的对齐/run 语义不同，
                # 共享 carry 会互相破坏（另一通道的开放 run 劫持 carry 起
                # 点，把本通道跨块 run 切碎）。
                carry8 = carry16 = b""
                off8 = off16 = 0
                while True:
                    chunk = stream.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    scanned += len(chunk)
                    data8 = carry8 + chunk
                    data16 = carry16 + chunk
                    hits8, open8 = _scan_utf8_runs(data8, off8, final=False)
                    hits16, open16 = _scan_utf16le_runs(data16, off16,
                                                        final=False)
                    file_hits.extend(hits8)
                    file_hits.extend(hits16)
                    # 未闭合 run 整体 carry 到下一块重扫（跨块 run 只产出
                    # 一次完整命中）；无未闭合 run 时保留保护尾（UTF-8 3
                    # 字节=最长序列 4 字节；UTF-16 2 字节=1 码元）。carry
                    # 超上限的病态长 run 按当前片段直接产出，退回保护尾。
                    # 注意：不能用对象同一性区分通道——bytes 拼接 b''+x
                    # 恒等返回 x，两个空 carry 时 data8 与 data16 是同一
                    # 对象，identity 判断会串通道。
                    for channel, open_start, data, keep in (
                            (8, open8, data8, 3), (16, open16, data16, 2)):
                        if (open_start is not None
                                and len(data) - open_start <= _MAX_CARRY_BYTES):
                            carry = data[open_start:]
                            base = open_start
                        else:
                            carry = data[-min(keep, len(data)):]
                            base = len(data) - min(keep, len(data))
                        if channel == 8:
                            carry8, off8 = carry, off8 + base
                        else:
                            carry16, off16 = carry, off16 + base
                    if len(file_hits) >= _MAX_RUNS_PER_FILE * 4:
                        break  # 超预算文件不再扫（清册有界）
            # 文件尾 carry 是终态：未闭合 run 在此产出完整命中
            if carry8:
                for hit in _scan_utf8_runs(carry8, off8, final=True)[0]:
                    file_hits.append(hit)
            if carry16:
                for hit in _scan_utf16le_runs(carry16, off16, final=True)[0]:
                    file_hits.append(hit)
        except OSError:
            result.files_skipped["read_failed"] = \
                result.files_skipped.get("read_failed", 0) + 1
            continue
        result.files_scanned += 1
        result.bytes_scanned += scanned
        # 去重（UTF-8 与 UTF-16LE 通道可能在同一区域重叠命中的极端情况）
        seen: set[tuple[int, str]] = set()
        deduped: list[CensusHit] = []
        for hit in sorted(file_hits, key=lambda h: (h.offset, h.encoding)):
            key = (hit.offset, hit.text)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(hit)
        if len(deduped) > _MAX_RUNS_PER_FILE:
            result.runs_truncated_file += len(deduped) - _MAX_RUNS_PER_FILE
            deduped = deduped[:_MAX_RUNS_PER_FILE]
        remaining = _MAX_RUNS_TOTAL - len(result.hits)
        if remaining <= 0:
            result.runs_truncated_total += len(deduped)
            continue
        if len(deduped) > remaining:
            result.runs_truncated_total += len(deduped) - remaining
            deduped = deduped[:remaining]
        for hit in deduped:
            result.hits.append(CensusHit(rel, hit.offset, hit.encoding, hit.text))
    return result


def iter_hits(result: CensusResult) -> Iterator[CensusHit]:
    yield from result.hits
