"""文件发现：只找游戏内容文本，严格排除 Unity 运行时噪音。

识别模型（见 docs/Unity游戏文本位置与提取全景指南.md §5.1）：
1) 扩展名是第一层线索（TEXT_EXTENSIONS），但不是唯一依据；
2) 无扩展名/伪装扩展名（.dat/.bin/.bytes/.pak/未知）文件按魔数 + 文本启发式路由，
   不再让「扩展名白名单」成为静默丢弃理由；
3) 容器（ZIP/SQLite/GZip/UnityFS/SerializedFile/WebFile）由内容探测识别。
"""
from __future__ import annotations
from collections.abc import Iterator
from collections.abc import Iterable
import os
from pathlib import Path

from hanhua.core.paths import _is_reparse_point

# 松散文本格式（含剧情脚本/字幕/本地化，见指南 §5.1 建议清单）
TEXT_EXTENSIONS = {
    ".json", ".json5", ".jsonl", ".ndjson",
    ".csv", ".tsv", ".psv",
    ".xml", ".resx", ".xlf", ".xliff", ".tmx",
    ".html", ".htm", ".md",
    ".txt", ".ini", ".cfg", ".conf", ".config", ".lang", ".loc", ".properties",
    ".yaml", ".yml", ".toml", ".po", ".arb",
    ".srt", ".vtt", ".ass", ".ssa", ".ttml", ".lrc",
    ".ink", ".yarn",
    # 实测变体（containment-breach-hd）：Language/ 下 JSON 内容的
    # 字幕/语言文件，扩展名非标准但必为文本
    ".subs", ".langs",
    # NodeEditorFramework 对话脚本（shellcore 实证 900+ 条对话真盲区）：
    # Text("key", "对话内容") 行格式，游戏对话系统核心数据
    ".corescript",
}
ASSET_EXTENSIONS = {".assets", ".ab", ".unity3d", ".bundle", ".pak", ".bytes"}
# 伪装扩展名：内容完全未知，一律探测（可能是文本/容器/二进制）
PROBE_EXTENSIONS = frozenset({".bytes", ".dat", ".bin", ".save", ".datas"})
# 已知二进制/媒体后缀：跳过内容探测（不可能承载可译文本）
_BINARY_SUFFIXES = frozenset({
    ".dll", ".exe", ".so", ".dylib", ".a", ".lib", ".pdb", ".mdb",
    ".ress", ".resource", ".resdata",
    # 编译/构建产物源码（IL2CPP 输出、工程残留）：可打印率高会被文本启发式
    # 误收（backrooms 的 il2cppOutput/*.c 实测 639 万条目），文件级兜底排除。
    # 注意：.json 不能进黑名单——它是常见本地化格式（TEXT_EXTENSIONS 先路由）
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx", ".cs", ".java",
    ".sln", ".csproj", ".vcxproj",

    ".png", ".jpg", ".jpeg", ".gif", ".tga", ".bmp", ".psd", ".webp",
    ".ico", ".cur", ".dds", ".ktx", ".pvr", ".astc", ".hdr",
    # IFF/Reflexive .rgb、Amiga .iff 等图像：内容探测会把灰度纹理（像素
    # 字节集中 0x20-0x7E，strict UTF-8 可过）误判为文本（实测 honorplusplus/
    # sonic-suggests/thirstiest 3 游戏 .rgb 位图被提取成条目 → 写回阻断）。
    # .rgb/.iff 现实中没有游戏用作文本扩展名，文件级黑名单直接跳过。
    ".rgb", ".iff", ".ilbm", ".sgi",
    ".wav", ".ogg", ".mp3", ".mp4", ".webm", ".avi", ".mov", ".wem",
    ".bank", ".bnk", ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".fbx", ".obj", ".blend", ".anim", ".controller", ".mixer",
    ".prefab", ".asset", ".unity", ".mat", ".shader",
    ".exr", ".tif", ".tiff", ".pdf",
    # Unity GI/场景缓存自定义序列化（调查实证：tQ\x10\xad 魔数，
    # 6+ 游戏大量文件，字节扫描仅随机噪声，无可译文本）
    ".caw", ".ecm", ".sse", ".vis", ".pos",
})
# Unity 运行时日志与 Mono 调试符号：探测也会被识别为文本，但绝非本地化
_NOISY_PROBE_EXTS = frozenset({".log", ".trace"})
# macOS 打包残留（F43，bubble-jcat 实证）：.DS_Store 文件索引与
# ._ 前缀 AppleDouble 元数据——探测会被识别为文本，绝非本地化
_MAC_RESIDUE_PREFIX = "._"
# NodeCanvas/NodeEditorFramework 图数据（F51c，shellcore 实证 9 万条
# 过度识别）：.sectordata/.dialoguedata/.taskdata/.worlddata 是 XML
# 节点图结构（节点名/变量名 = 代码键），按文本/XML 解析会把图结构
# 全量进池——与 census（F50）同一排除口径。.corescript 是真实对话
# 脚本（Text("key", "对话") 行），必须保留
_NODE_CANVAS_DATA_EXTS = frozenset({
    ".sectordata", ".dialoguedata", ".taskdata", ".worlddata",
})

