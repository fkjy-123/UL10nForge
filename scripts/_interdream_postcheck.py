# -*- coding: utf-8 -*-
"""游戏闭环终验脚本（文本快照版，2026-08-13）。用完即删。

项目库被 runner 清理（既定行为）——改用 runner 导出的
docs/all record/<游戏>/text/translated.txt（写回最终值）复验：

1. 解析 translated.txt → 写回条目集（写回：已写入）
2. F13 修复后质量门全量复验 → 生成 f13-defect-written-list.md 终版
3. 解析 failed.txt → F13 修复后裁决（判定误杀清单 → analysis 用）

用法：python scripts/_interdream_postcheck.py <游戏名> [defect-file.md]
"""
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GAME = sys.argv[1] if len(sys.argv) > 1 else "interdream"
TXT = REPO / "docs" / "all record" / GAME / "text"
OUT = REPO / "docs" / "all record" / GAME / "fix record"

sys.path.insert(0, str(REPO))
from hanhua.core.models import TextEntry  # noqa: E402
from hanhua.core.quality import validate_translation_quality  # noqa: E402

FIELD_RE = re.compile(
    r"^(来源|键位|对象|原文|译文|置信度|原因|角色|质量评分|翻译评价|"
    r"需要优化|写回|内容)：")
SEP_RE = re.compile(r"^─{10,}$")
NUM_RE = re.compile(r"^\[\d+\] ")


def parse_export(path: Path):
    """解析 runner 导出文件 → [{字段: 值}]。原文/译文可多行。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    items, cur, cur_field = [], None, None
    for ln in lines:
        if SEP_RE.match(ln):
            if cur is not None:
                items.append(cur)
            cur, cur_field = None, None
            continue
        if NUM_RE.match(ln) and "文本" in ln:
            cur = {}
            continue
        m = FIELD_RE.match(ln)
        if m and cur is not None:
            cur_field = m.group(1)
            cur[cur_field] = ln[m.end():].strip()
            continue
        if cur is not None and cur_field in ("原文", "译文"):
            cur[cur_field] += "\n" + ln
    if cur is not None:
        items.append(cur)
    return items


def main():
    print("== 1. 解析 translated.txt ==")
    ok_items = parse_export(TXT / "translated.txt")
    print(f"  成功块: {len(ok_items)}")
    written = [it for it in ok_items if it.get("写回") == "已写入"]
    print(f"  写回已写入: {len(written)}")

    print("\n== 2. F13 修复后质量门复验（translated 终值） ==")
    defects = []
    for it in written:
        key = it.get("键位", "")
        orig, trans = it.get("原文", ""), it.get("译文", "")
        if not trans or trans == orig:
            continue
        entry = TextEntry(file_id="", original=orig, translation=trans,
                          key_path=key, confidence=it.get("置信度", "medium"))
        try:
            res = validate_translation_quality(entry, trans)
            reasons = tuple(r for r in res.reasons
                            if r != "explanatory_prefix")  # 审核反馈残留不计
            if res.reasons and not reasons:
                pass  # 全部是审核反馈残留 → 放行
            if reasons:
                defects.append((key, orig, trans, reasons))
        except Exception as e:  # 防御：单条异常不中断
            print(f"  !! 检查异常 {key}: {e}")
    print(f"  复验拦截: {len(defects)}")

    print("\n== 3. 生成 f13-defect-written-list.md 终版 ==")
    lines = [
        f"# {GAME} F13 修复前已写回缺陷译文清单（终版）",
        "",
        f"> 生成：2026-08-13 · {GAME} 全流程闭环后",
        "> 数据源：runner 导出 text/translated.txt（写回最终值，"
        "项目库已按惯例清理）",
        "> 复验：F13 修复后代码（F13a 对话词对豁免 + F13b 字面 \\n 行首 `* `"
        "保护 + F13c 裸 ^NN 保护）",
        f"> 数量：{len(defects)} 条（写回最终值复验）",
        "> 处置：登记人工重译（本游戏特判，不自动回写）",
        f"> 对照：翻译运行中快照 → 终版 {len(defects)} 条（全量覆盖）",
        "",
        "## 拦截原因分布",
    ]
    for reason, n in Counter(d[3] for d in defects).most_common():
        lines.append(f"- `{reason}`: {n}")
    lines.append("")
    lines.append("## 清单")
    for i, (key, orig, trans, reason) in enumerate(defects, 1):
        lines.append(f"### {i}. {key}  {reason}")
        lines.append(f"- 原文：{orig!r}")
        lines.append(f"- 写回：{trans!r}")
    target = OUT / "f13-defect-written-list.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"  已生成 {target}（{len(defects)} 条）")

    print("\n== 4. failed.txt 复验（判定误杀清单） ==")
    fail_items = parse_export(TXT / "failed.txt")
    print(f"  失败块: {len(fail_items)}")
    false_kill = []
    for it in fail_items:
        orig, trans = it.get("原文", ""), it.get("译文", "")
        if not trans:
            continue
        entry = TextEntry(file_id="", original=orig, translation=trans,
                          key_path=it.get("键位", ""))
        res = validate_translation_quality(entry, trans)
        if not res.reasons:
            false_kill.append(it.get("键位", ""))
    print(f"  F13 后放行（判定误杀）: {len(false_kill)}")
    if false_kill:
        print("  键位：" + ", ".join(false_kill[:10]))
    # 写入 analysis 用参考
    (OUT / "f13-false-kill-final.txt").write_text(
        "\n".join(false_kill) or "（无）", encoding="utf-8")


if __name__ == "__main__":
    main()
