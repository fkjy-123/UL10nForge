"""TMP 富文本标签语法层（识别通用规则，覆盖全部 TMP 游戏）。

TextMeshPro 富文本标签全集（Unity 官方文档，43 种）：
align/allcaps/alpha/b/br/color/cspace/font/font-weight/gradient/i/indent/
line-height/line-indent/link/lowercase/margin/mark/mspace/nobr/noparse/
page/pos/rotate/s/size/smallcaps/space/sprite/strikethrough/style/sub/
sup/u/uppercase/voffset/width。

识别语义：
- 标签组合串（<color=red>Warning!</color>）是**显示文本**——标签是
  排版标记，正文是可译内容，即使正文短小无空格也应放行
  （"<b>hi</b>" 形态，形态规则会误判为标识符）；
- 纯标签串（<size=30><align=center>，无正文字母）是**结构**——标签
  序列不是语言内容，跳过（模型常回显或乱改标签）；
- <sprite>/<font>/<style>/<gradient>/<material> 的引用名是按名查找
  键（sprite 资产名/字体资产名/样式表名）——作为引用名样本留档，
  不参与正文判定（它们的完整跳过由 class_registry 的 config 类与
  is_tmp_asset_object 负责，此处只负责从显示串中剥离时不误伤）。
"""
from __future__ import annotations

import re
from collections.abc import Iterator

# 标签全集（TMP 官方文档 RichTextSupportedTags；含缩写的全大写变体
# 由 casefold 统一）
_TMP_TAG_NAMES = frozenset({
    "align", "allcaps", "alpha", "b", "br", "color", "cspace", "font",
    "font-weight", "gradient", "i", "indent", "line-height",
    "line-indent", "link", "lowercase", "margin", "mark", "mspace",
    "nobr", "noparse", "page", "pos", "rotate", "s", "size", "smallcaps",
    "space", "sprite", "strikethrough", "style", "sub", "sup", "u",
    "uppercase", "voffset", "width",
})
# 含按名引用值的标签（值 = 资产名/样式表名，翻译会断引用）
_REFERENCE_TAGS = frozenset({"sprite", "font", "style", "gradient",
                             "material"})

# <tag> / </tag> / <tag="v"> / <tag attr="v"> / <#FFFFFF>（颜色缩写形态）
# 只扫描标签名，不做严格属性解析（TMP 语法宽松，嵌套可乱序闭合）
_TAG_SCAN_RE = re.compile(
    r"</?([a-zA-Z][a-zA-Z-]*|#[0-9a-fA-F]{3,8})(?=[\s=/>])")
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def iter_tags(text: str) -> Iterator[tuple[int, int, str, str]]:
    """扫描 TMP 标签：yield (start, end, tag_name, raw_inner)。

    tag_name 为 casefold 后的合法 TMP 标签名（颜色缩写 <#FF0000>
    归为 "color"）；非法 `<...>`（富文本之外的尖括号用法）跳过。
    end 指向 '>' 之后。
    """
    for match in _TAG_SCAN_RE.finditer(text):
        raw_name = match.group(1)
        name = ("color" if raw_name.startswith("#")
                else raw_name.casefold())
        if name not in _TMP_TAG_NAMES:
            continue
        start = match.start()
        end = text.find(">", match.end())
        if end < 0:
            continue
        yield start, end + 1, name, text[match.end() - 1:end]


def strip_tags(text: str) -> str:
    """去掉 TMP 标签后的正文（正文判定/形态判定用）。"""
    out = list(text)
    for start, end, _name, _inner in iter_tags(text):
        for i in range(start, end):
            out[i] = " "
    return "".join(out)


def is_tag_composed(text: str) -> bool:
    """含 ≥1 个合法 TMP 标签且剥离标签后仍有字母正文 → 显示文本形态。"""
    stripped = strip_tags(text)
    return bool(_LETTER_RE.search(stripped)) and any(True for _ in iter_tags(text))


def is_pure_tags(text: str) -> bool:
    """含 ≥1 个合法 TMP 标签且剥离后无字母正文 → 纯标签结构串。"""
    stripped = strip_tags(text)
    return bool(not _LETTER_RE.search(stripped)) and any(True for _ in iter_tags(text))


def referenced_names(text: str) -> frozenset[str]:
    """<sprite>/<font>/<style> 等的引用名（按名查找键，翻译断引用）。

    取标签内第一个引号值（<font="X">）或无引号 token（<sprite=X>）。
    """
    names: set[str] = set()
    for _start, _end, name, inner in iter_tags(text):
        if name not in _REFERENCE_TAGS:
            continue
        # 全部引号值（<sprite="A" name="B"> 两个引用名都取）
        for quote in re.findall(r"""["']([^"']+)["']""", inner):
            value = quote.strip()
            if value:
                names.add(value)
        # <sprite=X> 无引号形态：= 后到空白/属性边界（search 而非
        # match——inner 含标签名残尾 'e=12'）
        bare = re.search(r"=\s*([^\s/]+)", inner)
        if bare:
            value = bare.group(1).strip()
            if value and not value.startswith('"'):
                names.add(value)
    return frozenset(names)
