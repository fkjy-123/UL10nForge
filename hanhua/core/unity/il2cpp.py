"""v2 IL2CPP 提取：global-metadata.dat 字符串字面量池（写回标记为实验性，长度受限）。"""
from __future__ import annotations
import re
import struct
from pathlib import Path
from typing import Callable

from hanhua.core.extractor import ParsedFile, looks_like_noise_file
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.unity.extractor import (
    _finalize_skipped_counts, _skipped_sample_entry)
from hanhua.core.placeholders import is_code_identifier, should_skip
from hanhua.core.engine_strings import (
    is_engine_string as _is_engine_string,
    is_strong_interaction_prompt,
)

METADATA_MAGIC = 0xFAB11BAF
_MIN_METADATA_HEADER_SIZE = 0x30
# 只列入已用真实 metadata 验证过的布局；未知版本直接拒绝，不猜 record 尺寸。
# 验证证据：.scratch/diag_il2cpp_records2.py 对 12 个真实 blocked 游戏程序化交叉验证
# （8 字节记录各版本 100% UTF-8 可解码；v39 的 4 字节记录 100% 可解码且 8 字节假说 55% 坏）。
# 每版本：(litOff_pos, litSize_pos, dataOff_pos, dataSize_pos, entry_size, record_mode)
#   record_mode "explicit"：8 字节 <length, dataIndex>，长度显式
#   record_mode "implicit"：4 字节 <dataIndex>，长度 = 下一条 dataIndex 差值（末条到 data 区尾部）
# v39 额外约束：u32@0x10 == 记录数 == litSize / 4（Unity 6 新增字段，三个真实样本全部命中）。
_LAYOUTS = {
    24: (0x08, 0x0C, 0x10, 0x14, 8, "explicit"),
    27: (0x08, 0x0C, 0x10, 0x14, 8, "explicit"),
    29: (0x08, 0x0C, 0x10, 0x14, 8, "explicit"),
    31: (0x08, 0x0C, 0x10, 0x14, 8, "explicit"),
    39: (0x08, 0x0C, 0x14, 0x18, 4, "implicit"),
}
_ALLOWED_CONTROLS = {"\t", "\n", "\r"}
# 引擎/调试字符串特征（真实样本统计：老版 metadata 字符串池含大量
# 反汇编/日志/格式模板，游戏显示文本不具备这些形态）：
# - {0} / {1,6} / {0:x5} 格式占位符 → 代码模板（2328/16541 命中）
# - 前导 ≥2 空白 → 调试/反汇编输出（'  .locals '、'   Character:'）
# - 无字母（字符表/数字/纯标点）→ 不可译
_IL2CPP_FORMAT_PLACEHOLDER = re.compile(r"\{[0-9][^}]*\}")
# 控制符/≥2 空白开头 = 调试输出（'\ndepth: '、'  .locals '、字符表片段）
_IL2CPP_LEADING_WS = re.compile(r"^[\t\r\n]|^[ \t]{2,}")
_MIN_LITERAL_LEN = 3
# 识别 L3：metadata 字符串区（header 0x18/0x1C，Il2CppDumper 跨
# v24-v31 交叉验证的稳定布局）= 类型名/方法名/namespace/字段名全集。
# 字面量与字符串区成员相等是「反射/代码引用键」的确定性证据（typeof/
# GetMethod 参数等运行时按名查找），证据强度高于 is_code_identifier 的
# 形态正则——所以判跳过时细分 reason，且优先于 engine_morph 的长度猜测。
# v39（Unity 6）字符串区偏移未验证（Il2CppDumper 6.7.46 不支持），
# 不启用——待真实样本校准（评估报告 L3 同款措辞）。
_STRING_POOL_VERSION_OK = frozenset({24, 27, 29, 31})
_MAX_POOL_ENTRIES = 2_000_000  # 防畸形区段死循环的上限（正常池远小于此）

# 兼容引用：保留名称，值 = 各版本记录字节数。
SUPPORTED_LITERAL_RECORD_SIZES = {v: cfg[4] for v, cfg in _LAYOUTS.items()}


