"""Small deployment probe: real Nginx assets, WebSocket ticks, optional SQLite readback.

Run against a disposable stack; this creates one small simulation run. It does
not replace the real-browser performance/evidence harness.
"""

from __future__ import annotations

import argparse
import asyncio
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import sqlite3
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import urlopen
import uuid

from websockets.asyncio.client import connect


class DashboardAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets: set[str] = set()
        self.has_root = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.has_root |= attrs.get("id") == "root"
        if tag == "script" and attrs.get("src"):
            self.assets.add(attrs["src"])
        if tag == "link" and attrs.get("rel") in {"stylesheet", "modulepreload"}:
            self.assets.add(attrs["href"])


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_http(url):
    with urlopen(url, timeout=10) as response:
        html = response.read().decode("utf-8")
    parser = DashboardAssets()
    parser.feed(html)
    require(parser.has_root and parser.assets, "Dashboard HTML has no React root or built assets")
    for asset in sorted(parser.assets):
        with urlopen(urljoin(url, asset), timeout=10) as response:
            require(response.headers.get_content_type() in {"text/javascript", "application/javascript", "text/css"},
                    f"Asset did not return JavaScript/CSS: {asset}")
            require(response.read(), f"Empty dashboard asset: {asset}")
    with urlopen(urljoin(url, "/health"), timeout=10) as response:
        require(json.load(response).get("status") == "ok", "Backend health proxy failed")
    return len(parser.assets)


async def receive_until(socket, predicate):
    while True:
        message = json.loads(await socket.recv())
        require("error" not in message, f"Server error: {message.get('error')}")
        if predicate(message):
            return message


async def check_simulation(url, sqlite_path):
    parts = urlsplit(url)
    ws_url = urlunsplit(("wss" if parts.scheme == "https" else "ws", parts.netloc, "/ws", "", ""))
    probe_id = uuid.uuid4().hex
    async with asyncio.timeout(60):
        async with connect(ws_url, proxy=None, open_timeout=10, close_timeout=5, max_size=10_000_000) as socket:
            await receive_until(socket, lambda m: m.get("type") == "SESSION")
            await socket.send(json.dumps({"command": "SETUP", "config": {
                "num_households": 30, "num_firms": 2, "seed": 42,
                "enable_llm_government": False, "startup_smoke_id": probe_id,
            }}))
            await receive_until(socket, lambda m: m.get("type") == "SETUP_COMPLETE")
            await socket.send(json.dumps({"command": "START"}))
            await receive_until(socket, lambda m: m.get("type") == "STARTED")
            last_tick = 0
            for _ in range(2):
                frame = await receive_until(socket, lambda m: "metrics" in m and "tick" in m)
                require(frame["tick"] > last_tick, "Simulation ticks did not advance")
                last_tick = frame["tick"]
                require(math.isfinite(frame["metrics"]["gdp"]), "Non-finite GDP in tick frame")
                require(frame["metrics"]["trackedSubjects"], "No households in dashboard telemetry")
            await socket.send(json.dumps({"command": "STOP"}))
            await receive_until(socket, lambda m: m.get("type") == "STOPPED")
            # RESET closes the run synchronously, giving deterministic readback
            # without sleeps or racing WebSocket-disconnect cleanup.
            await socket.send(json.dumps({"command": "RESET"}))
            await receive_until(socket, lambda m: m.get("type") == "RESET")

    result = {"ticks_observed": last_tick, "websocket": "ok"}
    if sqlite_path:
        uri = Path(sqlite_path).resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            run = connection.execute(
                "SELECT run_id, status, last_fully_persisted_tick, ended_at "
                "FROM simulation_runs WHERE json_extract(config_json, '$.startup_smoke_id') = ?",
                (probe_id,),
            ).fetchone()
            require(run is not None, "Smoke run was not persisted to SQLite")
            run_id, status, watermark, ended_at = run
            require(status == "stopped" and ended_at, f"Run was not closed: {run}")
            count, max_tick = connection.execute(
                "SELECT COUNT(*), MAX(tick) FROM tick_metrics WHERE run_id = ?", (run_id,),
            ).fetchone()
            require(count >= 2 and max_tick >= last_tick and watermark >= last_tick,
                    f"Incomplete SQLite tick persistence: count={count}, max={max_tick}, watermark={watermark}")
            result.update(run_id=run_id, persisted_ticks=count, sqlite="ok")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:5173", help="Dashboard/Nginx URL")
    parser.add_argument("--sqlite-path", help="Optional SQLite file on the machine running this probe")
    args = parser.parse_args()
    assets = check_http(args.url)
    result = asyncio.run(check_simulation(args.url, args.sqlite_path))
    print(json.dumps({"dashboard_assets": assets, **result}, indent=2))


if __name__ == "__main__":
    main()
