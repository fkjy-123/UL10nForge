"""检查 TTF 字体的字符覆盖：完整解析 cmap（format 4 + 12），输出多区段覆盖报告。

用法: python scripts/ttf_cjk_check.py <font.ttf> [font2.ttf ...]

旧版只收集 CJK 相关段（拉丁/假名等一律报 0%），无法判定字体是否「缺拉丁」——
而 legacy Font 替换后英文、数字、符号由目标 TTF 渲染，缺拉丁 = 全部口口。
"""
from __future__ import annotations
import struct
import sys
from pathlib import Path

# 常用汉字样本（GB2312 一级字 + 常用二级，覆盖 UI 常见词）
_CJK_SAMPLE = "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严龙飞"
_SAMPLE_CODES = [ord(c) for c in _CJK_SAMPLE]

# 覆盖区段（判定 legacy 替换后哪些字符会消失）：
# (名称, 起, 止, 期望) —— 期望为 True 表示游戏文本常用、必须覆盖
_RANGES = [
    ("ASCII",            0x0020, 0x007E, True),
    ("Latin-1 补充",      0x00A0, 0x00FF, True),
    ("Latin-A 扩展",      0x0100, 0x017F, False),
    ("希腊",              0x0370, 0x03FF, False),
    ("西里尔",            0x0400, 0x04FF, False),
    ("通用标点",          0x2000, 0x206F, True),
    ("箭头",              0x2190, 0x21FF, False),
    ("数学符号",          0x2200, 0x22FF, False),
    ("CJK 符号标点",      0x3000, 0x303F, True),
    ("平假名",            0x3040, 0x309F, False),
    ("片假名",            0x30A0, 0x30FF, False),
    ("谚文字母",          0x1100, 0x11FF, False),
    ("谚文音节",          0xAC00, 0xD7AF, False),
    ("CJK 基本区",        0x4E00, 0x9FFF, True),
    ("CJK 扩展A",         0x3400, 0x4DBF, False),
    ("全角",              0xFF00, 0xFFEF, True),
    ("阿拉伯",            0x0600, 0x06FF, False),
    ("Emoji",             0x1F300, 0x1F5FF, False),
]


def parse_cmap_codepoints(data: bytes) -> set[int]:
    """完整解析 TTF/OTF cmap（format 4 + 12），返回全部映射码点。

    format 4 使用完整段逻辑（idDelta/idRangeOffset 查真实 glyphId，跳过
    glyphId==0 的未映射码点）；format 12 直接用 groups。
    """
    if len(data) < 4 or data[:4] not in (b"\x00\x01\x00\x00", b"OTTO",
                                         b"true", b"ttcf"):
        return set()
    if data[:4] == b"ttcf":
        return set()  # TTC 集合：仅处理首个字体
    try:
        num_tables = struct.unpack(">H", data[4:6])[0]
        tables: dict[str, int] = {}
        for i in range(num_tables):
            off = 12 + i * 16
            if off + 16 > len(data):
                return set()
            tag = data[off:off + 4].decode("latin1")
            toffset = struct.unpack(">I", data[off + 8:off + 12])[0]
            tables[tag] = toffset
        cmap_off = tables.get("cmap")
        if cmap_off is None or cmap_off + 4 > len(data):
            return set()
        num_sub = struct.unpack(">H", data[cmap_off + 2:cmap_off + 4])[0]
        subs: list[tuple[int, int, int]] = []  # (platform, encoding, offset)
        for i in range(num_sub):
            off = cmap_off + 4 + i * 8
            if off + 8 > len(data):
                break
            platform, encoding, sub_off = struct.unpack(">HHI", data[off:off + 8])
            subs.append((platform, encoding, cmap_off + sub_off))
        codepoints: set[int] = set()

        def parse_fmt4(sub_off: int) -> set[int]:
            out: set[int] = set()
            if sub_off + 16 > len(data):
                return out
            length = struct.unpack(">H", data[sub_off + 2:sub_off + 4])[0]
            seg_count_x2 = struct.unpack(
                ">H", data[sub_off + 6:sub_off + 8])[0]
            seg_count = seg_count_x2 // 2
            end_off = sub_off + 14
            start_off = end_off + seg_count_x2 + 2
            delta_off = start_off + seg_count_x2
            ro_off = delta_off + seg_count_x2
            if ro_off + seg_count_x2 > len(data):
                return out
            glyph_ids = []
            for seg in range(seg_count):
                end = struct.unpack(">H", data[end_off + seg * 2:end_off + seg * 2 + 2])[0]
                start = struct.unpack(">H", data[start_off + seg * 2:start_off + seg * 2 + 2])[0]
                delta = struct.unpack(">h", data[delta_off + seg * 2:delta_off + seg * 2 + 2])[0]
                ro = struct.unpack(">H", data[ro_off + seg * 2:ro_off + seg * 2 + 2])[0]
                if start > end:
                    continue
                if ro == 0:
                    # 连续映射：glyphId = (codepoint + delta) & 0xFFFF
                    if delta == 0:
                        out.update(range(start, end + 1))
                    else:
                        for cp in range(start, end + 1):
                            if (cp + delta) & 0xFFFF:
                                out.add(cp)
                    continue
                # 分段映射：idRangeOffset 指向 glyphId 数组（相对该字段地址）
                array_base = ro_off + seg * 2
                for cp in range(start, end + 1):
                    addr = array_base + ro + (cp - start) * 2
                    if addr + 2 > len(data):
                        break
                    gid = struct.unpack(">H", data[addr:addr + 2])[0]
                    if gid:
                        out.add(cp)
            return out

        def parse_fmt12(sub_off: int) -> set[int]:
            out: set[int] = set()
            if sub_off + 16 > len(data):
                return out
            n_groups = struct.unpack(">I", data[sub_off + 12:sub_off + 16])[0]
            for g in range(n_groups):
                goff = sub_off + 16 + g * 12
                if goff + 12 > len(data):
                    break
                s, cnt, _d = struct.unpack(">III", data[goff:goff + 12])
                e = s + cnt - 1
                out.update(range(s, e + 1))
            return out

        for platform, encoding, sub_off in subs:
            if sub_off + 2 > len(data):
                continue
            fmt = struct.unpack(">H", data[sub_off:sub_off + 2])[0]
            if fmt == 4:
                codepoints |= parse_fmt4(sub_off)
            elif fmt == 12:
                codepoints |= parse_fmt12(sub_off)
        return codepoints
    except (struct.error, IndexError):
        return set()


def check_font(path: Path) -> dict:
    data = path.read_bytes()
    cps = parse_cmap_codepoints(data)
    covered = sum(1 for c in _SAMPLE_CODES if c in cps)
    ranges = {}
    for name, lo, hi, required in _RANGES:
        have = sum(1 for c in range(lo, hi + 1) if c in cps)
        total = hi - lo + 1
        ranges[name] = {
            "have": have, "total": total,
            "pct": round(have / total * 100, 1),
            "required": required,
            "ok": have >= int(total * 0.95) if required else True,
        }
    missing_required = [n for n, r in ranges.items() if r["required"] and not r["ok"]]
    return {
        "file": path.name,
        "size_mb": round(len(data) / 1048576, 1),
        "codepoints": len(cps),
        "cjk_sample_covered": covered,
        "cjk_sample_total": len(_SAMPLE_CODES),
        "ranges": ranges,
        "missing_required": missing_required,
        "usable": not missing_required and covered == len(_SAMPLE_CODES),
    }


if __name__ == "__main__":
    import json
    results = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_file():
            results.append(check_font(p))
    print(json.dumps(results, ensure_ascii=False, indent=1))
