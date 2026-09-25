"""Extract the recorded demo towns into the data block of 06-all-the-numbers.html.

Reads frontend-react/public/demo/town-a.jsonl (no changes) and town-b.jsonl
(higher minimum wage): JSON Lines, where `kind == "message"` lines carry a
`message` and tick frames are the messages with a numeric `tick` and no `type`.

Writes one JSON object into the <script id="numbers-data"> element of the
mockup, and prints whether each not-yet-curated `metrics` scalar is fresh
every tick or repeated (cached) between refreshes.

Run from anywhere:  python3 docs/superpowers/specs/2026-09-25-mockups/extract_numbers_data.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DEMO = ROOT / "frontend-react" / "public" / "demo"
HTML = HERE / "06-all-the-numbers.html"
TICK = 72  # Year 2, week 20: the week the Run screen is on in the mockup.
EVENT_KEYS = ["hired", "laidOff", "firmsOpened", "firmsClosed"]
# Not yet in `curated`; adding them is a backend change. Money ones are sent
# in millions, stored here in dollars.
NEW_METRICS = {"happiness": 1, "top10Share": 1, "bottom50Share": 1, "gdp": 1e6, "govRevenue": 1e6, "govTransfers": 1e6}
TOWNS = [("A", "town-a.jsonl", "Town A", "No changes"), ("B", "town-b.jsonl", "Town B", "A higher minimum wage")]


def tick_frames(path: Path) -> list[dict]:
    frames = []
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row.get("kind") != "message":
            continue
        msg = row["message"]
        if isinstance(msg, dict) and isinstance(msg.get("tick"), (int, float)) and "type" not in msg:
            frames.append(msg)
    frames.sort(key=lambda f: f["tick"])
    ticks = [f["tick"] for f in frames]
    assert ticks == list(range(1, len(frames) + 1)), f"{path.name}: ticks are not 1..N"
    return frames


def num(value, scale=1.0):
    if value is None:
        return None
    value = float(value) * scale
    return float(f"{value:.7g}") if value else 0


def refresh_ticks(values: list) -> list[int]:
    """Ticks (1-based) where the value differs from the week before."""
    return [1] + [i + 1 for i in range(1, len(values)) if values[i] != values[i - 1]]


def cache_verdict(values: list) -> dict:
    changes = refresh_ticks(values)
    live = [t for t in changes if t > 10]
    gaps = Counter(b - a for a, b in zip(live, live[1:]))
    if len(changes) >= len(values) - 1:
        verdict = "fresh every tick"
    elif gaps and set(gaps) == {5}:
        verdict = "cached: refreshed every 5 ticks (1, then multiples of 5), repeated in between"
    else:
        repeats = sorted(set(range(1, len(values) + 1)) - set(changes))
        verdict = f"fresh after warm-up; repeated only at ticks {repeats}"
    return {"refreshes": len(changes), "of": len(values), "verdict": verdict}


def extract_town(key: str, filename: str, label: str, rules: str) -> tuple[dict, dict]:
    frames = tick_frames(DEMO / filename)
    curated_keys = list(frames[0]["curated"].keys())
    series = {k: [num(f["curated"].get(k)) for f in frames] for k in curated_keys}
    for k in EVENT_KEYS:
        series[k] = [int(f["eventCounts"].get(k, 0)) for f in frames]
    raw_new = {k: [f["metrics"].get(k) for f in frames] for k in NEW_METRICS}
    for k, scale in NEW_METRICS.items():
        series[k] = [num(v, scale) for v in raw_new[k]]
    at = frames[TICK - 1]
    firms = [{"name": f["name"], "sector": f["sector"], "state": f["state"], "staff": f["staff"]} for f in at["firms"]]
    town = {
        "key": key,
        "label": label,
        "rules": rules,
        "policy": at["metrics"]["governmentPolicy"],
        "policyChanges": at["metrics"].get("policyChanges") or [],
        "firms": firms,
        "firmStates": dict(Counter(f["state"] for f in firms)),
        "closedLastYear": len(at.get("firmsClosed") or []),
        "series": series,
    }
    cache = {k: cache_verdict(v) for k, v in raw_new.items()}
    cache["curated.gini/wealthP10-90"] = cache_verdict(series["gini"])
    return town, cache


def main() -> int:
    towns, report = [], {}
    for spec in TOWNS:
        town, cache = extract_town(*spec)
        towns.append(town)
        report[town["label"]] = cache
    first = tick_frames(DEMO / TOWNS[0][1])
    data = {
        "tick": TICK,
        "horizon": len(first),
        "warmup": 10,
        "households": int(first[0]["curated"]["householdsTotal"]),
        "source": "frontend-react/public/demo/town-a.jsonl and town-b.jsonl (seed 1337, 500 households, 104 weeks)",
        "towns": towns,
        "cache": report["Town A"],
    }
    for label, cache in report.items():
        print(label)
        for k, v in cache.items():
            print(f"  {k:28s} {v['refreshes']:3d}/{v['of']} distinct  {v['verdict']}")
    if not HTML.exists():
        print(f"{HTML.name} not found; nothing written", file=sys.stderr)
        return 1
    blob = json.dumps(data, separators=(",", ":"))
    html = HTML.read_text()
    pattern = re.compile(r'(<script id="numbers-data" type="application/json">)(.*?)(</script>)', re.S)
    if not pattern.search(html):
        print("data block not found in the HTML", file=sys.stderr)
        return 1
    HTML.write_text(pattern.sub(lambda m: m.group(1) + blob + m.group(3), html, count=1))
    print(f"wrote {len(blob):,} bytes of data into {HTML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
