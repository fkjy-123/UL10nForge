# -*- coding: utf-8 -*-
"""GitHub Release 发布（2026-08-15）：用 git 凭据获取 token，
创建 v0.30.0-beta release 并上传 4 个分卷。

用法：
    python scripts/_publish_release.py            # 创建 release + 上传全部分卷
    python scripts/_publish_release.py --notes-only   # 只创建/更新 release 文案
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
REPO = "mingminghh611/UL10nForge"
TAG = "v0.30.0-beta"
RELEASE_NAME = "UL10nForge 0.30.0-beta — 首个公开测试版"

BODY = """# UL10nForge 0.30.0-beta — 首个公开测试版

一个**完全离线**的 Unity 游戏汉化工作台：识别 → 翻译 → 审校 → 写回全流程，每一步都有确定性检查与证据留档。

> 本项目由一位编程与游戏汉化的**新手**借助 **AI 辅助**独立开发——这是第一个公开测试版，问题在所难免，欢迎反馈。

## ✨ 核心功能

- **纯本地离线**：四模型（1.8B 翻译 + 4B 语义审核 + 0.6B 语境重排 + 0.6B 向量检索）随包运行，文本不上传任何服务器
- **规则护航**：每条译文过 20+ 项确定性质量门——占位符、富文本、数字、按键名保护，翻译不翻坏
- **四级语义审核**：PASS / MINOR / MAJOR / CRITICAL，错误带理由自动重译
- **安全写回**：四态闸门 + 重开比对验证；对象名/事件绑定/逻辑键多层保护
- **越用越熟**：跨游戏经验记忆 + 术语库 + 语境库自动沉淀

## 📦 安装使用

1. 下载 **4 个分卷**（.7z.001 ~ .7z.004，GitHub 单文件 2GB 限制）到同一目录
2. 用 7-Zip（www.7-zip.org）解压 `.7z.001`，得到完整应用目录（约 7.5GB，内置 Python 与模型，零配置）
3. 解压到纯英文路径，双击 `启动UL10nForge.bat`
4. 拖入游戏文件夹，按「概览 → 翻译 → 审校 → 写回」走完流程

硬件要求：CUDA 显卡 8GB+ 显存推荐（或大内存纯 CPU 模式）。

> 网盘下载见 README（国内下载更快）。

## 🧪 测试版已知问题（如实告知）

- **识别不全**：拼接/加密/服务器下发/贴图内文字无法识别，未知形态可能漏识别
- **翻译质量不高**：1.8B 小模型，复杂句/文学性表达有限，需人工审校兜底
- **写回可能有 bug**：按键 UI 失灵、游戏卡住等逻辑性问题可能发生——**建议写回前备份原游戏文件**
- 不做实机测试，UI 溢出、字体渲染等运行期问题可能漏检

遇到问题请带复现步骤提 Issue，或加入交流群：**931708916**。

## 📄 文件校验

分卷（SHA256）：

```text
UL10nForge-0.30.0-beta.7z.001  624475a282cdbbc95c47acc7b21bee4d9d0a7bc8ceaf719122b9ec3170c6827a
UL10nForge-0.30.0-beta.7z.002  5ae1df292b0f2c95665ace3d7e637e300e9aefe7375463c00324d258c65fb588
UL10nForge-0.30.0-beta.7z.003  3e26165bc112f202ab688d14536d195fc91bfb586d06d6c4e2bab6f4533760f3
UL10nForge-0.30.0-beta.7z.004  1ff7da1657fda1da1670addb018f18372e462e1a07e76bf5943bb2c5ce073678
```
"""


def _token() -> str:
    """从 git 凭据管理器取 GitHub token（git push 用的同一凭据）。"""
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        stdout=subprocess.PIPE, text=True, encoding="utf-8",
        errors="replace")
    for line in (proc.stdout or "").splitlines():
        if line.startswith("password="):
            return line[len("password="):].strip()
    raise RuntimeError("无法从 git 凭据获取 token")


def _curl(args: list[str], data: bytes | None = None) -> dict:
    import urllib.request
    req = urllib.request.Request(
        args[0], data=data, headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "UL10nForge-release",
            "X-GitHub-Api-Version": "2022-11-28",
        }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:300]}") from e


def _create_release() -> dict:
    """创建 release；已存在则复用并 PATCH 更新文案（2026-08-15 实证：
    只取 id 不更新 body 会让 SHA256 等文案停留在旧版）。"""
    from urllib.request import Request, urlopen

    def _headers() -> dict:
        return {"Authorization": f"Bearer {_token()}",
                "User-Agent": "UL10nForge-release",
                "X-GitHub-Api-Version": "2022-11-28"}

    try:
        return _curl([
            f"https://api.github.com/repos/{REPO}/releases",
        ], json.dumps({
            "tag_name": TAG, "name": RELEASE_NAME,
            "body": BODY, "prerelease": True,
        }).encode("utf-8"))
    except RuntimeError as exc:
        if "already_exists" not in str(exc):
            raise
    # 已存在 → 取 id 并同步文案
    req = Request(
        f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}",
        headers=_headers())
    with urlopen(req, timeout=60) as r:
        release = json.loads(r.read().decode("utf-8"))
    if release.get("body") != BODY:
        patch = Request(
            f"https://api.github.com/repos/{REPO}/releases/{release['id']}",
            data=json.dumps({"body": BODY}).encode("utf-8"),
            headers=_headers(), method="PATCH")
        with urlopen(patch, timeout=60) as r:
            release = json.loads(r.read().decode("utf-8"))
    return release


def _upload_asset(release_id: int, path: Path) -> None:
    """上传单个分卷（stream 上传，2GB 需要几分钟）。"""
    import urllib.request
    url = (f"https://uploads.github.com/repos/{REPO}/releases/"
           f"{release_id}/assets?name={path.name}")
    total = path.stat().st_size
    start = time.monotonic()
    req = urllib.request.Request(
        url, data=path.open("rb"), headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "UL10nForge-release",
            "Content-Type": "application/octet-stream",
        }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            result = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"上传失败 {path.name}: HTTP {e.code} "
                           f"{e.read().decode('utf-8', 'replace')[:200]}") from e
    elapsed = time.monotonic() - start
    print(f"[ok] {path.name} 已上传 "
          f"({total / 1e9:.2f} GB · {total / 1e6 / max(elapsed, 0.1):.1f} MB/s)"
          f" · {result.get('browser_download_url', '')[:80]}")


def main() -> int:
    notes_only = "--notes-only" in sys.argv
    release = _create_release()
    print(f"release: {release.get('html_url')} (id={release.get('id')})")
    if notes_only:
        return 0
    parts = sorted(DIST.glob("UL10nForge-0.30.0-beta.7z.*"))
    if not parts:
        print("[FAIL] 分卷不存在：先运行 _split_release.py")
        return 1
    # 跳过已上传的同名资产（断点续传）
    existing = {a["name"] for a in release.get("assets", [])}
    for part in parts:
        if part.name in existing:
            print(f"[skip] {part.name} 已存在")
            continue
        try:
            _upload_asset(release["id"], part)
        except RuntimeError as exc:
            print(f"[FAIL] {exc}")
            return 1
    print("[done] 全部分卷上传完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