# Unity/引擎运行时目录：永远不是本地化文本
SKIP_DIRS = {".git", ".svn", "__pycache__", ".idea", ".vs", "Library", "Temp", "Logs", "obj",
             "Build", "build", "MonoBleedingEdge", "MonoBundle", "il2cpp_data", "mono",
             "UnityCrashHandler", "Boot.config", "Unity_gameresources",
             # macOS 打包残留（zip 从 Mac 解压产生，bubble-jcat 实证）：
             # AppleDouble 元数据目录
             "__MACOSX",
             # 工具部署的运行时（BepInEx 字体覆盖）：0Harmony.xml 等 API 文档
             # 会被误扫为文本（ned-flanders 副本写回实测 42 条失败）
             "BepInEx", "doorstop",
             # F56（Rendezvous 实证）：Steamworks 破解配置目录
             # （steam_settings 含空 achievements.json——空 JSON 曾致
             # 扫描崩溃；破解配置非游戏内容，整目录跳过）
             "steam_settings", "steam_interfaces",
             # IL2CPP 转换产物（<Game>_BackUpThisFolder_ButDontShipItWithYourGame/ 下）：
             # 生成的 C++ 源码，每行 #include/#ifndef 会被文本启发式收为「文本文件」，
             # 单游戏实测 639 万条目（backrooms）——目录名固定，整树剪掉
             "il2cppOutput", "il2cppSymbols"}
