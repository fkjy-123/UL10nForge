"""阶段 4：GitHub 搜索带 Windows 构建的 Unity 游戏仓库。"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

QUERIES = [
    "topic:unity3d stars:>20",
    "topic:unity-game language:C# stars:>10",
    "unity game windows release in:readme",
    "unity game download windows in:readme stars:>5",
]

UA = {"User-Agent": "probe", "Accept": "application/vnd.github+json"}


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


seen: set[str] = set()
cands = []
for q in QUERIES:
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(q) + "&sort=stars&per_page=20")
    try:
        data = get(url)
    except Exception as exc:  # noqa: BLE001
        print(f"Q {q!r}: FAIL {exc}", flush=True)
        time.sleep(8)
        continue
    for r in data.get("items", []):
        full = r["full_name"]
        if full in seen:
            continue
        seen.add(full)
        cands.append((full, r["stargazers_count"],
                      (r.get("description") or "")[:50]))
    print(f"Q {q!r}: +{len(data.get('items', []))} total={len(cands)}", flush=True)
    time.sleep(8)

json.dump([c[0] for c in cands], open("survey_out/_gh_candidates.json", "w"))
print(f"\n===== {len(cands)} 候选 =====", flush=True)
for full, stars, desc in cands:
    print(f"{full} {stars} {desc}", flush=True)