def find_metadata_file(game_dir: str | Path) -> Path | None:
    """il2cpp_data/Metadata/global-metadata.dat。"""
    game_dir = Path(game_dir)
    for p in game_dir.rglob("global-metadata.dat"):
        return p
    return None


def _has_illegal_controls(text: str) -> bool:
    return any(
        (ord(ch) < 0x20 and ch not in _ALLOWED_CONTROLS)
        or 0x7F <= ord(ch) <= 0x9F
        for ch in text
    )


def parse_string_literals(raw: bytes) -> list[tuple[int, int, int]]:
    """严格解析已验证版本的字面量池 → [(dataIndex, length, dataOffset)]。

    v24/v27/v29/v31 使用 8 字节 <length, dataIndex> 显式长度记录；
    v39 使用 4 字节 <dataIndex> 记录，长度由下一条差值隐含（末条到 data 区尾部）。
    """
    if len(raw) < _MIN_METADATA_HEADER_SIZE:
        return []
    magic, version = struct.unpack_from("<II", raw, 0)
    if magic != METADATA_MAGIC:
        return []
    layout = _LAYOUTS.get(version)
    if layout is None:
        return []
    (lit_off_pos, lit_size_pos, data_off_pos, data_size_pos,
     entry_size, record_mode) = layout
    lit_off, lit_table_size = struct.unpack_from("<II", raw, lit_off_pos)
    data_off, data_size = struct.unpack_from("<II", raw, data_off_pos)
    if ((lit_table_size and lit_off < _MIN_METADATA_HEADER_SIZE)
            or (data_size and data_off < _MIN_METADATA_HEADER_SIZE)):
        return []
    if (lit_table_size % entry_size != 0
            or lit_off + lit_table_size > len(raw)):
        return []
    if data_off > len(raw) or data_size > len(raw) - data_off:
        return []
    lit_table_end = lit_off + lit_table_size
    data_end = data_off + data_size
    if (lit_table_size and data_size
            and max(lit_off, data_off) < min(lit_table_end, data_end)):
        return []
    out: list[tuple[int, int, int]] = []
    if record_mode == "implicit":
        # v39：4 字节 dataIndex 记录，长度 = 下一条差值（末条到 data 区尾部）。
        # Unity 6 在 header 0x10 处新增「记录数」字段，必须与 litSize/4 一致。
        if version == 39:
            declared = struct.unpack_from("<I", raw, 0x10)[0]
            if declared != lit_table_size // entry_size:
                return []
        if lit_table_end > len(raw) or (lit_table_end - lit_off) % entry_size:
            return []
        count = (lit_table_end - lit_off) // entry_size
        indexes = struct.unpack_from(f"<{count}I", raw, lit_off)
        for i, data_index in enumerate(indexes):
            end = indexes[i + 1] if i + 1 < count else data_size
            length = end - data_index
            if length < 0 or data_index > data_size:
                return []
            out.append((data_index, length, data_off + data_index))
    else:
        occupied_ranges: list[tuple[int, int]] = []
        for i in range(lit_table_size // entry_size):
            pos = lit_off + i * entry_size
            if pos + entry_size > lit_table_end or pos + entry_size > len(raw):
                return []
            length, data_index = struct.unpack_from("<II", raw, pos)
            if data_index > data_size or length > data_size - data_index:
                return []
            out.append((data_index, length, data_off + data_index))
            if length:
                occupied_ranges.append((data_index, data_index + length))
        occupied_ranges.sort()
        if any(current_start < previous_end
               for (_, previous_end), (current_start, _) in
               zip(occupied_ranges, occupied_ranges[1:])):
            return []
    valid: list[tuple[int, int, int]] = []
    for data_index, length, data_pos in out:
        if length == 0:
            continue
        try:
            raw[data_pos:data_pos + length].decode("utf-8")
        except UnicodeDecodeError:
            continue
        valid.append((data_index, length, data_pos))
    return valid


def _metadata_string_pool(raw: bytes) -> frozenset[str]:
    """字符串区标识符全集（识别 L3）；布局非法/版本未验证 → 空集。

    解析失败一律降级为空集——分类链保持现状，解析失败不改变既有判定
    （与 L6 `_script_class_of` 同模式）。自校验：偏移/大小在界内、
    逐条 NUL 终结、strict UTF-8 可解码、总数有上限。
    """
    if len(raw) < _MIN_METADATA_HEADER_SIZE:
        return frozenset()
    magic, version = struct.unpack_from("<II", raw, 0)
    if magic != METADATA_MAGIC or version not in _STRING_POOL_VERSION_OK:
        return frozenset()
    str_off, str_size = struct.unpack_from("<II", raw, 0x18)
    if not str_size or str_off < _MIN_METADATA_HEADER_SIZE:
        return frozenset()
    if str_off + str_size > len(raw):
        return frozenset()
    blob = raw[str_off:str_off + str_size]
    names: set[str] = set()
    cursor = 0
    for _ in range(_MAX_POOL_ENTRIES):
        if cursor >= str_size:
            break
        end = blob.find(b"\x00", cursor)
        if end < 0:
            return frozenset()   # 区段尾部无 NUL → 不是字符串数组布局
        try:
            names.add(blob[cursor:end].decode("utf-8"))
        except UnicodeDecodeError:
            return frozenset()
        cursor = end + 1
    else:
        return frozenset()       # 超上限 → 畸形区段，不启用
    return frozenset(names)


def _independent_pool_records(raw: bytes) -> list[tuple[int, int, int]] | None:
    """第二套独立字符串池读取器（交叉验证用，不共享 parse 的防御逻辑）。

    直接按 header 字段硬读记录区：explicit 逐条 <length, dataIndex>，
    implicit 差分（末条 = data_size - dataIndex）。不依赖 occupied_ranges
    重叠防御、不做 UTF-8/非零长过滤——返回记录区全部条目
    [(data_index, length, data_pos)]；布局非法返回 None。

    用途：写回前的「同源盲区」防御——提取/重开验证与 parse 共用同一套
    解析代码，若对布局有系统性误解，自证失效。独立读取器以不同代码路径
    重新推导全部记录，任何解析偏移/截断/防御误放行都会被交叉核对捕获。
    """
    if len(raw) < _MIN_METADATA_HEADER_SIZE:
        return None
    magic, version = struct.unpack_from("<II", raw, 0)
    if magic != METADATA_MAGIC:
        return None
    layout = _LAYOUTS.get(version)
    if layout is None:
        return None
    (lit_off_pos, lit_size_pos, data_off_pos, data_size_pos,
     entry_size, record_mode) = layout
    lit_off, lit_size = struct.unpack_from("<II", raw, lit_off_pos)
    data_off, data_size = struct.unpack_from("<II", raw, data_off_pos)
    if not lit_size or not data_size:
        return None
    if lit_off + lit_size > len(raw) or data_off + data_size > len(raw):
        return None
    out: list[tuple[int, int, int]] = []
    if record_mode == "implicit":
        count = lit_size // entry_size
        if not count or lit_off + count * 4 > len(raw):
            return None
        indexes = struct.unpack_from(f"<{count}I", raw, lit_off)
        for i, data_index in enumerate(indexes):
            end = indexes[i + 1] if i + 1 < count else data_size
            if data_index > data_size or end < data_index:
                return None
            out.append((data_index, end - data_index, data_off + data_index))
    else:
        for i in range(lit_size // entry_size):
            pos = lit_off + i * entry_size
            if pos + entry_size > len(raw):
                return None
            length, data_index = struct.unpack_from("<II", raw, pos)
            if data_index > data_size or length > data_size - data_index:
                return None
            out.append((data_index, length, data_off + data_index))
    return out


def _cross_validate_pool(raw: bytes) -> bool:
    """parse_string_literals 与独立读取器交叉核对。

    规则：独立读取器全部条目中「非零长且 strict UTF-8 可解码」的子集
    必须与 parse 的 valid 结果逐条一致（顺序与数量一致）。两套代码路径
    独立推导，任一偏移/过滤错误即不一致。
    """
    parsed = parse_string_literals(raw)
    independent = _independent_pool_records(raw)
    if independent is None:
        return False
    expect: list[tuple[int, int, int]] = []
    for data_index, length, data_pos in independent:
        if length == 0:
            continue
        try:
            raw[data_pos:data_pos + length].decode("utf-8")
        except UnicodeDecodeError:
            continue
        expect.append((data_index, length, data_pos))
    return expect == parsed


def metadata_data_layout(raw: bytes) -> tuple[int, int, str] | None:
    """(data_off, data_size, record_mode)；解析失败返回 None。

    供写回侧把「提取时记录的 file_offset」换算成 data_index，以及断言
    写回范围。与 parse_string_literals 共用同一版本白名单。
    """
    if len(raw) < _MIN_METADATA_HEADER_SIZE:
        return None
    magic, version = struct.unpack_from("<II", raw, 0)
    layout = _LAYOUTS.get(version)
    if layout is None:
        return None
    (_lit_off_pos, _lit_size_pos, data_off_pos, data_size_pos,
     _entry_size, record_mode) = layout
    data_off = struct.unpack_from("<I", raw, data_off_pos)[0]
    data_size = struct.unpack_from("<I", raw, data_size_pos)[0]
    if not data_size or data_off >= len(raw) or data_size > len(raw) - data_off:
        return None
    return data_off, data_size, record_mode


def patch_metadata_strings(raw: bytes, changes: dict[int, bytes]) -> bytes:
    """按 data_index 原位替换字面量数据,并同步修复长度语义(尾部 NUL 修复)。

    explicit(v24/27/29/31):记录区 <length> 字段更新为译文实际字节数,数据原位;
    运行时按记录长度读取 = 译文,不再带尾部 NUL 填充。剩余容量区域保持原字节
    (不被任何记录引用,运行时按更新后的 length 读取)。

    implicit(v39):没有 length 字段,每条长度由「下一条 dataIndex 差值」决定
    (末条 = data_size - dataIndex)——收缩后若不前移后续记录,运行时读到的
    长度仍是旧值,尾部残留照样进字符串。全部记录连续紧凑排列到数据区头部
    (记录间零间隙,每条差分长度 = 下一条差值 = 实际字节数),并同步改小
    header 的 dataSize 字段(= 新总长)——末条差分以 data_size 为锚,若不
    改小,空洞(原数据区尾部)会被末条差分吞进字符串(尾部 NUL 复现);
    改小后空洞落在数据区声明之外,不被任何记录引用。数据区之后的物理字节
    原位保留,其他区段按各自显式 offset 定位,不受 dataSize 影响。
    全部 dataIndex 链式更新,记录数不变。

    explicit(v24/27/29/31):记录 <length> 字段显式,数据原位覆盖,无差分
    问题,dataSize/header 一律不动。两种模式都不改记录数/其他区偏移。
    """
    if not changes:
        return raw
    if len(raw) < _MIN_METADATA_HEADER_SIZE:
        raise ValueError("metadata 文件过短,无法补丁")
    magic, version = struct.unpack_from("<II", raw, 0)
    if magic != METADATA_MAGIC:
        raise ValueError("非 global-metadata.dat(magic 不匹配)")
    layout = _LAYOUTS.get(version)
    if layout is None:
        raise ValueError(f"不支持的 metadata 版本: {version}")
    (lit_off_pos, lit_size_pos, data_off_pos, data_size_pos,
     entry_size, record_mode) = layout
    lit_off, lit_table_size = struct.unpack_from("<II", raw, lit_off_pos)
    data_off, data_size = struct.unpack_from("<II", raw, data_off_pos)
    if not lit_table_size or not data_size:
        raise ValueError("metadata 字面量表或数据区为空")
    records = parse_string_literals(raw)
    if not records:
        raise ValueError("metadata 字面量池无法解析,拒绝补丁")
    # 同源盲区防御：提取/重开验证与 parse 共用同一套解析，若对布局有
    # 系统性误解则自证失效——写回前用第二套独立读取器交叉核对
    if not _cross_validate_pool(raw):
        raise ValueError("metadata 字面量池交叉验证不一致,拒绝补丁")
    by_index = {data_index: (length, data_pos)
                for data_index, length, data_pos in records}
    for data_index, payload in changes.items():
        if data_index not in by_index:
            raise ValueError(f"data_index {data_index} 不在字面量记录表中")
        if len(payload) > by_index[data_index][0]:
            raise ValueError(
                f"译文 {len(payload)} 字节超过容量 "
                f"{by_index[data_index][0]}（data_index={data_index}）")
    blob = bytearray(raw)
    if record_mode == "explicit":
        # 记录区全部条目按 data_index 索引——绝不能用 valid 记录序号推算
        # 记录区位置：parse 的 UTF-8/非零长过滤会破坏「序号 ↔ 记录区位置」
        # 的对应（cosl 实证：15170 条目 1 条被过滤 → length 字段写错条目
        # → 重开区间重叠）。同一 data_index 可能有多条记录（空字符串），
        # 全部同步更新 length 字段。
        pos_of: dict[int, list[tuple[int, int]]] = {}
        for i in range(lit_table_size // entry_size):
            pos = lit_off + i * entry_size
            length, data_index = struct.unpack_from("<II", blob, pos)
            pos_of.setdefault(data_index, []).append((pos, length))
        for data_index, payload in changes.items():
            _length, data_pos = by_index[data_index]
            blob[data_pos:data_pos + len(payload)] = payload
            # explicit 记录 = <length, dataIndex>：length 在记录起点。
            # 同一 data_index 可有多条记录（空字符串 length=0 与实数据
            # 共享偏移，运行时读空）——只更新 length>0 的实际条目：空
            # 记录保持 0 才不新增区间重叠（parse 防御检查不误伤），且
            # 运行时语义不变（空记录仍读空字符串）。
            for pos, rec_len in pos_of.get(data_index, ()):
                if rec_len > 0:
                    struct.pack_into("<I", blob, pos, len(payload))
    else:
        # implicit：记录区全部条目（含 parse 过滤掉的空/非 UTF-8 记录）
        # 参与紧凑重建——valid 过滤掉的条目若被丢下，记录区残留旧
        # dataIndex，dataSize 缩小后越界（minato 实证：末 2 条残留
        # 528463/528466 > 新 dataSize → 重开解析整体拒绝）。
        # 全部记录连续紧凑到数据区头部（零间隙），差分长度含空洞原样
        # 搬运（运行时读取语义不变），末条差分以 data_size 为锚 → 同步
        # 改小 dataSize 字段，空洞（原数据区尾部）落在数据区声明之外，
        # 清零保持确定性。全部 dataIndex 链式更新，记录数不变。
        count = lit_table_size // entry_size
        indexes = struct.unpack_from(f"<{count}I", blob, lit_off)
        new_indexes: dict[int, int] = {}
        cursor = 0
        for i, data_index in enumerate(indexes):
            end = indexes[i + 1] if i + 1 < count else data_size
            length = end - data_index
            payload = changes.get(data_index)
            new_len = len(payload) if payload is not None else length
            new_indexes[data_index] = cursor
            if payload is not None:
                blob[data_off + cursor:data_off + cursor + new_len] = payload
            else:
                blob[data_off + cursor:data_off + cursor + new_len] = (
                    raw[data_off + data_index:data_off + end])
            cursor += new_len
        if cursor > data_size:
            raise ValueError("metadata 数据区溢出：紧凑重建超出 data_size")
        blob[data_off + cursor:data_off + data_size] = (
            b"\x00" * (data_size - cursor))
        struct.pack_into("<I", blob, data_size_pos, cursor)
        for i, data_index in enumerate(indexes):
            struct.pack_into("<I", blob, lit_off + i * entry_size,
                             new_indexes[data_index])
    _assert_diff_whitelist(
        raw, blob, record_mode=record_mode, lit_off=lit_off,
        lit_table_size=lit_table_size, data_off=data_off,
        data_size=data_size, data_size_pos=data_size_pos,
        entry_size=entry_size, changes=changes, by_index=by_index,
        cursor=cursor if record_mode == "implicit" else None)
    return bytes(blob)


def _assert_diff_whitelist(raw: bytes, blob: bytearray, *, record_mode: str,
                           lit_off: int, lit_table_size: int, data_off: int,
                           data_size: int, data_size_pos: int, entry_size: int,
                           changes: dict[int, bytes],
                           by_index: dict[int, tuple[int, int]],
                           cursor: int | None = None) -> None:
    """写回差异白名单：patch 前后逐字节 diff，所有差异必须落在合法变更
    范围内——header 其他字段、其他区段（方法名表/类表等游戏逻辑所在）
    零字节被碰（「不影响游戏」的硬保证）。

    explicit：允许差异 = 被改记录的数据段 [data_pos, data_pos+len(payload))
    + 记录区 length 字段（记录起点 4 字节，仅 length>0 条目——与补丁
    逻辑同判据，空记录不更新）。
    implicit：允许差异 = 数据区 [data_off, data_off+cursor)（紧凑重建）
    + dataSize 字段 + 记录区全部条目（链式更新）。
    """
    patched = bytes(blob)
    if len(patched) != len(raw):
        raise ValueError(f"写回改变了文件长度 {len(raw)} -> {len(patched)}")
    if record_mode == "explicit":
        allowed: set[int] = set()
        for data_index, payload in changes.items():
            _length, data_pos = by_index[data_index]
            allowed.update(range(data_pos, data_pos + len(payload)))
            for i in range(lit_table_size // entry_size):
                pos = lit_off + i * entry_size
                length, di = struct.unpack_from("<II", raw, pos)
                if di == data_index and length > 0:
                    allowed.update(range(pos, pos + 4))
        bad = [i for i in range(len(raw))
               if raw[i] != patched[i] and i not in allowed]
    else:
        if cursor is None:
            raise ValueError("implicit 白名单需要 cursor")
        # 数据区允许范围 = 整个 [data_off, data_off+data_size)：紧凑重建
        # 搬移全部记录 + 空洞（原数据区尾部）清零覆盖数据区全部字节；
        # 白名单的意义是锁定「数据区/记录区/dataSize 之外零字节被碰」
        intervals = [
            (data_off, data_off + data_size),
            (data_size_pos, data_size_pos + 4),
            (lit_off, lit_off + lit_table_size),
        ]
        bad = [i for i in range(len(raw))
               if raw[i] != patched[i]
               and not any(a <= i < b for a, b in intervals)]
    if bad:
        raise ValueError(
            f"写回差异越出白名单 {len(bad)} 处（首例 0x{bad[0]:x}），"
            "文件被意外改动，拒绝")


def extract_metadata_strings(path: str | Path, file_id: str | None = None,
                             progress_cb: Callable | None = None) -> ParsedFile:
    """提取 metadata 字符串字面量 → ParsedFile。"""
    p = Path(path)
    fid = file_id or str(p).replace("\\", "/")
    raw = p.read_bytes()
    entries: list[TextEntry] = []
    skipped: dict[str, int] = {}  # R5 静默跳过留档（哑识别可见化）
    # 识别 L3：字符串区标识符全集（类型名/方法名/namespace 名）——
    # 字面量与它相等是反射/代码引用键的确定性证据；解析失败 → 空集
    # 降级（分类链保持现状）
    metadata_strings = _metadata_string_pool(raw)
    for data_index, length, data_pos in parse_string_literals(raw):
        if data_pos + length > len(raw):
            # R5：记录越界（池损坏/解析器边界）静默跳过留档
            skipped["literal_oob"] = skipped.get("literal_oob", 0) + 1
            continue
        try:
            s = raw[data_pos:data_pos + length].decode("utf-8")
        except UnicodeDecodeError:
            skipped["decode_failed"] = skipped.get("decode_failed", 0) + 1
            continue
        if _has_illegal_controls(s):
            # R5/L1：非法控制字符静默跳过留档（计数 + 限量样本）
            skipped["illegal_controls"] = skipped.get("illegal_controls", 0) + 1
            sample = _skipped_sample_entry(
                fid, f"skip/meta#{data_index}", s, kind="il2cpp",
                reason="illegal_controls",
                count=skipped["illegal_controls"])
            if sample:
                entries.append(sample)
            continue
        # 代码池严格键检测：无空格标识符是枚举名/绑定名，绝不翻译
        if should_skip(s) or is_code_identifier(s) or _is_engine_string(s):
            # R5/L1：代码标识符/引擎串静默跳过留档（计数 + 限量样本）
            skipped["code_identifier"] = skipped.get("code_identifier", 0) + 1
            sample = _skipped_sample_entry(
                fid, f"skip/meta#{data_index}", s, kind="il2cpp",
                reason="code_identifier",
                count=skipped["code_identifier"])
            if sample:
                entries.append(sample)
            continue
        # 识别 L3：确定性反射键——字面量 == metadata 字符串区成员（类型名/
        # 方法名/namespace/字段名）。is_code_identifier 是形态正则猜测，这里
        # 是集合命中的事实证据（typeof/GetMethod 参数等运行时按名查找键），
        # 优先于 engine_morph 的长度猜测（证据分层：确定性 > 形态）。
        if s in metadata_strings:
            skipped["reflection_key"] = skipped.get("reflection_key", 0) + 1
            sample = _skipped_sample_entry(
                fid, f"skip/meta#{data_index}", s, kind="il2cpp",
                reason="reflection_key", count=skipped["reflection_key"])
            if sample:
                entries.append(sample)
            continue
        # 引擎/调试形态：格式模板、反汇编/日志输出、字符表 → 不产生条目
        # （真实样本 16541 条中 65% 属此类，minato/seijunDROP v24 池）
        if (_IL2CPP_FORMAT_PLACEHOLDER.search(s)
                or _IL2CPP_LEADING_WS.match(s)
                or len(s) < _MIN_LITERAL_LEN
                or not any(ch.isalpha() for ch in s)):
            # R5/L1：引擎/调试形态静默跳过留档（计数 + 限量样本）
            skipped["engine_morph"] = skipped.get("engine_morph", 0) + 1
            sample = _skipped_sample_entry(
                fid, f"skip/meta#{data_index}", s, kind="il2cpp",
                reason="engine_morph", count=skipped["engine_morph"])
            if sample:
                entries.append(sample)
            continue
        # 剩余字面量分类。真实样本验证（minato/seijunDROP 老版池）：
        # 池内容几乎全是引擎字符串（异常消息/属性名/系统库字符表），游戏
        # 显示文本在资源而非代码字面量——句子形态只是「可能」而非证据。
        # - 交互提示形态 → display/medium（可翻译）
        # - 句子形态 → display/low（留档可见、不可自动翻译——质量门禁
        #   is_actionable_translation 要求 confidence≠low）
        # - 其余（词/短语）→ structural/low 留档（「过滤不是删除」）
        interaction = is_strong_interaction_prompt(s)
        sentence_like = " " in s and s[0].isalpha() and s[-1].isalnum()
        if interaction:
            status, confidence, role, disposition, reason = (
                "pending", "medium", "display", "translate",
                "il2cpp_interaction_prompt")
        elif sentence_like:
            status, confidence, role, disposition, reason = (
                "pending", "low", "display", "translate",
                "il2cpp_sentence")
        else:
            status, confidence, role, disposition, reason = (
                STATUS_SKIPPED, "low", "structural", "structural",
                "il2cpp_literal")
        entries.append(TextEntry(
            file_id=fid, key_path=f"meta#{data_index}",
            original=s, status=status,
            meta={
                "kind": "il2cpp", "file_offset": data_pos, "length": length,
                "confidence": confidence, "role": role,
                "disposition": disposition, "reason": reason,
            }))
    for e in entries:
        if e.status == "pending" and (should_skip(e.original) or is_code_identifier(e.original)):
            e.status = STATUS_SKIPPED
    # 样本计数回写：限量样本的 skipped_count 是累计值，报告聚合需
    # 真实总数（消费端按 (file_id, reason, obj) 取 max）
    _finalize_skipped_counts(entries, skipped)
    noise = looks_like_noise_file(entries)
    return ParsedFile(fid, str(p), "v2_il2cpp", entries, "utf-8", "\n",
                      {"kind": "il2cpp"}, noise, skipped)