# 已知 Unity 运行时噪音文件（打包必带，绝非本地化）
# 注意：data.unity3d 不在黑名单——它是 Unity 5.x 的合并场景（GameName_Data/ 下），
# 含全部场景文本（crash-back-in-time/hickory 识别不全的根因，见 ISSUES #190）。
SKIP_FILES = {
    "browscap.ini",
    "ScriptingAssemblies.json", "RuntimeInitializeOnLoads.json",
    "UnityServicesProjectConfiguration.json", "link.xml",
    "UnityPlayer.dll", "GameAssembly.dll", "UnityEngine.dll",
    "globalgamemanagers", "globalgamemanagers.assets",
    # 引擎内置资源（Resources/ 下）：默认 shader/material/字体，无游戏文本。
    # 无后缀名 + SerializedFile 头自洽判定会被误收（实测每游戏 2 个噪音文件）。
    "unity_builtin_extra", "unity default resources",
    # Unity 运行时日志（打包必带，纯硬件/启动噪音，绝非本地化）
    "output_log.txt", "player.log", "error.log",
    # Unity 自动生成的游戏名/公司名文件（DefaultCompany␤游戏名）——
    # 78-hour-rain 实证：被当文本翻译写回（'78 Hour Rain'→'78小时降雨'，
    # 游戏名被改坏）。census（F34）已跳过，提取管线（F36）同步跳过。
    "app.info",
    # BepInEx 部署文件（.ini 属 TEXT_EXTENSIONS，不排除会被误扫）
    "doorstop_config.ini",
}
# 注意：StreamingAssets/aa/ 是 Addressables 打包的游戏内容（含 Localization 表），
# 绝不能整目录跳过——只靠文件名黑名单 + 文件级噪音判定兜底。
# 子串匹配的目录模式：<Game>_BackUpThisFolder_ButDontShipItWithYourGame（前缀带
# 游戏名，exact 匹配无效）；其下 il2cppOutput/ 由 SKIP_DIRS 精确剪掉。
SKIP_DIR_PATTERNS = ("backupthisfolder_butdontshipitwithyourgame",)
BURST_DEBUG_DIR_SUFFIX = "_burstdebuginformation_donotship"
_SKIP_DIR_KEYS = frozenset(name.casefold() for name in SKIP_DIRS)
_SKIP_FILE_KEYS = frozenset(name.casefold() for name in SKIP_FILES)
_UNITY_BUNDLE_MAGICS = (b"UnityFS", b"UnityWeb", b"UnityRaw")
# UnityCN（中国区）加密 bundle 签名（#$unity3dchina!@）：识别为加密态，
# 不尝试解析——标记 blocked 而非静默跳过（需 SetAssetBundleDecryptKey）
_UNITYCN_ENC_MAGIC = b"#$unity3dchina!@"
# Unity SerializedFile 无魔数：头部字段恒为大端存储（历史遗产），off16 的
# endian 字节只指示对象数据端序。判定 = 4 字段自洽性检查（见 _looks_like_serialized_file）。
# 注意：b"\x42\x89\xe3\x0d"（0x0DE38942）是 Addressables catalog.bin 的
# BinaryStorageBuffer kMagic（ContentCatalogData.Serialize），不是 SerializedFile
# 魔数——在此大端读法下它 version 巨大被拒绝，走 binary 分支（见 _update_addressables_catalogs
# 的字节级 CRC 替换，catalog 不需要解析）。
_WEBFILE_MAGIC = b"UnityWebData1.0"
_SQLITE_MAGIC = b"SQLite format 3\x00"
_ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06")
_GZIP_MAGIC = b"\x1f\x8b"
_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
_LZ4_MAGIC = b"\x04\x22\x4d\x18"
# Reflexive/Amiga IFF 位图（.rgb/.iff）：FORM + 4 字节大小 + 表单类型。
# 表单类型恒为 4 字节大写 ASCII（RTEXVERS 等）；精确匹配「FORM 后第 9-16
# 字节 == RTEXVERS」——文本开头恰好是 "FORMxxxxRTEXVERS" 的概率趋零。
_IFF_RTEX_MAGIC = b"RTEXVERS"
_PROBE_HEAD_BYTES = 8192
# 文本判定：可打印字节比例阈值（UTF-8/ASCII/GBK 文本远高于此，二进制远低于）
_TEXT_PRINTABLE_RATIO = 0.92
_TEXT_BOMS = (b"\xef\xbb\xbf", b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff",
              b"\xff\xfe", b"\xfe\xff")


def _has_unity_bundle_magic(path: Path) -> bool:
    """旧版兼容：无扩展名文件的 UnityFS/UnityWeb/UnityRaw 魔数探测。

    新代码请用 probe_file_kind()（支持任意后缀 + SerializedFile/WebFile/容器）。
    """
    if path.suffix or path.is_symlink():
        return False
    return probe_file_kind(path) == "unity"


def probe_head_kind(head: bytes) -> str:
    """按内容头探测文件种类（魔数优先，文本启发式兜底）。

    返回：unity / serialized / webfile / zip / sqlite / gzip / zstd / lz4
          / text / binary / unknown
    """
    if head.startswith(_UNITY_BUNDLE_MAGICS):
        return "unity"
    if head.startswith(_UNITYCN_ENC_MAGIC):
        return "unitycn_encrypted"
    if _looks_like_serialized_file(head):
        return "serialized"
    if head.startswith(_WEBFILE_MAGIC):
        return "webfile"
    if head.startswith(_ZIP_MAGICS):
        return "zip"
    if (head.startswith(b"FORM") and len(head) >= 16
            and head[8:16] == _IFF_RTEX_MAGIC):
        # Reflexive .rgb 位图：BODY 为像素数据（无扩展名副本/伪装场景），
        # 灰度像素字节可过文本启发式，必须魔数级拦截（实测 3 游戏误提取）
        return "binary"
    if head.startswith(_SQLITE_MAGIC):
        return "sqlite"
    if head.startswith(_GZIP_MAGIC):
        return "gzip"
    if head.startswith(_ZSTD_MAGIC):
        return "zstd"
    if head.startswith(_LZ4_MAGIC):
        return "lz4"
    if _looks_like_text(head):
        return "text"
    if not head:
        return "unknown"
    return "binary"


