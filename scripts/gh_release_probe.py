"""阶段 4 预检：探测 GitHub 仓库 Releases 里的 Windows Unity 构建资产。"""
from __future__ import annotations

import json
import sys
import urllib.request

REPOS = [
    "BayatGames/RedRunner",
    "nvjob/Infinity-Square-Space",
    "trolit/projectZero",
    "choubari/3D-Tanks-Game-Unity",
    "AnimaRain/ShootAR",
    "CrimsonHawk/Unity-Game-Sample",
    "gamesgoodtocook/unitygame",
    "zalo/MathUtilities",
    "imadr/Unity-game-hacking",  # 教程，无构建，参考
    "Unity-Technologies/TanksDemo",
]


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "probe"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


for repo in REPOS:
    try:
        rel = get(f"https://api.github.com/repos/{repo}/releases?per_page=5")
    except Exception as exc:  # noqa: BLE001
        print(f"{repo}: REQ-FAIL {type(exc).__name__}")
        continue
    if not rel:
        print(f"{repo}: no releases")
        continue
    for r in rel[:2]:
        assets = [a["name"] for a in r.get("assets", [])]
        win = [a for a in assets if any(
            a.lower().endswith(ext) for ext in (".zip", ".rar", ".7z"))]
        print(f"{repo} v{r.get('tag_name','?')}: assets={len(assets)} win={win}")
