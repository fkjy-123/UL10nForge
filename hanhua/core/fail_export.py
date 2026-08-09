"""翻译完成后失败记录导出：docs/fail record/「游戏名 fail record 时间戳.txt」。

每次汉化结束把审校中所有失败条目（来源/原文/译文/原因/错误详情）落盘，
按游戏名命名、带时间戳保留历史，方便复盘与补翻。
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

_SEPARATOR = "─" * 64


def _meta_of(row: dict) -> dict:
    raw = row.get("meta", {})
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _format_detail(raw) -> str:
    """错误详情字段：已序列化的 JSON 展开为可读文本，其他原样返回。"""
    if raw is None or raw == "":
        return ""
    if isinstance(raw, dict):
        text = json.dumps(raw, ensure_ascii=False, indent=2)
    else:
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return str(raw)
        text = json.dumps(value, ensure_ascii=False, indent=2) \
            if isinstance(value, (dict, list)) else str(value)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines)


_LOCK_ERROR_MARKERS = (
    "文件被占用", "拒绝访问", "access is denied", "permissionerror",
    "winerror 5", "另一个程序正在使用", "in use by another",
    "being used by another process",
)


def _lock_error_hint(detail: str) -> str:
    """F9：锁定类写回错误（WinError 5）追加可操作提示。

    上次 93 游戏写回审计 7 个失败全因此类：DLL 被游戏进程占用 /
    Windows Defender 扫描窗口 / 杀软隔离。提示给出处理方向。
    """
    lowered = (detail or "").casefold()
    if not any(marker in lowered for marker in _LOCK_ERROR_MARKERS):
        return ""
    return ("文件正被占用导致写回失败。请关闭该游戏（含后台进程）后重试；"
            "若仍有问题，等 Windows Defender/杀毒软件扫描完成后重试，"
            "或将游戏目录加入杀软白名单。")


def export_fail_record(project, out_dir: str | Path, *,
                       error_title: str = "",
                       error_detail: str = "") -> Path | None:
    """导出当前项目的全部失败条目。

    返回写入的文件路径；无失败条目且无附加错误时返回 None。文件名为
    「{游戏名} fail record {yyyy-mm-dd HH-MM-SS}.txt」。

    error_title/error_detail：附加错误段（写回失败/写回未通过验证/翻译出错等
    非条目级失败），保证「所有失败都落盘」。
    """
    store = getattr(project, "store", None)
    entries = (store.get_entries(status="failed")
               if store is not None else [])
    if not entries and not error_title:
        return None
    profile = getattr(project, "profile", None)
    game = (getattr(profile, "game_name", None) or "未命名游戏").strip()
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    target = Path(out_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{game} fail record {stamp}.txt"
    counter = 2
    while path.exists():            # 同一秒内多次导出 → 追加序号不覆盖
        path = target / f"{game} fail record {stamp}-{counter}.txt"
        counter += 1

    blocks = [f"游戏：{game}",
              f"导出时间：{stamp}",
              f"失败条目：{len(entries)} 条", ""]
    if error_title:
        blocks += [_SEPARATOR, f"附加错误：{error_title}"]
        if error_detail:
            blocks.append(f"详情：{error_detail}")
            hint = _lock_error_hint(error_detail)
            if hint:
                blocks.append(f"提示：{hint}")
        blocks.append("")
    for index, row in enumerate(entries, start=1):
        meta = _meta_of(row)
        reasons = meta.get("quality_reasons", [])
        if isinstance(reasons, list):
            reason_text = "、".join(str(r) for r in reasons)
        else:
            reason_text = str(reasons) if reasons else ""
        detail = _format_detail(meta.get("request_error_detail"))
        source = meta.get("source") or row["file_id"]
        blocks += [
            _SEPARATOR,
            f"[{index}] 失败条目",
            f"来源：{source}",
            f"键位：{row.get('key_path', '')}",
            f"原文：{row.get('original', '')}",
            f"译文：{row.get('translation', '') or '（无）'}",
            f"原因：{reason_text or '未知'}",
        ]
        if detail:
            blocks.append(f"详情：{detail}")
        blocks.append("")
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path
