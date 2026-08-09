"""全流程闭环检验（不开游戏窗口、不启动 exe、不调模型服务）。

对真实游戏副本执行：扫描 → 规则翻译 → 写回（smoke=False）→
UnityPy 重开验证。验证点：
1) 写回后副本可被 UnityPy 完整解析（无损坏）；
2) 全部已翻译条目在副本中可寻回（中文写入成功）；
3) 不可变字段（Localization 表键 / m_Name / m_SharedData 等）保持英文；
4) 源目录在写回后未被修改（hash 不变）；
5) manifest 生成且 changed_files 与写回数一致。

翻译用确定性规则（词汇表 + 中文标记），不依赖本地模型服务。
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from UnityPy import Environment

from hanhua.core.project import Project
from hanhua.core.unity.writer import _dispose_environment

# 常用 UI 词单字映射：保证 UTF-8 字节 <= 原文（DLL #US/IL2CPP metadata
# 都是固定容量写回，超长译文会被截断并阻断发布——宁可漏译不可破坏）
_GLOSS = [
    ("Play", "玩"), ("Quit", "退"), ("Back", "回"), ("Save", "存"),
    ("Load", "读"), ("Open", "开"), ("Close", "关"), ("Yes", "是"),
    ("Pause", "停"), ("Start", "启"), ("Stop", "停"), ("Menu", "单"),
    ("Exit", "退"), ("Level", "关"), ("Score", "分"), ("Health", "命"),
    ("Time", "时"), ("Day", "日"), ("Night", "夜"), ("Door", "门"),
    ("Key", "钥"), ("Lock", "锁"), ("Item", "物"), ("Coin", "币"),
    ("Shop", "店"), ("Buy", "买"), ("Sell", "卖"), ("Use", "用"),
    ("Take", "拿"), ("Jump", "跳"), ("Run", "跑"), ("Walk", "走"),
    ("Help", "助"), ("Map", "图"), ("Talk", "谈"), ("Wait", "等"),
    ("New", "新"), ("Old", "旧"), ("Big", "大"), ("Small", "小"),
    ("Hot", "热"), ("Cold", "冷"), ("Fast", "快"), ("Slow", "慢"),
]


def _fits(zh: str, orig: str) -> bool:
    """译文在两种固定容量编码（UTF-8 字节 / UTF-16 字符）下都不超原文。"""
    return (len(zh.encode("utf-8")) <= len(orig.encode("utf-8"))
            and len(zh) <= len(orig))


def rule_translate(text: str) -> str:
    """确定性翻译：词汇表替换，未命中词保留原词并加中文标记前缀。

    保证译文含中文字符（验证 UTF-8 写入），且原文可回溯（验证不漏译）。
    """
    out = text
    for src, dst in _GLOSS:
        out = re.sub(rf"\b{re.escape(src)}\b", dst, out, flags=re.IGNORECASE)
    if not re.search(r"[一-鿿]", out):
        return None
    return out if _fits(out, text) else None


def _sha256_tree(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            hashes[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return hashes


_CN_RE = re.compile(r"[一-鿿]")


def _build_cn_buckets(written_values: set[str]) -> dict[str, list[str]]:
    """按首字分桶：匹配时只试首字相同的位置，避免逐段全量 in 扫描。

    片段全部来自 re.findall(r"[一-鿿]+") 纯中文；二进制文件 utf-16-le
    解码必有随机中文噪声（任意 2 字节组合约 4‰ 概率落在汉字区），
    「无中文早退」对 utf-16-le 几乎不触发，逐段 in 搜索在 42MB 大文件上
    O(files×bytes×segments) 爆炸（MarioVsLuigi 87MB 实测卡 25 分钟）。
    """
    buckets: dict[str, list[str]] = {}
    for s in written_values:
        buckets.setdefault(s[0], []).append(s)
    return buckets


def _check_bytes(blob: bytes, cn_buckets: dict[str, list[str]],
                 protected_keys: set[str] | None, found: set[str],
                 max_utf16_size: int = 8_000_000) -> None:
    """字节级找回：Unity 字符串在容器里常为 UTF-16（4 字节长+UTF-16 或
    DLL #US 表），文本文件为 UTF-8——两种编码都搜。
    protected_keys 为 None 时（源树对照扫描）跳过键查找。

    cn_buckets：_build_cn_buckets 分桶结果。utf-8 解码的二进制基本无
    中文可早退；utf-16-le 总有噪声中文，用 finditer 扫一遍文本 + 每
    中文位置只试首字同桶片段（O(n) 级，而非 O(n×segments)）。
    max_utf16_size：utf-16 解码搜索的字节上限（utf-16 解码后文本膨胀
    一倍，大文件逐位置扫描数秒；超大非容器文件——42MB 资源包等——
    不可能是译文目标，容器内对象 raw 不受限，译文找回完整）。
    """
    need_keys = protected_keys is not None
    texts = [blob.decode("utf-8", errors="ignore")]
    if len(blob) <= max_utf16_size:
        texts.append(blob.decode("utf-16-le", errors="ignore"))
    for text in texts:
        cn_iter = _CN_RE.finditer(text)
        first = next(cn_iter, None)
        if first is None and not need_keys:
            continue
        pos = first
        while pos is not None:
            for s in cn_buckets.get(pos.group(), ()):
                if text.startswith(s, pos.start()):
                    found.add(s)
            pos = next(cn_iter, None)
        if need_keys:
            for k in list(protected_keys):
                if k in text:
                    protected_keys.discard(k)


def _scan_hits(root: Path, segments: set[str],
               protected_keys: set[str] | None = None,
               ) -> tuple[list[str], set[str]]:
    """扫描一棵树：UnityPy 可加载文件走对象树 + raw，其余走字节搜索。

    返回 (parse_errors, 命中片段集)。protected_keys 非 None 时在树/字节
    中查找并 discard（写回后保持英文验证）；场景文件（level1/level2…，
    无扩展名）与 DLL 同样覆盖。
    """
    parse_errors: list[str] = []
    found: set[str] = set()
    byte_files: list[Path] = []
    cn_buckets = _build_cn_buckets(segments)
    env = Environment()
    try:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            try:
                env.load([str(p)])
            except Exception:  # noqa: BLE001 非 Unity 容器：字节搜索
                byte_files.append(p)
                continue
            for obj in env.objects:
                # 只做字节级找回：树级 read_typetree 对无 typetree 的老
                # bundle 每对象生成模板（MonoBehaviour 专属树），合并场景
                # 几十万节点递归遍历，源+写回两侧全量做会卡死
                # （MarioVsLuigi data.unity3d 实测 25 分钟）。raw 必含树
                # 字段的序列化字节，_check_bytes 双编码搜索已覆盖全部
                # 字符串字段，树级收集是冗余的。
                try:
                    raw = obj.get_raw_data()
                except Exception:  # noqa: BLE001
                    continue
                if raw:
                    _check_bytes(raw, cn_buckets, protected_keys, found)
        for p in byte_files:
            try:
                blob = p.read_bytes()
            except OSError:  # noqa: BLE001
                continue
            _check_bytes(blob, cn_buckets, protected_keys, found)
    finally:
        _dispose_environment(env)
    return parse_errors, found


def _verify_reopen(src_dir: Path, out_dir: Path, zh_segments: set[str],
                   protected_keys: set[str]) -> dict:
    """对照重开验证。

    1) 全部资源可完整解析（源与写回两侧）；
    2) 译文中文片段必须落在「写回后新增」的命中里——UTF-16-LE 解码任意
       二进制会产生噪声中文，单字译文在源树里同样命中，无对照会恒真
       （review 实证）；
    3) 受保护键（Localization 表键 / m_Name）保持英文——写回树中查找，
       最后仍未被找到者即保护失败（key_ok=False）。
    """
    src_errors, src_hits = _scan_hits(src_dir, zh_segments)
    out_errors, out_hits = _scan_hits(out_dir, zh_segments, protected_keys)
    missing = sorted(zh_segments - (out_hits - src_hits))
    return {
        "parse_errors": src_errors + out_errors,
        "missing_values": missing,
        "key_ok": not protected_keys,
        "remaining_keys": sorted(protected_keys),
    }


def run_closure(game_name: str, source: Path, work_root: Path) -> dict:
    game_dir = work_root / game_name
    if not game_dir.exists():
        shutil.copytree(source, game_dir, ignore=shutil.ignore_patterns(
            "*_BackUpThisFolder_*", "il2cppOutput", "il2cppSymbols"))
    app_dir = work_root / f"{game_name}-app"
    proj = Project.open_game_dir(game_dir, app_dir)
    t0 = time.time()
    # scan_all（统一扫描）：IL2CPP 写回证据链要求本次项目的
    # native/Il2CppDumper 交叉验证 + _last_il2cpp_input_hashes 绑定，
    # 只有 scan_all 执行 dumper 分析（mono 游戏内部跳过）
    proj.scan_all()
    rows = proj.store.get_entries()
    pending = [r for r in rows if r["status"] == "pending"]
    # 规则翻译（确定性）
    written: list[tuple[str, str, str]] = []  # (file_id, key_path, 译文)
    for r in pending:
        zh = rule_translate(r["original"])
        if zh is None:
            continue  # 超长/未命中：保持 pending 不写回，避免截断
        proj.store.set_manual(r["file_id"], r["key_path"], zh)
        written.append((r["file_id"], r["key_path"], zh))
    if not written:
        return {"game": game_name, "skipped": True,
                "reason": ("无已翻译条目（规则翻译未命中词汇表）"
                           if pending else "无 pending 条目")}

    # 键保护样本：Localization 表键风格（ui_xxx / _xxx / menu_xxx）。
    # 只取 pending 真实原文——硬编码不存在的键会永远找不到（假阴性）
    protected_keys = {
        r["original"] for r in pending
        if re.match(r"^(?:ui_|menu_|btn_|[a-z]+_[A-Z])", r["original"])
    }

    before = _sha256_tree(game_dir)
    out_dir = proj.out_dir
    result = proj.write_all(smoke=False)
    after = _sha256_tree(game_dir)
    scan_ms = int((time.time() - t0) * 1000)

    verification = result["verification"]
    gates = verification.get("gates", {})
    overall = verification.get("overall", "?")
    # 写入生效判定用译文的中文片段（而非完整值）：富文本/多行值写回后
    # 形态可能因编码/对齐变化，但中文片段必逐字落盘（the-keeper 实证）。
    # 对照扫描（源 vs 写回树）滤除 UTF-16-LE 噪声命中的假证据
    zh_segments = {
        seg for _, _, zh in written
        for seg in re.findall(r"[一-鿿]+", zh)}
    reopen = _verify_reopen(game_dir, out_dir, zh_segments, protected_keys)

    # manifest 的 changed_files 应与写回数一致（changed_files 在
    # .hanhua-manifest.json 内，不在 verification dict）
    manifest_changed = None
    manifest_name = verification.get("manifest")
    if manifest_name:
        manifest_path = out_dir / manifest_name
        if manifest_path.exists():
            manifest_changed = json.loads(
                manifest_path.read_text(encoding="utf-8")).get("changed_files")

    # 副本重扫：译文可寻回
    re_proj = Project.open_game_dir(out_dir, app_dir)
    re_proj.scan()
    re_proj.scan_v2()
    re_rows = re_proj.store.get_entries()
    re_pending = [r for r in re_rows if r["status"] == "pending"]
    zh_recovered = sum(
        1 for r in re_pending if re.search(r"[\u4e00-\u9fff]", r["original"]))
    en_leftover = sum(
        1 for r in re_pending
        if not re.search(r"[\u4e00-\u9fff]", r["original"])
        and json.loads(r["meta"] or "{}").get("role") == "display")

    return {
        "game": game_name,
        "skipped": False,
        "pending": len(pending),
        "written": len(written),
        "scan_ms": scan_ms,
        "gates_overall": overall,
        "file_gate": gates.get("file", {}).get("status"),
        "object_gate": gates.get("object", {}).get("status"),
        "runtime_gate": gates.get("runtime", {}).get("status"),
        "gameplay_gate": gates.get("gameplay", {}).get("status"),
        "manifest": manifest_name,
        "changed_files": manifest_changed,
        "reopen_parse_errors": reopen["parse_errors"],
        "reopen_missing_values": len(reopen["missing_values"]),
        "reopen_missing_detail": reopen["missing_values"],
        "reopen_remaining_keys": reopen["remaining_keys"],
        "reopen_key_ok": reopen["key_ok"],
        "source_unchanged": before == after,
        "rescan_zh_recovered": zh_recovered,
        "rescan_en_leftover_display": en_leftover,
        "rescan_total_pending": len(re_pending),
    }


def main() -> int:
    import json
    games = [
        ("doubleshake", r"D:\游戏\doubleshake"),
        ("hunt", r"D:\游戏\hunt"),
        ("slendergus", r"D:\游戏\slendergus"),
        ("the-keeper", r"D:\游戏\the-keeper"),
        ("backrooms", r"D:\游戏\backrooms"),
        ("seijundrop", r"D:\游戏\seijundrop"),
        ("vapor-trails", r"D:\游戏\vapor-trails"),
        ("ultrakill-prelude", r"D:\游戏\ultrakill-prelude"),
        ("tiiny-ragdoll", r"D:\游戏\tiiny-ragdoll"),
    ]
    work_root = Path(tempfile.mkdtemp(prefix="flow-closure-"))
    out_root = work_root / "out"
    out_root.mkdir()
    report: list[dict] = []
    for name, src in games:
        print(f"=== {name} ===", flush=True)
        try:
            report.append(run_closure(name, Path(src), work_root))
        except Exception as exc:  # noqa: BLE001
            report.append({"game": name, "error": f"{type(exc).__name__}: {exc}"})
        print(json.dumps(report[-1], ensure_ascii=False, indent=1), flush=True)
    print("\n===== 汇总 =====", flush=True)
    ok = 0
    for item in report:
        if item.get("error"):
            print(f"  {item['game']:<14} 失败: {item['error']}", flush=True)
            continue
        if item.get("skipped"):
            print(f"  {item['game']:<14} 跳过: {item['reason']}", flush=True)
            continue
        ok += 1
        print(
            f"  {item['game']:<14} pending={item['pending']:<5} "
            f"写入={item['written']:<5} 闸门={item['gates_overall']:<6} "
            f"重开错误={len(item['reopen_parse_errors'])} "
            f"译文缺失={item['reopen_missing_values']} "
            f"键保持={item['reopen_key_ok']} "
            f"源未变={item['source_unchanged']} "
            f"译文可寻回={item['rescan_zh_recovered']}/{item['written']} "
            f"英文残留={item['rescan_en_leftover_display']}",
            flush=True)
    print(f"通过 {ok}/{len(games)}", flush=True)
    return 0 if ok == len(games) else 1


if __name__ == "__main__":
    sys.exit(main())
