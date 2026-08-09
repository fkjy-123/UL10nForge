"""从已验译文构建 BMFont 字符语料并严格验证字体描述器。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shlex
import struct
import zlib

from hanhua.core.models import TextEntry
from hanhua.core.tooling.manifest import ToolSpec
from hanhua.core.tooling.runner import IsolatedToolRunner, ToolRunResult


class BmFontValidationError(ValueError):
    pass


@dataclass(frozen=True)
class BmFontArtifact:
    descriptor: Path
    pages: tuple[Path, ...]
    characters: frozenset[int]
    width: int
    height: int
    unavailable: frozenset[int] = frozenset()


_BASE_CHARS = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
    "，。！？：；、（）【】《》“”‘’…—·+-/%.:,!?_()[]{}<>#@&*='\"\uFFFD"
)
_MAX_ATLAS_PIXELS = 64 * 1024 * 1024
_MAX_PAGES = 16


def _ttf_family_name(path: Path) -> str:
    raw = path.read_bytes()
    try:
        table_count = struct.unpack_from(">H", raw, 4)[0]
        name_offset = None
        for index in range(table_count):
            pos = 12 + index * 16
            tag, _checksum, offset, length = struct.unpack_from(">4sIII", raw, pos)
            if tag == b"name" and offset + length <= len(raw):
                name_offset = offset
                break
        if name_offset is None:
            return path.stem
        _format, count, strings_offset = struct.unpack_from(">HHH", raw, name_offset)
        candidates = []
        for index in range(count):
            pos = name_offset + 6 + index * 12
            platform, encoding, language, name_id, length, offset = struct.unpack_from(
                ">HHHHHH", raw, pos)
            if name_id != 1:
                continue
            start = name_offset + strings_offset + offset
            value_raw = raw[start:start + length]
            codec = "utf-16-be" if platform in {0, 3} else "latin-1"
            value = value_raw.decode(codec).strip("\x00 ")
            if value:
                priority = (platform == 3, language in {0x0409, 0x0804}, encoding == 10)
                candidates.append((priority, value))
        return max(candidates)[1] if candidates else path.stem
    except (IndexError, struct.error, UnicodeError):
        return path.stem


def build_corpus(entries) -> str:
    characters = set(_BASE_CHARS)
    for item in entries:
        if isinstance(item, TextEntry):
            if (item.status != "translated" or not item.translation
                    or item.meta.get("quality_passed") is not True):
                continue
            role = str(item.meta.get("role", "display"))
            confidence = str(item.meta.get("confidence", item.confidence))
            if role in {"structural", "code", "key"}:
                continue
            if (confidence == "low"
                    and item.meta.get("confidence_promoted") is not True):
                continue
            value = item.translation
        else:
            raise TypeError("BMFont 语料只接受含质量门证据的 TextEntry")
        characters.update(value)
    characters.discard("\x00")
    return "".join(sorted(characters, key=ord))


def write_bmfont_config(path: str | Path, font_file: str | Path, *,
                        width: int = 2048, height: int = 2048,
                        font_size: int = 36) -> Path:
    destination = Path(path)
    font = Path(font_file).resolve()
    if not font.is_file():
        raise BmFontValidationError(f"字体文件不存在：{font}")
    if width < 128 or height < 128 or width > 8192 or height > 8192:
        raise BmFontValidationError("atlas 尺寸超出 128..8192")
    lines = [
        "fileVersion=1", f"fontName={_ttf_family_name(font)}", f"fontFile={font}", "charSet=0",
        f"fontSize={font_size}", "aa=1", "scaleH=100", "useSmoothing=1",
        "isBold=0", "isItalic=0", "useUnicode=1", "disableBoxChars=1",
        "outputInvalidCharGlyph=0", "dontIncludeKerningPairs=1", "useHinting=1",
        "renderFromOutline=0", "useClearType=0", "paddingDown=2", "paddingUp=2",
        "paddingRight=2", "paddingLeft=2", "spacingHoriz=1", "spacingVert=1",
        f"outWidth={width}", f"outHeight={height}", "outBitDepth=32",
        "fontDescFormat=0", "fourChnlPacked=0", "textureFormat=png",
        "textureCompression=0", "alphaChnl=0", "redChnl=4", "greenChnl=4",
        "blueChnl=4", "invA=0", "invR=0", "invG=0", "invB=0",
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def _fields(line: str) -> tuple[str, dict[str, str]]:
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError as exc:
        raise BmFontValidationError(".fnt 行引号无效") from exc
    if not tokens:
        return "", {}
    values = {}
    for token in tokens[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            values[key] = value
    return tokens[0], values


def _png_dimensions(raw: bytes) -> tuple[int, int]:
    if len(raw) < 33 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise BmFontValidationError("atlas page 不是有效 PNG")
    pos = 8
    width = height = bit_depth = color_type = interlace = None
    idat = bytearray()
    saw_iend = False
    while pos + 12 <= len(raw):
        length = struct.unpack_from(">I", raw, pos)[0]
        if length > 256 * 1024 * 1024 or pos + 12 + length > len(raw):
            raise BmFontValidationError("PNG chunk 边界无效")
        kind = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + length]
        expected_crc = struct.unpack_from(">I", raw, pos + 8 + length)[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != expected_crc:
            raise BmFontValidationError("PNG chunk CRC 无效")
        if kind == b"IHDR":
            if width is not None or length != 13:
                raise BmFontValidationError("PNG IHDR 无效")
            width, height, bit_depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", data))
            if not width or not height or compression != 0 or filtering != 0 or interlace != 0:
                raise BmFontValidationError("PNG IHDR 参数不受支持")
        elif kind == b"IDAT":
            idat.extend(data)
        elif kind == b"IEND":
            if length != 0:
                raise BmFontValidationError("PNG IEND 无效")
            saw_iend = True
            pos += 12
            break
        pos += 12 + length
    if width is None or not idat or not saw_iend or pos != len(raw):
        raise BmFontValidationError("PNG 必需 chunk 缺失")
    if width > 8192 or height > 8192 or width * height > _MAX_ATLAS_PIXELS:
        raise BmFontValidationError("PNG atlas 像素超限")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None or bit_depth not in {1, 2, 4, 8, 16}:
        raise BmFontValidationError("PNG 色彩格式不受支持")
    row_bytes = (width * channels * bit_depth + 7) // 8
    expected_size = (row_bytes + 1) * height
    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(bytes(idat), expected_size + 1)
    except zlib.error as exc:
        raise BmFontValidationError("PNG IDAT 无法解压") from exc
    if (len(decoded) != expected_size or not decompressor.eof
            or decompressor.unconsumed_tail):
        raise BmFontValidationError("PNG IDAT 像素长度无效")
    return width, height


def validate_fnt(path: str | Path, required: str, *,
                 expected_width: int | None = None,
                 expected_height: int | None = None) -> BmFontArtifact:
    descriptor = Path(path).resolve()
    if (not descriptor.is_file() or descriptor.stat().st_size == 0
            or descriptor.stat().st_size > 64 * 1024 * 1024):
        raise BmFontValidationError(".fnt 缺失或过大")
    try:
        lines = descriptor.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise BmFontValidationError(".fnt 不是有效 UTF-8 文本描述器") from exc
    pages: dict[int, Path] = {}
    characters: set[int] = set()
    character_records = 0
    char_pages: list[int] = []
    width = height = declared_pages = None
    declared_chars = None
    for line in lines:
        kind, fields = _fields(line)
        try:
            if kind == "common":
                width = int(fields["scaleW"])
                height = int(fields["scaleH"])
                declared_pages = int(fields["pages"])
            elif kind == "page":
                page_id = int(fields["id"])
                filename = fields["file"]
                if Path(filename).name != filename:
                    raise BmFontValidationError("page 文件名包含路径")
                pages[page_id] = descriptor.parent / filename
            elif kind == "char":
                character = int(fields["id"])
                if character < 0 or character > 0x10FFFF:
                    raise BmFontValidationError("char id 超出 Unicode")
                if character in characters:
                    raise BmFontValidationError(f"重复 char id：{character}")
                characters.add(character)
                character_records += 1
                char_pages.append(int(fields.get("page", "0")))
            elif kind == "chars":
                declared_chars = int(fields["count"])
        except (KeyError, ValueError) as exc:
            raise BmFontValidationError(f".fnt {kind} 字段无效") from exc
    if (width is None or height is None or declared_pages is None
            or width < 1 or height < 1 or width > 8192 or height > 8192
            or declared_pages < 1 or declared_pages > _MAX_PAGES):
        preview = descriptor.read_text(encoding="utf-8-sig", errors="replace")[:1000]
        raise BmFontValidationError(
            f".fnt common 声明缺失或无效（size={descriptor.stat().st_size}, head={preview!r}）")
    if ((expected_width is not None and width != expected_width)
            or (expected_height is not None and height != expected_height)):
        raise BmFontValidationError(
            f"atlas 与请求尺寸不符：{width}x{height}")
    if width * height * declared_pages > _MAX_ATLAS_PIXELS:
        raise BmFontValidationError("atlas 总像素超限")
    if set(pages) != set(range(declared_pages)):
        raise BmFontValidationError(".fnt page id/count 不一致")
    if declared_chars is None or declared_chars != character_records:
        raise BmFontValidationError(".fnt chars count 与 char 记录不一致")
    resolved_pages = []
    for page_id in range(declared_pages):
        page = pages[page_id]
        if page.is_symlink() or not page.is_file() or page.stat().st_size == 0:
            raise BmFontValidationError(f"atlas page 缺失或为空：{page.name}")
        raw = page.read_bytes()
        try:
            png_width, png_height = _png_dimensions(raw)
        except BmFontValidationError as exc:
            raise BmFontValidationError(f"{exc}：{page.name}") from exc
        if (png_width, png_height) != (width, height):
            raise BmFontValidationError(
                f"atlas page 尺寸不符：{page.name}={png_width}x{png_height}")
        resolved_pages.append(page.resolve())
    if any(page_id not in pages for page_id in char_pages):
        raise BmFontValidationError("char 引用了不存在的 page")
    missing = {ord(char) for char in required} - characters
    explicitly_unavailable = missing & {0xFFFD}
    blocking_missing = sorted(missing - explicitly_unavailable)
    if blocking_missing:
        codes = ", ".join(f"U+{code:04X}" for code in blocking_missing[:20])
        raise BmFontValidationError(f"atlas 缺少字符：{codes}")
    return BmFontArtifact(descriptor, tuple(resolved_pages),
                          frozenset(characters), width, height,
                          frozenset(explicitly_unavailable))


def run_bmfont(
    runner: IsolatedToolRunner,
    spec: ToolSpec,
    font_file: str | Path,
    entries,
    *,
    width: int = 2048,
    height: int = 2048,
    timeout_s: float = 180,
) -> tuple[ToolRunResult, BmFontArtifact]:
    corpus = build_corpus(entries)
    corpus_sha = hashlib.sha256(corpus.encode("utf-8")).hexdigest()

    def prepare(job, inputs, _entry):
        (job / "corpus.txt").write_text(corpus, encoding="utf-8-sig")
        write_bmfont_config(job / "font.bmfc", inputs["font.ttf"],
                            width=width, height=height)

    def command(entry, _inputs, output):
        job = output.parent
        return [str(entry), "-c", str(job / "font.bmfc"),
                "-o", str(output / "font.fnt"), "-t", str(job / "corpus.txt")]

    def validate(output):
        artifact = validate_fnt(
            output / "font.fnt", corpus,
            expected_width=width, expected_height=height)
        return [artifact.descriptor, *artifact.pages]

    result = runner.run(
        spec, {"font.ttf": font_file},
        {"corpus_sha256": corpus_sha, "width": width, "height": height},
        prepare=prepare, command=command, validate=validate, timeout_s=timeout_s,
    )
    artifact = validate_fnt(
        result.artifact_dir / "font.fnt", corpus,
        expected_width=width, expected_height=height)
    return result, artifact
