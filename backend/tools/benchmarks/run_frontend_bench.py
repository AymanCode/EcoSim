"""Browser-level dashboard benchmark for the live React frontend.

This benchmark expects the FastAPI backend and Vite frontend to be running.
It launches Chrome through the Chrome DevTools Protocol, initializes a 10k
simulation through the real UI, and records WebSocket plus browser-side costs.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import shutil
import socket
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests

from .common import (
    BenchmarkPaths,
    collect_metadata,
    default_results_root,
    mean,
    percentile,
    write_json,
    write_markdown,
    write_rows_csv,
)


BENCHMARK_INSTRUMENTATION = r"""
(() => {
  if (window.__ecosimBenchInstalled) return;
  window.__ecosimBenchInstalled = true;
  const bench = window.__ecosimBench = {
    startedAt: performance.now(),
    messages: [],
    longTasks: [],
    layoutShifts: [],
    errors: [],
    warnings: [],
    wsMessagesTotal: 0,
    lcpMs: 0,
    cls: 0
  };

  const textSize = (value) => {
    if (typeof value !== "string") return 0;
    try {
      return new TextEncoder().encode(value).length;
    } catch (_error) {
      return value.length;
    }
  };

  window.addEventListener("error", (event) => {
    bench.errors.push({
      message: String(event.message || ""),
      source: String(event.filename || ""),
      line: Number(event.lineno || 0),
      col: Number(event.colno || 0),
      atMs: performance.now()
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    bench.errors.push({
      message: String(event.reason && event.reason.message ? event.reason.message : event.reason || "unhandled rejection"),
      source: "unhandledrejection",
      line: 0,
      col: 0,
      atMs: performance.now()
    });
  });

  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        bench.longTasks.push({
          startTime: Number(entry.startTime || 0),
          duration: Number(entry.duration || 0),
          name: String(entry.name || "longtask")
        });
      }
    }).observe({ entryTypes: ["longtask"] });
  } catch (_error) {}

  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        bench.lcpMs = Number(entry.startTime || 0);
      }
    }).observe({ type: "largest-contentful-paint", buffered: true });
  } catch (_error) {}

  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.hadRecentInput) continue;
        const value = Number(entry.value || 0);
        bench.cls += value;
        bench.layoutShifts.push({
          startTime: Number(entry.startTime || 0),
          value
        });
      }
    }).observe({ type: "layout-shift", buffered: true });
  } catch (_error) {}

  const NativeWebSocket = window.WebSocket;
  function BenchWebSocket(url, protocols) {
    const ws = protocols === undefined
      ? new NativeWebSocket(url)
      : new NativeWebSocket(url, protocols);

    ws.addEventListener("message", (event) => {
      const receivedAt = performance.now();
      const raw = typeof event.data === "string" ? event.data : "";
      let parsed = null;
      let parseMs = 0;
      let parseFailed = false;
      try {
        const parseStart = performance.now();
        parsed = JSON.parse(raw);
        parseMs = performance.now() - parseStart;
      } catch (_error) {
        parseFailed = true;
      }

      bench.wsMessagesTotal += 1;
      if (!parsed || !parsed.metrics) {
        return;
      }

      const metrics = parsed.metrics || {};
      const row = {
        messageIndex: bench.messages.length,
        tick: Number(parsed.tick || 0),
        receivedAtMs: receivedAt,
        payloadBytes: textSize(raw),
        parseMs,
        parseFailed,
        backendTickComputeMs: Number(metrics.tickComputeMs || 0),
        trackedSubjects: Array.isArray(metrics.trackedSubjects) ? metrics.trackedSubjects.length : 0,
        trackedFirms: Array.isArray(metrics.trackedFirms) ? metrics.trackedFirms.length : 0,
        logCount: Array.isArray(parsed.logs) ? parsed.logs.length : 0,
        metricKeyCount: Object.keys(metrics).length,
        nextFrameMs: null,
        twoFrameMs: null
      };
      bench.messages.push(row);
      requestAnimationFrame(() => {
        row.nextFrameMs = performance.now() - receivedAt;
        requestAnimationFrame(() => {
          row.twoFrameMs = performance.now() - receivedAt;
        });
      });
    }, { capture: true });
    return ws;
  }

  Object.setPrototypeOf(BenchWebSocket, NativeWebSocket);
  BenchWebSocket.prototype = NativeWebSocket.prototype;
  for (const key of ["CONNECTING", "OPEN", "CLOSING", "CLOSED"]) {
    Object.defineProperty(BenchWebSocket, key, { value: NativeWebSocket[key] });
  }
  window.WebSocket = BenchWebSocket;
})();
"""


def _chrome_candidates() -> list[Path]:
    roots = [
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        Path.home() / "AppData/Local/Microsoft/Edge/Application/msedge.exe",
    ]
    return [path for path in roots if path.exists()]


def _resolve_chrome_path(value: str | None) -> Path:
    if value:
        path = Path(value)
        if not path.exists():
            raise FileNotFoundError(f"Chrome executable not found: {path}")
        return path
    candidates = _chrome_candidates()
    if candidates:
        return candidates[0]
    found = shutil.which("chrome") or shutil.which("msedge") or shutil.which("chromium")
    if found:
        return Path(found)
    raise FileNotFoundError("Chrome or Edge was not found in standard locations.")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.perf_counter() + timeout_seconds
    last_error: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            response = requests.get(url, timeout=1.0)
            if response.ok:
                return response.json()
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def _open_cdp_tab(port: int) -> dict[str, Any]:
    target = urllib.parse.quote("about:blank", safe="")
    url = f"http://127.0.0.1:{port}/json/new?{target}"
    response = requests.put(url, timeout=5.0)
    if response.status_code >= 400:
        response = requests.get(url, timeout=5.0)
    response.raise_for_status()
    return response.json()


class CdpClient:
    def __init__(self, websocket_url: str, timeout_seconds: float) -> None:
        # Lazy import: websocket-client is only needed to actually drive the
        # browser benchmark, not to import the harness helpers (which the
        # contract tests exercise). Keeps the import chain dependency-free in CI.
        import websocket

        self._ws_mod = websocket
        self._ws = websocket.create_connection(
            websocket_url,
            timeout=timeout_seconds,
            suppress_origin=True,
        )
        self._timeout_seconds = timeout_seconds
        self._next_id = 1
        self.events: list[dict[str, Any]] = []
        self.console_rows: list[dict[str, Any]] = []

    def close(self) -> None:
        self._ws.close()

    def command(self, method: str, params: dict[str, Any] | None = None, timeout_seconds: float | None = None) -> dict[str, Any]:
        command_id = self._next_id
        self._next_id += 1
        payload = {"id": command_id, "method": method}
        if params:
            payload["params"] = params
        self._ws.send(json.dumps(payload))
        deadline = time.perf_counter() + (timeout_seconds or self._timeout_seconds)
        while time.perf_counter() < deadline:
            try:
                raw = self._ws.recv()
            except self._ws_mod.WebSocketTimeoutException:
                continue
            message = json.loads(raw)
            if "method" in message:
                self._record_event(message)
                continue
            if message.get("id") != command_id:
                continue
            if "error" in message:
                raise RuntimeError(f"CDP command failed: {method}: {message['error']}")
            return message.get("result", {})
        raise TimeoutError(f"Timed out waiting for CDP command {method}")

    def evaluate(self, expression: str, *, timeout_seconds: float | None = None) -> Any:
        result = self.command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
                "timeout": int((timeout_seconds or self._timeout_seconds) * 1000.0),
            },
            timeout_seconds=timeout_seconds,
        )
        remote = result.get("result", {})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return remote.get("value")

    def _record_event(self, message: dict[str, Any]) -> None:
        self.events.append(message)
        method = message.get("method", "")
        params = message.get("params", {})
        if method == "Runtime.consoleAPICalled":
            level = str(params.get("type", "log"))
            args = params.get("args", [])
            text = " ".join(str(arg.get("value", arg.get("description", ""))) for arg in args)
            if level in {"warning", "error", "assert"}:
                self.console_rows.append(
                    {
                        "source": "console",
                        "level": level,
                        "message": text,
                        "timestamp_ms": params.get("timestamp", 0),
                    }
                )
        elif method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails", {})
            self.console_rows.append(
                {
                    "source": "exception",
                    "level": "error",
                    "message": str(details.get("text", "")),
                    "timestamp_ms": params.get("timestamp", 0),
                }
            )
        elif method == "Log.entryAdded":
            entry = params.get("entry", {})
            level = str(entry.get("level", "log"))
            if level in {"warning", "error"}:
                self.console_rows.append(
                    {
                        "source": str(entry.get("source", "log")),
                        "level": level,
                        "message": str(entry.get("text", "")),
                        "timestamp_ms": entry.get("timestamp", 0),
                    }
                )


def _launch_chrome(
    *,
    chrome_path: Path,
    port: int,
    user_data_dir: Path,
    headless: bool,
    viewport: str,
) -> subprocess.Popen:
    args = [
        str(chrome_path),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir.resolve()}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        "--remote-allow-origins=*",
        f"--window-size={viewport}",
        "about:blank",
    ]
    if headless:
        args.insert(1, "--headless=new")
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_for_page_ready(cdp: CdpClient, timeout_seconds: float) -> None:
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        ready = cdp.evaluate(
            "document.readyState === 'complete' && document.body && document.body.innerText.includes('Simulation Controls')",
            timeout_seconds=5.0,
        )
        if ready:
            return
        time.sleep(0.5)
    raise TimeoutError("Frontend page did not reach the config screen.")


def _set_population_and_launch(cdp: CdpClient, households: int, timeout_seconds: float) -> None:
    script = f"""
    (() => {{
      const input = [...document.querySelectorAll('input[type="range"]')]
        .find(el => Number(el.max) >= {households});
      if (!input) return {{ok: false, reason: 'population range input not found'}};
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(input, String({households}));
      input.dispatchEvent(new Event('input', {{ bubbles: true }}));
      input.dispatchEvent(new Event('change', {{ bubbles: true }}));
      return {{ok: true, value: input.value}};
    }})()
    """
    result = cdp.evaluate(script, timeout_seconds=5.0)
    if not result or not result.get("ok"):
        raise RuntimeError(f"Could not set population scale: {result}")

    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        launched = cdp.evaluate(
            """
            (() => {
              const button = [...document.querySelectorAll('button')]
                .find(el => el.textContent && el.textContent.includes('Launch Simulation'));
              if (!button) return {ok: false, reason: 'launch button not found'};
              if (button.disabled) return {ok: false, reason: 'launch button disabled'};
              button.click();
              return {ok: true};
            })()
            """,
            timeout_seconds=5.0,
        )
        if launched and launched.get("ok"):
            return
        time.sleep(0.5)
    raise TimeoutError("Could not launch simulation through the UI.")


def _click_view(cdp: CdpClient, label: str) -> bool:
    return bool(
        cdp.evaluate(
            f"""
            (() => {{
              const label = {json.dumps(label)};
              const button = [...document.querySelectorAll('button')]
                .find(el => el.textContent && el.textContent.trim().includes(label) && !el.disabled);
              if (!button) return false;
              button.click();
              return true;
            }})()
            """,
            timeout_seconds=5.0,
        )
    )


def _collect_browser_snapshot(cdp: CdpClient) -> dict[str, Any]:
    return cdp.evaluate(
        """
        (() => {
          const bench = window.__ecosimBench || {};
          return {
            url: location.href,
            title: document.title,
            bodyTextSample: document.body ? document.body.innerText.slice(0, 500) : '',
            messages: bench.messages || [],
            longTasks: bench.longTasks || [],
            layoutShifts: bench.layoutShifts || [],
            errors: bench.errors || [],
            warnings: bench.warnings || [],
            wsMessagesTotal: bench.wsMessagesTotal || 0,
            lcpMs: bench.lcpMs || 0,
            cls: bench.cls || 0,
            memory: performance.memory ? {
              jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
              totalJSHeapSize: performance.memory.totalJSHeapSize,
              usedJSHeapSize: performance.memory.usedJSHeapSize
            } : null,
            navigation: performance.getEntriesByType('navigation').map(entry => ({
              startTime: entry.startTime,
              duration: entry.duration,
              domContentLoadedEventEnd: entry.domContentLoadedEventEnd,
              loadEventEnd: entry.loadEventEnd,
              transferSize: entry.transferSize || 0,
              encodedBodySize: entry.encodedBodySize || 0,
              decodedBodySize: entry.decodedBodySize || 0
            }))[0] || null
          };
        })()
        """,
        timeout_seconds=10.0,
    )


def _summarize(rows: list[dict[str, Any]], long_tasks: list[dict[str, Any]], snapshot: dict[str, Any], performance_metrics: dict[str, Any]) -> dict[str, Any]:
    payloads = [float(row.get("payloadBytes", 0.0)) for row in rows]
    parse = [float(row.get("parseMs", 0.0)) for row in rows]
    next_frame = [float(row.get("nextFrameMs", 0.0)) for row in rows if row.get("nextFrameMs") is not None]
    two_frame = [float(row.get("twoFrameMs", 0.0)) for row in rows if row.get("twoFrameMs") is not None]
    backend_compute = [float(row.get("backendTickComputeMs", 0.0)) for row in rows]
    received_at = [float(row.get("receivedAtMs", 0.0)) for row in rows]
    interarrival = [
        received_at[index] - received_at[index - 1]
        for index in range(1, len(received_at))
        if received_at[index] >= received_at[index - 1]
    ]
    long_task_durations = [float(row.get("duration", 0.0)) for row in long_tasks]
    metric_map = {item.get("name"): item.get("value") for item in performance_metrics.get("metrics", [])}
    total_payload = sum(payloads)
    return {
        "tick_messages": len(rows),
        "final_tick": int(rows[-1].get("tick", 0)) if rows else 0,
        "total_payload_bytes": int(total_payload),
        "mean_payload_bytes": round(mean(payloads), 2),
        "p95_payload_bytes": round(percentile(payloads, 95), 2),
        "p50_interarrival_ms": round(percentile(interarrival, 50), 3),
        "p95_interarrival_ms": round(percentile(interarrival, 95), 3),
        "p50_backend_tick_compute_ms": round(percentile(backend_compute, 50), 3),
        "p95_backend_tick_compute_ms": round(percentile(backend_compute, 95), 3),
        "p50_parse_ms": round(percentile(parse, 50), 3),
        "p95_parse_ms": round(percentile(parse, 95), 3),
        "p50_next_frame_ms": round(percentile(next_frame, 50), 3),
        "p95_next_frame_ms": round(percentile(next_frame, 95), 3),
        "p50_two_frame_ms": round(percentile(two_frame, 50), 3),
        "p95_two_frame_ms": round(percentile(two_frame, 95), 3),
        "long_task_count": len(long_tasks),
        "long_task_total_ms": round(sum(long_task_durations), 3),
        "p95_long_task_ms": round(percentile(long_task_durations, 95), 3),
        "max_long_task_ms": round(max(long_task_durations), 3) if long_task_durations else 0.0,
        "lcp_ms": round(float(snapshot.get("lcpMs", 0.0) or 0.0), 3),
        "cls": round(float(snapshot.get("cls", 0.0) or 0.0), 5),
        "used_js_heap_mb": round(float((snapshot.get("memory") or {}).get("usedJSHeapSize", 0.0)) / (1024.0 * 1024.0), 3),
        "task_duration_ms": round(float(metric_map.get("TaskDuration", 0.0) or 0.0) * 1000.0, 3),
        "script_duration_ms": round(float(metric_map.get("ScriptDuration", 0.0) or 0.0) * 1000.0, 3),
        "layout_duration_ms": round(float(metric_map.get("LayoutDuration", 0.0) or 0.0) * 1000.0, 3),
        "recalc_style_duration_ms": round(float(metric_map.get("RecalcStyleDuration", 0.0) or 0.0) * 1000.0, 3),
        "node_count": int(metric_map.get("Nodes", 0) or 0),
        "error_count": len(snapshot.get("errors", []) or []),
    }


def _render_summary(metadata: dict[str, Any], summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# EcoSim Frontend Browser Benchmark",
            "",
            "## Runtime Context",
            "",
            f"- Commit: `{metadata.get('commit', 'unknown')}`",
            f"- Platform: `{metadata.get('platform', 'unknown')}`",
            f"- Browser: `{metadata.get('browser_product', 'unknown')}`",
            f"- URL: `{metadata.get('url', 'unknown')}`",
            f"- Viewport: `{metadata.get('viewport', 'unknown')}`",
            "",
            "## Results",
            "",
            f"- Tick messages: `{summary.get('tick_messages', 0)}`",
            f"- Final tick observed: `{summary.get('final_tick', 0)}`",
            f"- Total streamed payload: `{summary.get('total_payload_bytes', 0)} bytes`",
            f"- p95 payload size: `{summary.get('p95_payload_bytes', 0.0)} bytes`",
            f"- p95 JSON parse: `{summary.get('p95_parse_ms', 0.0)} ms`",
            f"- p95 next-frame latency: `{summary.get('p95_next_frame_ms', 0.0)} ms`",
            f"- p95 two-frame latency: `{summary.get('p95_two_frame_ms', 0.0)} ms`",
            f"- Long tasks: `{summary.get('long_task_count', 0)}` total, `{summary.get('p95_long_task_ms', 0.0)} ms` p95",
            f"- LCP: `{summary.get('lcp_ms', 0.0)} ms`",
            f"- CLS: `{summary.get('cls', 0.0)}`",
            f"- Used JS heap: `{summary.get('used_js_heap_mb', 0.0)} MB`",
            "",
            "## Evidence Summary",
            "",
            (
                "- The live React dashboard benchmark measures WebSocket payloads, "
                "browser JSON parse time, frame latency, long tasks, and Core Web Vitals-style load/stability metrics."
            ),
        ]
    )


def run_frontend_benchmark(
    *,
    url: str,
    households: int,
    ticks: int,
    output_root: Path,
    chrome_path: str | None,
    remote_debugging_port: int,
    viewport: str,
    timeout_seconds: float,
    headless: bool,
    cycle_views: list[str],
    view_cycle_interval: int,
) -> dict[str, Any]:
    paths = BenchmarkPaths.create(output_root, "frontend-browser")
    resolved_chrome = _resolve_chrome_path(chrome_path)
    port = remote_debugging_port if remote_debugging_port > 0 else _free_port()
    user_data_dir = paths.run_dir / "chrome-user-data"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    process = _launch_chrome(
        chrome_path=resolved_chrome,
        port=port,
        user_data_dir=user_data_dir,
        headless=headless,
        viewport=viewport,
    )

    cdp: CdpClient | None = None
    try:
        version = _wait_for_json(f"http://127.0.0.1:{port}/json/version", timeout_seconds=timeout_seconds)
        tab = _open_cdp_tab(port)
        cdp = CdpClient(tab["webSocketDebuggerUrl"], timeout_seconds=timeout_seconds)
        cdp.command("Runtime.enable")
        cdp.command("Page.enable")
        cdp.command("Log.enable")
        cdp.command("Performance.enable")
        width, height = [int(part) for part in viewport.lower().split("x", 1)]
        cdp.command(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )
        cdp.command("Page.addScriptToEvaluateOnNewDocument", {"source": BENCHMARK_INSTRUMENTATION})
        cdp.command("Page.navigate", {"url": url})
        _wait_for_page_ready(cdp, timeout_seconds)
        _set_population_and_launch(cdp, households, timeout_seconds)

        next_view_index = 0
        next_view_threshold = view_cycle_interval if cycle_views else ticks + 1
        deadline = time.perf_counter() + timeout_seconds
        while time.perf_counter() < deadline:
            message_count = int(
                cdp.evaluate(
                    "(window.__ecosimBench && window.__ecosimBench.messages.length) || 0",
                    timeout_seconds=5.0,
                )
                or 0
            )
            if message_count >= ticks:
                break
            if cycle_views and message_count >= next_view_threshold:
                _click_view(cdp, cycle_views[next_view_index % len(cycle_views)])
                next_view_index += 1
                next_view_threshold += max(1, view_cycle_interval)
            time.sleep(0.5)
        else:
            raise TimeoutError(f"Timed out waiting for {ticks} frontend tick messages.")

        # Let the last message reach at least one more animation frame.
        time.sleep(1.0)
        _click_view(cdp, "Command")
        snapshot = _collect_browser_snapshot(cdp)
        screenshot = cdp.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        screenshot_path = paths.run_dir / "frontend-final.png"
        screenshot_path.write_bytes(base64.b64decode(screenshot["data"]))
        performance_metrics = cdp.command("Performance.getMetrics")
        with contextlib.suppress(Exception):
            cdp.evaluate(
                """
                (() => {
                  const button = [...document.querySelectorAll('button')]
                    .find(el => el.textContent && el.textContent.includes('Suspend'));
                  if (button) button.click();
                  return true;
                })()
                """,
                timeout_seconds=5.0,
            )

        message_rows = list(snapshot.get("messages", []))[:ticks]
        long_task_rows = list(snapshot.get("longTasks", []))
        summary = _summarize(message_rows, long_task_rows, snapshot, performance_metrics)
        metadata = collect_metadata(
            {
                "benchmark": "frontend-browser",
                "url": url,
                "households": households,
                "ticks": ticks,
                "chrome_path": str(resolved_chrome),
                "browser_product": version.get("Browser", "unknown"),
                "viewport": viewport,
                "headless": headless,
                "cycle_views": cycle_views,
                "view_cycle_interval": view_cycle_interval,
            }
        )
        message_csv = write_rows_csv(paths, "frontend_message_rows", message_rows)
        long_task_csv = write_rows_csv(paths, "frontend_long_task_rows", long_task_rows)
        console_csv = write_rows_csv(paths, "frontend_console_rows", cdp.console_rows)
        summary_md = write_markdown(paths, "summary", _render_summary(metadata, summary))
        raw_json = write_json(
            paths,
            "raw",
            {
                "metadata": metadata,
                "summary": summary,
                "snapshot": snapshot,
                "performance_metrics": performance_metrics,
                "console_rows": cdp.console_rows,
            },
        )
        return {
            "paths": paths,
            "metadata": metadata,
            "summary": summary,
            "rows": message_rows,
            "artifacts": {
                "message_csv": message_csv,
                "long_task_csv": long_task_csv,
                "console_csv": console_csv,
                "summary_md": summary_md,
                "raw_json": raw_json,
                "screenshot": screenshot_path,
            },
        }
    finally:
        if cdp is not None:
            with contextlib.suppress(Exception):
                cdp.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def _parse_view_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark EcoSim frontend browser performance.")
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--households", type=int, default=10000)
    parser.add_argument("--ticks", type=int, default=100)
    parser.add_argument("--chrome-path", default=None)
    parser.add_argument("--remote-debugging-port", type=int, default=0)
    parser.add_argument("--viewport", default="1440x1000")
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--headed", action="store_true", help="Run a visible browser instead of headless Chrome.")
    parser.add_argument(
        "--cycle-views",
        default="Command,Population,Markets,Finance,Government,Logs",
        help="Comma-separated dashboard nav labels to click during the run. Empty disables cycling.",
    )
    parser.add_argument("--view-cycle-interval", type=int, default=20)
    parser.add_argument("--output-root", type=Path, default=default_results_root())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_frontend_benchmark(
        url=args.url,
        households=args.households,
        ticks=args.ticks,
        output_root=args.output_root,
        chrome_path=args.chrome_path,
        remote_debugging_port=args.remote_debugging_port,
        viewport=args.viewport,
        timeout_seconds=args.timeout_seconds,
        headless=not args.headed,
        cycle_views=_parse_view_list(args.cycle_views),
        view_cycle_interval=max(1, args.view_cycle_interval),
    )
    print(f"Wrote frontend benchmark artifacts to {result['paths'].run_dir}")
    print(f"p95 next-frame latency: {result['summary']['p95_next_frame_ms']} ms")
    print(f"p95 JSON parse: {result['summary']['p95_parse_ms']} ms")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