def _looks_like_serialized_file(head: bytes) -> bool:
    """Unity SerializedFile 头部自洽性检查（大端，对齐 UnityPy check_file_type）。

    v22+ 头（48 字节）：metadata_size(0) file_size(4) version(8) data_offset(12)
    endian(16)+reserved(17-19) metadata_size(20) file_size u64(24) data_offset
    u64(32) unknown(40)——全部大端。老版本头 16 字节。
    """
    if len(head) < 48:
        return False
    metadata_size = int.from_bytes(head[0:4], "big")
    file_size = int.from_bytes(head[4:8], "big")
    version = int.from_bytes(head[8:12], "big")
    data_offset = int.from_bytes(head[12:16], "big")
    if version >= 22:
        metadata_size = int.from_bytes(head[20:24], "big")
        file_size = int.from_bytes(head[24:32], "big")
        data_offset = int.from_bytes(head[32:40], "big")
    return (0 <= version <= 100
            and 0 < file_size
            and 0 <= metadata_size <= file_size
            and 0 < data_offset <= file_size)


def _looks_like_text(head: bytes) -> bool:
    """轻量文本启发式：BOM 明确 → 文本；否则可打印率 + 字母存在性。"""
    if not head:
        return False
    if head.startswith(_TEXT_BOMS):
        return True
    sample = head[:4096]
    printable = sum(
        1 for byte in sample
        if byte >= 0x20 or byte in (0x09, 0x0A, 0x0D))
    if printable / max(1, len(sample)) < _TEXT_PRINTABLE_RATIO:
        return False
    try:
        text = sample.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        # 高可打印率的非 UTF-8 多为 GBK/Shift-JIS 等东亚编码文本
        return True
    return any(ch.isalnum() for ch in text)


def probe_file_kind(path: Path) -> str:
    """读取文件头（≤8KB）并探测种类；OSError 时返回 'unknown'。"""
    try:
        with path.open("rb") as stream:
            head = stream.read(_PROBE_HEAD_BYTES)
    except OSError:
        return "unknown"
    return probe_head_kind(head)


def _is_runtime_dir_name(name: str) -> bool:
    key = name.casefold()
    if key in _SKIP_DIR_KEYS or key.endswith(BURST_DEBUG_DIR_SUFFIX):
        return True
    # 子串匹配（路径段包含）：<Game>_BackUpThisFolder_ButDontShipItWithYourGame
    # 前缀带游戏名，用「_」连接而非路径分隔符，只能按段包含判定
    return any(pattern.casefold() in key for pattern in SKIP_DIR_PATTERNS)


def _walk_files(
        game_dir: Path, *, exclude_roots: Iterable[str | Path] = ()) -> Iterator[Path]:
    """惰性遍历文件，并在 os.walk 下探前剪掉运行时目录树。

    Windows junction 在 os.walk 中 islink 为 False（默认会跟随），若链接指向
    祖先目录会无限循环卡死扫描 → 下探前剪掉所有 reparse point。
    """
    excluded = {Path(path).absolute() for path in exclude_roots}
    for root, dirs, files in os.walk(game_dir, topdown=True):
        root_path = Path(root)
        dirs[:] = sorted(
            name for name in dirs
            if not _is_runtime_dir_name(name)
            and not _is_reparse_point(root_path / name)
            and (root_path / name).absolute() not in excluded)
        for name in sorted(files):
            yield root_path / name


def _is_runtime_file(p: Path, game_dir: Path) -> bool:
    # 汉化工具自身生成的备份/清单（点文件 + .bak/.tmp，Rendezvous 实证
    # 2026-08-17）：.pre-xxx.bak / .xxx.hanhua-*.tmp 等被扫描产生 650+
    # 条重复待翻译，且写回可能污染备份。游戏内容不会放在点文件/备份
    # 后缀里，统一排除（Windows 隐藏文件 + 工具产物）。
    if p.name.startswith("."):
        return True
    if p.suffix.lower() in {".bak", ".tmp", ".orig", ".old"}:
        return True
    if p.name.casefold() in _SKIP_FILE_KEYS:
        return True
    rel_parts = p.relative_to(game_dir).parts
    dir_parts = rel_parts[:-1]  # 目录段检查限定目录——文件名命中目录名
    # （如无扩展名文件恰叫 Temp/Logs/Build）会误伤真实文本文件
    if any(part.casefold() in _SKIP_DIR_KEYS for part in dir_parts):
        return True
    if any(part.casefold().endswith(BURST_DEBUG_DIR_SUFFIX) for part in dir_parts):
        return True
    # 路径段包含 SKIP_DIR_PATTERNS（<Game>_BackUpThisFolder_... 前缀名）
    if any(pattern.casefold() in part.casefold()
           for part in dir_parts for pattern in SKIP_DIR_PATTERNS):
        return True
    rel = "/".join(rel_parts).casefold()
    if ("/managed/" in rel or rel.startswith("managed/")) and p.suffix.lower() == ".xml":
        # Managed/*.xml 是引擎/程序集 API 文档注释（UnityEngine.AIModule.xml、
        # Assembly-CSharp.xml），不是本地化内容（真实失败样本 42 条）
        return True
    if p.suffix.lower() == ".txt" and any(
            part in p.stem.casefold().split("_") for part in
            ("credits", "credit", "license", "licence", "readme")):
        # F54（bad-faith 实证）：credit/README 文件——人名/品牌/法律文本
        # 翻译无意义且必坏；README_Credits_MoreInfo.txt 是 windows-1252
        # 编码（中文写回被正确阻断，文件本身该跳过）。段匹配
        # （split("_") 任意段）覆盖 README_Credits 组合名。
        return True
    return False


# 含文本的容器/结构化二进制：文本扫描阶段直接纳入（由 parse_file 路由）
_TEXT_CONTAINER_KINDS = frozenset({"zip", "sqlite", "gzip"})


def discover(
        game_dir: str | Path, include_assets: bool = False, *,
        exclude_roots: Iterable[str | Path] = ()) -> list[Path]:
    """递归扫描游戏目录。

    - 文本/容器（ZIP/SQLite/GZip/伪装文本）：始终发现；
    - Unity 二进制资源（.assets / AssetBundle / SerializedFile / WebFile）：
      仅 include_assets=True 时发现（由 v2 扫描负责）。
    无扩展名/伪装扩展名文件按内容探测路由，不再静默丢弃。
    """
    game_dir = Path(game_dir)
    found: list[Path] = []
    for p in _walk_files(game_dir, exclude_roots=exclude_roots):
        if _is_runtime_file(p, game_dir):
            continue
        suffix = p.suffix.lower()
        # F51c：NodeCanvas 图数据不是文本（节点名/变量名=代码键），
        # 即使 XML 内容也整体排除（防 9 万条图结构进池）
        if suffix in _NODE_CANVAS_DATA_EXTS:
            continue
        if suffix in TEXT_EXTENSIONS:
            found.append(p)
            continue
        if include_assets and suffix in ASSET_EXTENSIONS:
            found.append(p)
            continue
        if (suffix in _BINARY_SUFFIXES
                or suffix in _NOISY_PROBE_EXTS
                or p.name.casefold().endswith(tuple(_NOISY_PROBE_EXTS))
                # F43：macOS 打包残留（.DS_Store / ._ AppleDouble）
                or p.name == ".DS_Store"
                or p.name.startswith(_MAC_RESIDUE_PREFIX)):
            continue
        kind = probe_file_kind(p)
        if kind == "text" or kind in _TEXT_CONTAINER_KINDS:
            found.append(p)
        elif include_assets and kind in ("unity", "serialized", "webfile"):
            found.append(p)
    return sorted(found)
