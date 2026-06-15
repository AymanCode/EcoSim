"""Run a real frontend/server/warehouse EcoSim evidence test.

This harness starts the FastAPI backend, starts the Vite React dashboard,
drives the dashboard through Chrome/CDP, captures the real WebSocket stream,
and verifies warehouse readback through REST plus SQLite queries.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import requests

from ..benchmarks.common import (
    BenchmarkPaths,
    collect_metadata,
    default_results_root,
    percentile,
    repo_root,
    write_json,
    write_markdown,
    write_rows_csv,
)
from ..benchmarks.run_frontend_bench import (
    CdpClient,
    _click_view,
    _free_port,
    _launch_chrome,
    _open_cdp_tab,
    _resolve_chrome_path,
    _wait_for_json,
    _wait_for_page_ready,
)


FULL_APP_INSTRUMENTATION = r"""
(() => {
  if (window.__ecosimFullAppEvidenceInstalled) return;
  window.__ecosimFullAppEvidenceInstalled = true;
  const evidence = window.__ecosimEvidence = {
    startedAt: performance.now(),
    messages: [],
    errors: [],
    warnings: [],
    wsEvents: [],
    longTasks: [],
    layoutShifts: [],
    wsMessagesTotal: 0,
    topLevelKeys: {},
    metricKeys: {},
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

  const bump = (target, key) => {
    if (!key) return;
    target[key] = (target[key] || 0) + 1;
  };

  window.addEventListener("error", (event) => {
    evidence.errors.push({
      message: String(event.message || ""),
      source: String(event.filename || ""),
      line: Number(event.lineno || 0),
      col: Number(event.colno || 0),
      atMs: performance.now()
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    evidence.errors.push({
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
        evidence.longTasks.push({
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
        evidence.lcpMs = Number(entry.startTime || 0);
      }
    }).observe({ type: "largest-contentful-paint", buffered: true });
  } catch (_error) {}

  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.hadRecentInput) continue;
        const value = Number(entry.value || 0);
        evidence.cls += value;
        evidence.layoutShifts.push({
          startTime: Number(entry.startTime || 0),
          value
        });
      }
    }).observe({ type: "layout-shift", buffered: true });
  } catch (_error) {}

  const NativeWebSocket = window.WebSocket;
  function EvidenceWebSocket(url, protocols) {
    const ws = protocols === undefined
      ? new NativeWebSocket(url)
      : new NativeWebSocket(url, protocols);
    if (String(url || "").endsWith("/ws")) {
      window.__ecosimEvidenceAppSocket = ws;
    }
    const wsIndex = evidence.wsEvents.length;
    const recordWsEvent = (type, extra = {}) => {
      evidence.wsEvents.push({
        index: wsIndex,
        type,
        url: String(url || ""),
        readyState: Number(ws.readyState),
        atMs: performance.now(),
        ...extra
      });
    };
    recordWsEvent("constructed");

    const nativeSend = ws.send.bind(ws);
    ws.send = (payload) => {
      recordWsEvent("send", {
        payloadBytes: typeof payload === "string" ? textSize(payload) : 0,
        payloadSample: typeof payload === "string" ? payload.slice(0, 200) : ""
      });
      return nativeSend(payload);
    };

    ws.addEventListener("open", () => recordWsEvent("open"));
    ws.addEventListener("close", (event) => recordWsEvent("close", {
      code: Number(event.code || 0),
      reason: String(event.reason || ""),
      wasClean: Boolean(event.wasClean)
    }));
    ws.addEventListener("error", () => recordWsEvent("error"));

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
      recordWsEvent("message", {
        payloadBytes: textSize(raw),
        parsedType: parsed && parsed.type ? String(parsed.type) : "",
        hasMetrics: Boolean(parsed && parsed.metrics)
      });

      evidence.wsMessagesTotal += 1;
      if (!parsed || parseFailed) {
        return;
      }

      const topKeys = Object.keys(parsed).sort();
      for (const key of topKeys) bump(evidence.topLevelKeys, key);
      const metrics = parsed.metrics || {};
      for (const key of Object.keys(metrics).sort()) bump(evidence.metricKeys, key);
      if (!parsed.metrics) {
        return;
      }

      const historySizes = {};
      for (const [key, value] of Object.entries(metrics)) {
        if (key.endsWith("History") && Array.isArray(value)) {
          historySizes[key] = value.length;
        }
      }

      const row = {
        messageIndex: evidence.messages.length,
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
        topLevelKeys: topKeys.join(","),
        historySizes,
        nextFrameMs: null,
        twoFrameMs: null
      };
      evidence.messages.push(row);
      requestAnimationFrame(() => {
        row.nextFrameMs = performance.now() - receivedAt;
        requestAnimationFrame(() => {
          row.twoFrameMs = performance.now() - receivedAt;
        });
      });
    }, { capture: true });
    return ws;
  }

  Object.setPrototypeOf(EvidenceWebSocket, NativeWebSocket);
  EvidenceWebSocket.prototype = NativeWebSocket.prototype;
  for (const key of ["CONNECTING", "OPEN", "CLOSING", "CLOSED"]) {
    Object.defineProperty(EvidenceWebSocket, key, { value: NativeWebSocket[key] });
  }
  window.WebSocket = EvidenceWebSocket;
})();
"""


EVENT_KEY_TABLES = [
    "labor_events",
    "healthcare_events",
    "policy_actions",
    "llm_government_decisions",
    "regime_events",
]

FRONTEND_DEFAULT_FIRMS_PER_CATEGORY = 5
FRONTEND_DEFAULT_SEED = 42


READBACK_ENDPOINTS = {
    "runs": "/warehouse/runs",
    "tick_metrics": "/warehouse/runs/{run_id}/tick-metrics",
    "summary": "/warehouse/runs/{run_id}/summary",
    "decision_features": "/warehouse/runs/{run_id}/decision-features",
    "sector_metrics": "/warehouse/runs/{run_id}/sector-metrics",
    "tick_diagnostics": "/warehouse/runs/{run_id}/tick-diagnostics",
    "sector_shortages": "/warehouse/runs/{run_id}/sector-shortages",
    "regime_events": "/warehouse/runs/{run_id}/regime-events",
    "llm_government_decisions": "/warehouse/runs/{run_id}/llm-government-decisions",
}


def summarize_stream_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    payloads = [int(row.get("payloadBytes", row.get("payload_bytes", 0)) or 0) for row in rows]
    received = [float(row.get("receivedAtMs", 0.0) or 0.0) for row in rows]
    ticks = [int(row.get("tick", 0) or 0) for row in rows]
    duration_seconds = 0.0
    if len(received) >= 2 and received[-1] >= received[0]:
        duration_seconds = round((received[-1] - received[0]) / 1000.0, 3)
    frames_per_second = round(len(rows) / duration_seconds, 3) if duration_seconds > 0 else 0.0
    return {
        "frame_count": len(rows),
        "first_tick": ticks[0] if ticks else 0,
        "last_tick": ticks[-1] if ticks else 0,
        "duration_seconds": duration_seconds,
        "frames_per_second": frames_per_second,
        "payload_bytes": {
            "min": min(payloads) if payloads else 0,
            "p50": int(percentile(payloads, 50)),
            "p95": int(percentile(payloads, 95)),
            "max": max(payloads) if payloads else 0,
            "total": sum(payloads),
        },
        "max_tracked_subjects": max((int(row.get("trackedSubjects", 0) or 0) for row in rows), default=0),
        "max_tracked_firms": max((int(row.get("trackedFirms", 0) or 0) for row in rows), default=0),
    }


def summarize_browser_performance(
    rows: Sequence[Mapping[str, Any]],
    long_tasks: Sequence[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    parse_ms = [float(row.get("parseMs", 0.0) or 0.0) for row in rows]
    next_frame = [float(row.get("nextFrameMs", 0.0) or 0.0) for row in rows if row.get("nextFrameMs") is not None]
    two_frame = [float(row.get("twoFrameMs", 0.0) or 0.0) for row in rows if row.get("twoFrameMs") is not None]
    backend_compute = [float(row.get("backendTickComputeMs", 0.0) or 0.0) for row in rows]
    long_task_durations = [float(row.get("duration", 0.0) or 0.0) for row in long_tasks]
    memory = snapshot.get("memory") or {}
    return {
        "p50_parse_ms": round(percentile(parse_ms, 50), 3),
        "p95_parse_ms": round(percentile(parse_ms, 95), 3),
        "p50_next_frame_ms": round(percentile(next_frame, 50), 3),
        "p95_next_frame_ms": round(percentile(next_frame, 95), 3),
        "p50_two_frame_ms": round(percentile(two_frame, 50), 3),
        "p95_two_frame_ms": round(percentile(two_frame, 95), 3),
        "p50_backend_tick_compute_ms": round(percentile(backend_compute, 50), 3),
        "p95_backend_tick_compute_ms": round(percentile(backend_compute, 95), 3),
        "long_task_count": len(long_tasks),
        "long_task_total_ms": round(sum(long_task_durations), 3),
        "p95_long_task_ms": round(percentile(long_task_durations, 95), 3),
        "lcp_ms": round(float(snapshot.get("lcpMs", 0.0) or 0.0), 3),
        "cls": round(float(snapshot.get("cls", 0.0) or 0.0), 5),
        "used_js_heap_mb": round(float(memory.get("usedJSHeapSize", 0.0) or 0.0) / (1024.0 * 1024.0), 3),
    }


def hash_json_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    encoded = json.dumps(list(rows), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_duplicate_summary(rows_by_table: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    by_table: dict[str, dict[str, int]] = {}
    duplicate_event_key_count = 0
    tables_with_duplicates: list[str] = []
    for table, rows in rows_by_table.items():
        duplicate_keys = len(rows)
        duplicate_rows_over_unique = sum(max(0, int(row.get("count", 0) or 0) - 1) for row in rows)
        by_table[table] = {
            "duplicate_keys": duplicate_keys,
            "duplicate_rows_over_unique": duplicate_rows_over_unique,
        }
        duplicate_event_key_count += duplicate_keys
        if duplicate_keys:
            tables_with_duplicates.append(table)
    return {
        "duplicate_event_key_count": duplicate_event_key_count,
        "tables_with_duplicates": tables_with_duplicates,
        "by_table": by_table,
    }


def _repo_root() -> Path:
    return repo_root()


def _wait_for_http(url: str, timeout_seconds: float) -> dict[str, Any] | str:
    deadline = time.perf_counter() + timeout_seconds
    last_error: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            response = requests.get(url, timeout=2.0)
            if response.ok:
                with contextlib.suppress(Exception):
                    return response.json()
                return response.text
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def _wait_for_http_with_process(url: str, timeout_seconds: float, process: subprocess.Popen, label: str) -> dict[str, Any] | str:
    deadline = time.perf_counter() + timeout_seconds
    last_error: Exception | None = None
    while time.perf_counter() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{label} process exited before {url} became ready (returncode={process.returncode})")
        try:
            response = requests.get(url, timeout=2.0)
            if response.ok:
                with contextlib.suppress(Exception):
                    return response.json()
                return response.text
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def _initialize_sqlite_schema(sqlite_path: Path, paths: BenchmarkPaths) -> dict[str, Any]:
    schema_path = _repo_root() / "backend" / "data" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        conn.executescript(schema_sql)
        tables = [
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
    result = {
        "sqlite_path": str(sqlite_path),
        "schema_path": str(schema_path),
        "schema_sha256": hashlib.sha256(schema_sql.encode("utf-8")).hexdigest(),
        "table_count": len(tables),
        "tables": tables,
    }
    write_json(paths, "sqlite_schema_init", result)
    return result


def _request_json(url: str, params: Mapping[str, Any] | None = None, timeout_seconds: float = 30.0) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


def _write_process_log(paths: BenchmarkPaths, stem: str, process: subprocess.Popen) -> Path:
    path = paths.run_dir / f"{stem}.log"
    stdout = ""
    if process.stdout is not None:
        try:
            stdout, _stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.output or "") if isinstance(exc.output, str) else ""
        except Exception:
            stdout = ""
    path.write_text(stdout or "", encoding="utf-8", errors="replace")
    return path


def _append_progress(paths: BenchmarkPaths, message: str) -> None:
    path = paths.run_dir / "progress.log"
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def _start_backend(*, paths: BenchmarkPaths, port: int, sqlite_path: Path, tick_batch_size: int) -> subprocess.Popen:
    env = os.environ.copy()
    env.update(
        {
            "ECOSIM_ENABLE_WAREHOUSE": "1",
            "ECOSIM_WAREHOUSE_BACKEND": "sqlite",
            "ECOSIM_SQLITE_PATH": str(sqlite_path),
            "ECOSIM_TICK_BATCH_SIZE": str(max(1, tick_batch_size)),
            "PYTHONUNBUFFERED": "1",
        }
    )
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=_repo_root(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _npm_command() -> str:
    command = shutil.which("npm.cmd") or shutil.which("npm")
    if not command:
        raise FileNotFoundError("npm was not found on PATH.")
    return command


def _start_frontend(*, backend_port: int, frontend_port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["VITE_WS_URL"] = f"ws://127.0.0.1:{backend_port}/ws"
    return subprocess.Popen(
        [_npm_command(), "run", "preview", "--", "--host", "127.0.0.1", "--port", str(frontend_port)],
        cwd=_repo_root() / "frontend-react",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _build_frontend(*, paths: BenchmarkPaths, backend_port: int, timeout_seconds: float) -> Path:
    env = os.environ.copy()
    env["VITE_WS_URL"] = f"ws://127.0.0.1:{backend_port}/ws"
    path = paths.run_dir / "frontend-build.log"
    completed = subprocess.run(
        [_npm_command(), "run", "build"],
        cwd=_repo_root() / "frontend-react",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    path.write_text(completed.stdout or "", encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError(f"Frontend production build failed with code {completed.returncode}; see {path}")
    return path


def _terminate_process(process: subprocess.Popen | None) -> int | None:
    if process is None:
        return None
    if process.poll() is None:
        if os.name == "nt":
            with contextlib.suppress(Exception):
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    check=False,
                )
        else:
            process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=8)
    return process.returncode


def _wait_for_run_id(base_url: str, timeout_seconds: float) -> str:
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        with contextlib.suppress(Exception):
            payload = _request_json(f"{base_url}/warehouse/runs", timeout_seconds=5.0)
            runs = payload.get("runs") or []
            if runs:
                return str(runs[0]["run_id"])
        time.sleep(0.5)
    raise TimeoutError("Timed out waiting for a warehouse run id.")


def _wait_for_warehouse_run_finalized(
    *,
    base_url: str,
    run_id: str,
    paths: BenchmarkPaths,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    deadline = time.perf_counter() + timeout_seconds
    last_error: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            payload = _request_json(f"{base_url}/warehouse/runs", timeout_seconds=5.0)
            for run in payload.get("runs") or []:
                if str(run.get("run_id")) != run_id:
                    continue
                status = str(run.get("status", ""))
                _append_progress(paths, f"warehouse run status after Suspend status={status}")
                if status and status != "running":
                    return run
        except Exception as exc:
            last_error = exc
            _append_progress(paths, f"warehouse run status poll failed error={exc}")
        time.sleep(1.0)
    _append_progress(paths, f"warehouse run did not finalize before timeout last_error={last_error}")
    return None


def _browser_setup_state(cdp: CdpClient) -> dict[str, Any]:
    return cdp.evaluate(
        """
        (() => {
          const buttons = [...document.querySelectorAll('button')].map((el, index) => ({
            index,
            text: (el.textContent || '').replace(/\\s+/g, ' ').trim(),
            disabled: Boolean(el.disabled)
          }));
          const ranges = [...document.querySelectorAll('input[type="range"]')].map((el, index) => ({
            index,
            min: Number(el.min),
            max: Number(el.max),
            step: Number(el.step),
            value: Number(el.value)
          }));
          const numberInputs = [...document.querySelectorAll('input[type="number"]')].map((el, index) => ({
            index,
            ariaLabel: el.getAttribute('aria-label') || '',
            min: Number(el.min),
            max: Number(el.max),
            step: Number(el.step),
            value: Number(el.value)
          }));
          const launchButton = buttons.find(button => button.text.includes('Launch Simulation')) || null;
          const text = document.body ? document.body.innerText : '';
          return {
            readyState: document.readyState,
            wsConnected: text.includes('Backend Connected'),
            hasOfflineBanner: text.includes('Backend telemetry offline'),
            launchButton,
            ranges,
            numberInputs,
            wsEvents: (window.__ecosimEvidence && window.__ecosimEvidence.wsEvents || []).slice(-50),
            consoleErrors: (window.__ecosimEvidence && window.__ecosimEvidence.errors || []).slice(-20),
            bodyTextSample: text.slice(0, 500)
          };
        })()
        """,
        timeout_seconds=5.0,
    ) or {}


def _set_simulation_seed(cdp: CdpClient, seed: int) -> dict[str, Any]:
    return cdp.evaluate(
        f"""
        (() => {{
          const input = document.querySelector('input[type="number"][aria-label="Simulation seed"]');
          if (!input) {{
            return {{
              ok: false,
              reason: 'simulation seed input not found',
              numberInputs: [...document.querySelectorAll('input[type="number"]')].map((el, index) => ({{
                index,
                ariaLabel: el.getAttribute('aria-label') || '',
                min: Number(el.min),
                max: Number(el.max),
                value: Number(el.value)
              }}))
            }};
          }}
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          setter.call(input, String({seed}));
          input.dispatchEvent(new Event('input', {{ bubbles: true }}));
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
          return {{ ok: true, value: Number(input.value), min: Number(input.min), max: Number(input.max) }};
        }})()
        """,
        timeout_seconds=5.0,
    ) or {}


def _set_population_scale(cdp: CdpClient, households: int) -> dict[str, Any]:
    return cdp.evaluate(
        f"""
        (() => {{
          const input = [...document.querySelectorAll('input[type="range"]')]
            .find(el => Number(el.min) <= {households} && Number(el.max) >= {households});
          if (!input) {{
            return {{
              ok: false,
              reason: 'population range input not found',
              ranges: [...document.querySelectorAll('input[type="range"]')].map((el, index) => ({{
                index,
                min: Number(el.min),
                max: Number(el.max),
                value: Number(el.value)
              }}))
            }};
          }}
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          setter.call(input, String({households}));
          input.dispatchEvent(new Event('input', {{ bubbles: true }}));
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
          return {{ ok: true, value: Number(input.value), min: Number(input.min), max: Number(input.max) }};
        }})()
        """,
        timeout_seconds=5.0,
    ) or {}


def _click_launch_button(cdp: CdpClient) -> dict[str, Any]:
    return cdp.evaluate(
        """
        (() => {
          const button = [...document.querySelectorAll('button')]
            .find(el => el.textContent && el.textContent.includes('Launch Simulation'));
          if (!button) return { ok: false, reason: 'launch button not found' };
          if (button.disabled) return { ok: false, reason: 'launch button disabled' };
          button.click();
          return { ok: true };
        })()
        """,
        timeout_seconds=5.0,
    ) or {}


def _click_or_send_stop(cdp: CdpClient) -> dict[str, Any]:
    return cdp.evaluate(
        """
        (() => {
          const buttons = [...document.querySelectorAll('button')].map((button, index) => ({
            index,
            text: (button.textContent || '').replace(/\\s+/g, ' ').trim(),
            ariaLabel: button.getAttribute('aria-label') || '',
            disabled: Boolean(button.disabled)
          }));
          const button = [...document.querySelectorAll('button')]
            .find(el => (el.getAttribute('aria-label') || '').includes('Suspend simulation'))
            || [...document.querySelectorAll('button')]
            .find(el => (el.textContent || '').replace(/\\s+/g, ' ').trim() === 'Suspend');
          if (button && !button.disabled) {
            button.click();
            return { ok: true, method: 'ui-button', buttons };
          }
          const appSocket = window.__ecosimEvidenceAppSocket;
          if (appSocket && appSocket.readyState === WebSocket.OPEN) {
            appSocket.send(JSON.stringify({ command: 'STOP' }));
            return { ok: true, method: 'page-websocket-fallback', buttons };
          }
          return {
            ok: false,
            method: 'none',
            reason: button && button.disabled ? 'suspend button disabled' : 'suspend button not found and app websocket unavailable',
            appSocketReadyState: appSocket ? appSocket.readyState : null,
            buttons
          };
        })()
        """,
        timeout_seconds=5.0,
    ) or {}


def _wait_for_stop_sent(cdp: CdpClient, timeout_seconds: float) -> bool:
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        sent = bool(
            cdp.evaluate(
                """
                (() => {
                  const events = (window.__ecosimEvidence && window.__ecosimEvidence.wsEvents) || [];
                  return events.some(event =>
                    event.type === 'send'
                    && typeof event.payloadSample === 'string'
                    && event.payloadSample.includes('"STOP"')
                  );
                })()
                """,
                timeout_seconds=5.0,
            )
        )
        if sent:
            return True
        time.sleep(0.25)
    return False


def _wait_for_ws_message_type(cdp: CdpClient, message_type: str, timeout_seconds: float) -> bool:
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        observed = bool(
            cdp.evaluate(
                f"""
                (() => {{
                  const events = (window.__ecosimEvidence && window.__ecosimEvidence.wsEvents) || [];
                  return events.some(event => event.type === 'message' && event.parsedType === {json.dumps(message_type)});
                }})()
                """,
                timeout_seconds=5.0,
            )
        )
        if observed:
            return True
        time.sleep(0.25)
    return False


def _set_population_and_launch_through_dashboard(
    cdp: CdpClient,
    paths: BenchmarkPaths,
    households: int,
    seed: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    set_result = _set_population_scale(cdp, households)
    _append_progress(paths, f"population slider set result={json.dumps(set_result, sort_keys=True)}")
    if not set_result.get("ok"):
        raise RuntimeError(f"Could not set population scale through dashboard: {set_result}")

    seed_result = _set_simulation_seed(cdp, seed)
    _append_progress(paths, f"simulation seed input set result={json.dumps(seed_result, sort_keys=True)}")
    if not seed_result.get("ok"):
        raise RuntimeError(f"Could not set simulation seed through dashboard: {seed_result}")

    deadline = time.perf_counter() + timeout_seconds
    last_state: dict[str, Any] = {}
    last_progress_reason = ""
    while time.perf_counter() < deadline:
        state = _browser_setup_state(cdp)
        last_state = state
        launch_button = state.get("launchButton") or {}
        reason = (
            "missing launch button"
            if not launch_button
            else "launch disabled"
            if launch_button.get("disabled")
            else "launch enabled"
        )
        if reason != last_progress_reason:
            _append_progress(
                paths,
                "launch readiness "
                f"reason={reason} wsConnected={state.get('wsConnected')} "
                f"offlineBanner={state.get('hasOfflineBanner')} "
                f"button={json.dumps(launch_button, sort_keys=True)}",
            )
            last_progress_reason = reason
        if launch_button and not launch_button.get("disabled"):
            launch_result = _click_launch_button(cdp)
            _append_progress(paths, f"launch click result={json.dumps(launch_result, sort_keys=True)}")
            if launch_result.get("ok"):
                return {
                    "set_population": set_result,
                    "set_seed": seed_result,
                    "launch_state": state,
                    "launch_click": launch_result,
                }
        time.sleep(0.5)
    write_json(paths, "launch_failure", last_state)
    raise TimeoutError(f"Could not launch simulation through the dashboard. Last state: {last_state}")


def _sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(str(row[1]) == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def sqlite_table_counts(db_path: Path, run_id: str) -> dict[str, int]:
    if not db_path.exists():
        return {}
    with sqlite3.connect(db_path) as conn:
        counts: dict[str, int] = {}
        for table in _sqlite_tables(conn):
            if _table_has_column(conn, table, "run_id"):
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id = ?", (run_id,)).fetchone()[0])
            else:
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return counts


def sqlite_duplicate_rows(db_path: Path, run_id: str) -> dict[str, list[dict[str, Any]]]:
    if not db_path.exists():
        return {table: [] for table in EVENT_KEY_TABLES}
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = set(_sqlite_tables(conn))
        for table in EVENT_KEY_TABLES:
            if table not in existing_tables:
                rows_by_table[table] = []
                continue
            rows = conn.execute(
                f"""
                SELECT event_key, COUNT(*) AS count
                FROM {table}
                WHERE run_id = ?
                GROUP BY event_key
                HAVING COUNT(*) > 1
                ORDER BY event_key
                """,
                (run_id,),
            ).fetchall()
            rows_by_table[table] = [dict(row) for row in rows]
    return rows_by_table


def _collect_rest_readback(base_url: str, run_id: str) -> dict[str, Any]:
    readback: dict[str, Any] = {}
    for name, path in READBACK_ENDPOINTS.items():
        url = f"{base_url}{path.format(run_id=run_id)}"
        params = None
        try:
            payload = _request_json(url, params=params, timeout_seconds=20.0)
            readback[name] = {
                "status": "ok",
                "count": int(payload.get("count", 1 if payload else 0) or 0),
                "payload": payload,
            }
        except Exception as exc:
            readback[name] = {"status": "error", "error": str(exc), "count": 0, "payload": None}
    return readback


def _collect_browser_snapshot(cdp: CdpClient) -> dict[str, Any]:
    return cdp.evaluate(
        """
        (() => {
          const evidence = window.__ecosimEvidence || {};
          return {
            url: location.href,
            title: document.title,
            bodyTextSample: document.body ? document.body.innerText.slice(0, 800) : '',
            messages: evidence.messages || [],
            errors: evidence.errors || [],
            warnings: evidence.warnings || [],
            wsEvents: evidence.wsEvents || [],
            longTasks: evidence.longTasks || [],
            layoutShifts: evidence.layoutShifts || [],
            wsMessagesTotal: evidence.wsMessagesTotal || 0,
            topLevelKeys: evidence.topLevelKeys || {},
            metricKeys: evidence.metricKeys || {},
            lcpMs: evidence.lcpMs || 0,
            cls: evidence.cls || 0,
            renderedTickText: (() => {
              const text = document.body ? document.body.innerText : '';
              const match = text.match(/TICK\\s+([0-9]{3,})/i);
              return match ? match[1] : '';
            })(),
            memory: performance.memory ? {
              jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
              totalJSHeapSize: performance.memory.totalJSHeapSize,
              usedJSHeapSize: performance.memory.usedJSHeapSize
            } : null
          };
        })()
        """,
        timeout_seconds=15.0,
    )


def _run_browser_flow(
    *,
    paths: BenchmarkPaths,
    frontend_url: str,
    backend_url: str,
    sqlite_path: Path,
    households: int,
    seed: int,
    ticks: int,
    live_check_tick: int,
    chrome_path: str | None,
    remote_debugging_port: int,
    viewport: str,
    timeout_seconds: float,
    headless: bool,
    cycle_views: list[str],
    view_cycle_interval: int,
) -> dict[str, Any]:
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
    run_id: str | None = None
    midrun_counts: dict[str, int] | None = None
    midrun_tick = 0
    try:
        _append_progress(paths, f"waiting for Chrome CDP port={port}")
        version = _wait_for_json(f"http://127.0.0.1:{port}/json/version", timeout_seconds=timeout_seconds)
        tab = _open_cdp_tab(port)
        cdp = CdpClient(tab["webSocketDebuggerUrl"], timeout_seconds=min(10.0, timeout_seconds))
        # The full run may have a long overall timeout, but individual CDP calls
        # should fail quickly so the harness can record useful progress.
        with contextlib.suppress(Exception):
            cdp._ws.settimeout(5.0)
        _append_progress(paths, f"connected to browser={version.get('Browser', 'unknown')}")
        cdp.command("Runtime.enable")
        cdp.command("Page.enable")
        cdp.command("Log.enable")
        cdp.command("Performance.enable")
        width, height = [int(part) for part in viewport.lower().split("x", 1)]
        cdp.command(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
        )
        cdp.command("Page.addScriptToEvaluateOnNewDocument", {"source": FULL_APP_INSTRUMENTATION})
        _append_progress(paths, f"navigating frontend url={frontend_url}")
        cdp.command("Page.navigate", {"url": frontend_url})
        _wait_for_page_ready(cdp, timeout_seconds)
        _append_progress(paths, "frontend page ready")
        launch_details = _set_population_and_launch_through_dashboard(cdp, paths, households, seed, timeout_seconds)
        _append_progress(paths, f"launch clicked households={households} seed={seed}")
        run_id = _wait_for_run_id(backend_url, timeout_seconds)
        _append_progress(paths, f"warehouse run observed run_id={run_id}")

        next_view_index = 0
        next_view_threshold = view_cycle_interval if cycle_views else ticks + 1
        last_progress_count = -1
        deadline = time.perf_counter() + timeout_seconds
        while time.perf_counter() < deadline:
            message_count = int(
                cdp.evaluate(
                    "(window.__ecosimEvidence && window.__ecosimEvidence.messages.length) || 0",
                    timeout_seconds=5.0,
                )
                or 0
            )
            if message_count != last_progress_count and (
                message_count <= 3 or message_count % max(1, min(10, ticks)) == 0
            ):
                _append_progress(paths, f"browser stream messages={message_count}")
                last_progress_count = message_count
            if midrun_counts is None and message_count >= live_check_tick:
                midrun_tick = message_count
                midrun_counts = sqlite_table_counts(sqlite_path, run_id)
                _append_progress(paths, f"midrun sqlite counts at messages={message_count}: tick_metrics={midrun_counts.get('tick_metrics', 0)}")
            if message_count >= ticks:
                break
            if cycle_views and message_count >= next_view_threshold:
                _click_view(cdp, cycle_views[next_view_index % len(cycle_views)])
                next_view_index += 1
                next_view_threshold += max(1, view_cycle_interval)
            time.sleep(0.5)
        else:
            raise TimeoutError(f"Timed out waiting for {ticks} frontend tick messages.")

        _append_progress(paths, "target tick messages observed; sending STOP")
        stop_result = _click_or_send_stop(cdp)
        _append_progress(paths, f"stop command result={json.dumps(stop_result, sort_keys=True)}")
        stop_sent = _wait_for_stop_sent(cdp, timeout_seconds=10.0)
        _append_progress(paths, f"stop command observed by websocket instrumentation={stop_sent}")
        stop_ack = _wait_for_ws_message_type(cdp, "STOPPED", timeout_seconds=10.0)
        _append_progress(paths, f"STOPPED message observed by websocket instrumentation={stop_ack}")
        time.sleep(1.0)
        _append_progress(paths, "collecting browser snapshot")
        _click_view(cdp, "Command")
        snapshot = _collect_browser_snapshot(cdp)
        screenshot = cdp.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        screenshot_path = paths.run_dir / "frontend-final.png"
        screenshot_path.write_bytes(base64.b64decode(screenshot["data"]))
        _append_progress(paths, "browser snapshot captured after Suspend")
        time.sleep(2.0)
        return {
            "run_id": run_id,
            "browser_product": version.get("Browser", "unknown"),
            "chrome_path": str(resolved_chrome),
            "snapshot": snapshot,
            "console_rows": list(cdp.console_rows),
            "screenshot": str(screenshot_path),
            "midrun_tick": midrun_tick,
            "midrun_counts": midrun_counts or {},
            "launch_details": launch_details,
            "stop_result": stop_result,
            "stop_sent": stop_sent,
            "stop_ack": stop_ack,
        }
    finally:
        if cdp is not None:
            with contextlib.suppress(Exception):
                cdp.close()
        _terminate_process(process)


def _render_claim_ledger(
    *,
    metadata: Mapping[str, Any],
    stream_summary: Mapping[str, Any],
    browser_performance: Mapping[str, Any],
    readback: Mapping[str, Any],
    table_counts: Mapping[str, int],
    duplicate_summary: Mapping[str, Any],
    midrun_counts: Mapping[str, int],
    tick_hash: str,
    artifacts: Mapping[str, Any],
) -> str:
    run_id = metadata.get("run_id", "unknown")
    llm_rows = int(table_counts.get("llm_government_decisions", 0) or 0)
    tick_rows = int(table_counts.get("tick_metrics", 0) or 0)
    decision_rows = int(table_counts.get("decision_features", 0) or 0)
    midrun_tick_rows = int(midrun_counts.get("tick_metrics", 0) or 0)
    lines = [
        "# EcoSim Full App Evidence Run",
        "",
        "## Runtime",
        "",
        f"- Run id: `{run_id}`",
        f"- Households: `{metadata.get('households')}`",
        f"- Firms/category: `{metadata.get('firms_per_category')}` ({metadata.get('firms_per_category_source')})",
        f"- Seed: `{metadata.get('seed')}` ({metadata.get('seed_source')})",
        f"- Target ticks: `{metadata.get('ticks')}`",
        f"- Finalized run status: `{metadata.get('finalized_run_status')}`",
        f"- Finalized total ticks / persisted watermark: `{metadata.get('finalized_run_total_ticks')}` / `{metadata.get('finalized_run_last_fully_persisted_tick')}`",
        f"- Stop method / STOP sent / STOPPED ack: `{(metadata.get('stop_result') or {}).get('method', '')}` / `{metadata.get('stop_sent')}` / `{metadata.get('stop_ack')}`",
        f"- Backend URL: `{metadata.get('backend_url')}`",
        f"- Frontend URL: `{metadata.get('frontend_url')}`",
        f"- Frontend mode: `{metadata.get('frontend_mode')}`",
        f"- SQLite DB: `{metadata.get('sqlite_path')}`",
        f"- LLM government: `disabled by setup/config; zero decision rows expected`",
        "",
        "## Stream Performance",
        "",
        f"- Frames: `{stream_summary.get('frame_count')}`",
        f"- Tick range: `{stream_summary.get('first_tick')}..{stream_summary.get('last_tick')}`",
        f"- Duration: `{stream_summary.get('duration_seconds')} s`",
        f"- Frames/sec: `{stream_summary.get('frames_per_second')}`",
        f"- Payload bytes p50/p95/max: `{stream_summary.get('payload_bytes', {}).get('p50')}` / `{stream_summary.get('payload_bytes', {}).get('p95')}` / `{stream_summary.get('payload_bytes', {}).get('max')}`",
        f"- Total streamed bytes: `{stream_summary.get('payload_bytes', {}).get('total')}`",
        f"- Backend tick compute p50/p95: `{browser_performance.get('p50_backend_tick_compute_ms')} ms` / `{browser_performance.get('p95_backend_tick_compute_ms')} ms`",
        f"- Browser parse p50/p95: `{browser_performance.get('p50_parse_ms')} ms` / `{browser_performance.get('p95_parse_ms')} ms`",
        f"- Next-frame p50/p95: `{browser_performance.get('p50_next_frame_ms')} ms` / `{browser_performance.get('p95_next_frame_ms')} ms`",
        f"- Long tasks: `{browser_performance.get('long_task_count')}`",
        "",
        "## Warehouse Evidence",
        "",
        f"- Mid-run tick_metrics rows before STOP: `{midrun_tick_rows}`",
        f"- Final tick_metrics rows: `{tick_rows}`",
        f"- Final decision_features rows: `{decision_rows}`",
        f"- REST tick metrics count: `{readback.get('tick_metrics', {}).get('count')}`",
        f"- REST LLM decision count: `{readback.get('llm_government_decisions', {}).get('count')}`",
        f"- Tick metrics SHA256: `{tick_hash}`",
        f"- Duplicate event keys: `{duplicate_summary.get('duplicate_event_key_count')}`",
        "",
        "## Claim Ledger",
        "",
        "Claim: React dashboard loads and observes the live stream.",
        "Validity: Direct / Strong.",
        f"Evidence: browser frames={stream_summary.get('frame_count')}, final_tick={stream_summary.get('last_tick')}, console_rows={metadata.get('console_row_count')}.",
        f"Artifact: `{artifacts.get('screenshot')}`",
        "Still separate or unproven: this does not cover every dashboard view or click workflow.",
        "",
        "Claim: Server runs a real simulation through `/ws`.",
        "Validity: Direct / Strong.",
        f"Evidence: real browser WebSocket tick range {stream_summary.get('first_tick')}..{stream_summary.get('last_tick')} with backend tick compute p95 {browser_performance.get('p95_backend_tick_compute_ms')} ms.",
        f"Artifact: `{artifacts.get('stream_rows_csv')}`",
        "Still separate or unproven: policy variants beyond default/rule-based policy are not covered.",
        "",
        "Claim: WebSocket stream performance is measurable under the full app path.",
        "Validity: Direct / Strong.",
        f"Evidence: total_payload_bytes={stream_summary.get('payload_bytes', {}).get('total')}, p95_payload_bytes={stream_summary.get('payload_bytes', {}).get('p95')}, frames_per_second={stream_summary.get('frames_per_second')}.",
        f"Artifact: `{artifacts.get('raw_json')}`",
        "Still separate or unproven: this is one machine/browser/viewport run, not a cross-browser benchmark.",
        "",
        "Claim: Warehouse rows are written during the live run.",
        "Validity: Direct / Strong." if midrun_tick_rows > 0 else "Validity: Direct / Partial.",
        f"Evidence: mid-run tick_metrics rows before STOP={midrun_tick_rows}; final tick_metrics rows={tick_rows}.",
        f"Artifact: `{artifacts.get('sqlite_counts_csv')}`",
        "Still separate or unproven: Postgres live persistence is not covered.",
        "",
        "Claim: REST endpoints return persisted data from the same run.",
        "Validity: Direct / Strong." if readback.get("tick_metrics", {}).get("count") else "Validity: Not proven.",
        f"Evidence: run_id={run_id}, REST tick_metrics count={readback.get('tick_metrics', {}).get('count')}, summary status={readback.get('summary', {}).get('status')}.",
        f"Artifact: `{artifacts.get('rest_readback_json')}`",
        "Still separate or unproven: REST correctness is sampled by endpoint counts and hash, not exhaustive schema validation.",
        "",
        "Claim: LLM government is disabled and LLM decision rows are not expected.",
        "Validity: Direct / Strong." if llm_rows == 0 else "Validity: Failed.",
        f"Evidence: setup sends enable_llm_government=false; llm_government_decisions rows={llm_rows}.",
        f"Artifact: `{artifacts.get('sqlite_counts_csv')}`",
        "Still separate or unproven: LLM government behavior is intentionally excluded.",
        "",
        "Claim: Forecasting is integrated with this live-persisted run.",
        "Validity: Not proven.",
        "Evidence: current forecasting pipeline consumes offline Parquet sweep artifacts, not this live SQLite run.",
        "Artifact: repository source inventory from Part 1.",
        "Still separate or unproven: live warehouse-to-forecasting adapter is separate future work.",
        "",
    ]
    return "\n".join(lines)


def _rows_from_mapping(mapping: Mapping[str, int], key_name: str = "table") -> list[dict[str, Any]]:
    return [{key_name: key, "row_count": value} for key, value in sorted(mapping.items())]


def run_full_app_evidence(
    *,
    households: int,
    firms_per_category: int,
    ticks: int,
    seed: int,
    output_root: Path,
    chrome_path: str | None,
    viewport: str,
    timeout_seconds: float,
    headed: bool,
    tick_batch_size: int,
    cycle_views: list[str],
    view_cycle_interval: int,
) -> dict[str, Any]:
    if firms_per_category != FRONTEND_DEFAULT_FIRMS_PER_CATEGORY:
        raise ValueError(
            "The current React dashboard does not expose a firm-count control. "
            f"Use --firms-per-category {FRONTEND_DEFAULT_FIRMS_PER_CATEGORY} for the real app path, "
            "or add a visible frontend control before claiming another value."
        )
    paths = BenchmarkPaths.create(output_root, "full-app-evidence")
    backend_port = _free_port()
    frontend_port = _free_port()
    sqlite_path = paths.run_dir / "full_app_evidence.sqlite3"
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    backend: subprocess.Popen | None = None
    frontend: subprocess.Popen | None = None
    backend_returncode: int | None = None
    frontend_returncode: int | None = None
    try:
        schema_init = _initialize_sqlite_schema(sqlite_path, paths)
        _append_progress(
            paths,
            f"sqlite schema initialized tables={schema_init['table_count']} sha256={schema_init['schema_sha256']}",
        )
        _append_progress(paths, f"starting backend port={backend_port} sqlite={sqlite_path}")
        backend = _start_backend(paths=paths, port=backend_port, sqlite_path=sqlite_path, tick_batch_size=tick_batch_size)
        _wait_for_http_with_process(f"{backend_url}/health", timeout_seconds=timeout_seconds, process=backend, label="backend")
        _append_progress(paths, "backend health ready")
        _append_progress(paths, "building production frontend with run websocket url")
        frontend_build_log = _build_frontend(paths=paths, backend_port=backend_port, timeout_seconds=timeout_seconds)
        _append_progress(paths, f"frontend build ready log={frontend_build_log}")
        _append_progress(paths, f"starting frontend preview port={frontend_port}")
        frontend = _start_frontend(backend_port=backend_port, frontend_port=frontend_port)
        _wait_for_http_with_process(frontend_url, timeout_seconds=timeout_seconds, process=frontend, label="frontend")
        _append_progress(paths, "frontend http ready")

        browser_result = _run_browser_flow(
            paths=paths,
            frontend_url=frontend_url,
            backend_url=backend_url,
            sqlite_path=sqlite_path,
            households=households,
            seed=seed,
            ticks=ticks,
            live_check_tick=max(1, min(ticks, max(5, ticks // 2))),
            chrome_path=chrome_path,
            remote_debugging_port=0,
            viewport=viewport,
            timeout_seconds=timeout_seconds,
            headless=not headed,
            cycle_views=cycle_views,
            view_cycle_interval=max(1, view_cycle_interval),
        )
        run_id = str(browser_result["run_id"])

        # _run_browser_flow closes Chrome in its finally block. That closes the
        # WebSocket, and the backend marks the warehouse run stopped there.
        time.sleep(2.0)
        finalized_run = _wait_for_warehouse_run_finalized(
            base_url=backend_url,
            run_id=run_id,
            paths=paths,
            timeout_seconds=min(120.0, timeout_seconds),
        )
        table_counts = sqlite_table_counts(sqlite_path, run_id)
        duplicate_rows = sqlite_duplicate_rows(sqlite_path, run_id)
        duplicate_summary = compute_duplicate_summary(duplicate_rows)
        if finalized_run is None:
            readback = {
                name: {
                    "status": "error",
                    "error": "warehouse run did not leave running state before REST readback",
                    "count": 0,
                    "payload": None,
                }
                for name in READBACK_ENDPOINTS
            }
        else:
            readback = _collect_rest_readback(backend_url, run_id)
        tick_metric_rows = (readback.get("tick_metrics", {}).get("payload") or {}).get("tickMetrics") or []
        tick_hash = hash_json_rows(tick_metric_rows)

        snapshot = browser_result["snapshot"]
        stream_rows = list(snapshot.get("messages", []))[:ticks]
        long_tasks = list(snapshot.get("longTasks", []))
        stream_summary = summarize_stream_rows(stream_rows)
        browser_performance = summarize_browser_performance(stream_rows, long_tasks, snapshot)
        console_rows = list(browser_result.get("console_rows", []))
        browser_error_rows = list(snapshot.get("errors", []))
        finalized_run = finalized_run or {}

        metadata = collect_metadata(
            {
                "kind": "full-app-evidence",
                "run_id": run_id,
                "households": households,
                "firms_per_category": firms_per_category,
                "ticks": ticks,
                "seed": seed,
                "backend_url": backend_url,
                "frontend_url": frontend_url,
                "frontend_mode": "vite production build served by vite preview",
                "sqlite_path": str(sqlite_path),
                "sqlite_schema_sha256": schema_init["schema_sha256"],
                "sqlite_schema_table_count": schema_init["table_count"],
                "tick_batch_size": tick_batch_size,
                "seed_source": "visible dashboard seed control sent in SETUP config",
                "firms_per_category_source": "frontend setupConfig.num_firms default; no visible dashboard firm-count control",
                "llm_scope": "excluded; frontend setupConfig.enable_llm_government is false by default",
                "viewport": viewport,
                "headless": not headed,
                "browser_product": browser_result.get("browser_product", "unknown"),
                "chrome_path": browser_result.get("chrome_path", ""),
                "finalized_run_status": finalized_run.get("status", ""),
                "finalized_run_total_ticks": finalized_run.get("total_ticks", None),
                "finalized_run_last_fully_persisted_tick": finalized_run.get("last_fully_persisted_tick", None),
                "stop_result": browser_result.get("stop_result", {}),
                "stop_sent": browser_result.get("stop_sent", False),
                "stop_ack": browser_result.get("stop_ack", False),
                "console_row_count": len(console_rows),
                "browser_error_count": len(browser_error_rows),
                "launch_details": browser_result.get("launch_details", {}),
            }
        )

        stream_rows_csv = write_rows_csv(paths, "websocket_stream_rows", stream_rows)
        console_csv = write_rows_csv(paths, "browser_console_rows", console_rows)
        browser_errors_csv = write_rows_csv(paths, "browser_error_rows", browser_error_rows)
        sqlite_counts_csv = write_rows_csv(paths, "sqlite_table_counts", _rows_from_mapping(table_counts))
        midrun_counts_csv = write_rows_csv(paths, "sqlite_midrun_table_counts", _rows_from_mapping(browser_result.get("midrun_counts", {})))
        duplicate_rows_csv = write_rows_csv(
            paths,
            "duplicate_event_keys",
            [
                {"table": table, **row}
                for table, rows in duplicate_rows.items()
                for row in rows
            ],
        )
        rest_readback_json = write_json(paths, "rest_readback", readback)
        raw_json = write_json(
            paths,
            "raw",
            {
                "metadata": metadata,
                "stream_summary": stream_summary,
                "browser_performance": browser_performance,
                "snapshot": snapshot,
                "console_rows": console_rows,
                "browser_error_rows": browser_error_rows,
                "table_counts": table_counts,
                "midrun_counts": browser_result.get("midrun_counts", {}),
                "duplicate_rows": duplicate_rows,
                "duplicate_summary": duplicate_summary,
                "tick_metrics_sha256": tick_hash,
            },
        )
        artifacts = {
            "stream_rows_csv": str(stream_rows_csv),
            "console_csv": str(console_csv),
            "browser_errors_csv": str(browser_errors_csv),
            "sqlite_counts_csv": str(sqlite_counts_csv),
            "midrun_counts_csv": str(midrun_counts_csv),
            "duplicate_rows_csv": str(duplicate_rows_csv),
            "rest_readback_json": str(rest_readback_json),
            "raw_json": str(raw_json),
            "screenshot": browser_result.get("screenshot"),
            "frontend_build_log": str(paths.run_dir / "frontend-build.log"),
            "sqlite_schema_init": str(paths.run_dir / "sqlite_schema_init.json"),
        }
        summary_md = write_markdown(
            paths,
            "summary",
            _render_claim_ledger(
                metadata=metadata,
                stream_summary=stream_summary,
                browser_performance=browser_performance,
                readback=readback,
                table_counts=table_counts,
                duplicate_summary=duplicate_summary,
                midrun_counts=browser_result.get("midrun_counts", {}),
                tick_hash=tick_hash,
                artifacts=artifacts,
            ),
        )
        artifacts["summary_md"] = str(summary_md)
        return {
            "paths": paths,
            "metadata": metadata,
            "stream_summary": stream_summary,
            "browser_performance": browser_performance,
            "readback": readback,
            "table_counts": table_counts,
            "duplicate_summary": duplicate_summary,
            "tick_metrics_sha256": tick_hash,
            "artifacts": artifacts,
        }
    finally:
        frontend_returncode = _terminate_process(frontend)
        backend_returncode = _terminate_process(backend)
        if backend is not None:
            backend_log = _write_process_log(paths, "backend", backend)
        else:
            backend_log = None
        if frontend is not None:
            frontend_log = _write_process_log(paths, "frontend", frontend)
        else:
            frontend_log = None
        write_json(
            paths,
            "processes",
            {
                "backend_returncode": backend_returncode,
                "frontend_returncode": frontend_returncode,
                "backend_log": str(backend_log) if backend_log else None,
                "frontend_log": str(frontend_log) if frontend_log else None,
            },
        )


def _parse_view_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the EcoSim full app evidence harness.")
    parser.add_argument("--households", type=int, default=10000)
    parser.add_argument(
        "--firms-per-category",
        type=int,
        default=FRONTEND_DEFAULT_FIRMS_PER_CATEGORY,
        help="Must match the current dashboard default; the React UI does not expose this as a control.",
    )
    parser.add_argument("--ticks", type=int, default=50)
    parser.add_argument(
        "--seed",
        type=int,
        default=FRONTEND_DEFAULT_SEED,
        help="Must match the current dashboard/backend default; the React UI does not expose this as a control.",
    )
    parser.add_argument("--output-root", type=Path, default=default_results_root())
    parser.add_argument("--chrome-path", default=None)
    parser.add_argument("--viewport", default="1440x1000")
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--tick-batch-size", type=int, default=5)
    parser.add_argument(
        "--cycle-views",
        default="Command,Population,Markets,Finance,Government,Logs",
        help="Comma-separated dashboard nav labels to click during the run. Empty disables cycling.",
    )
    parser.add_argument("--view-cycle-interval", type=int, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_full_app_evidence(
        households=args.households,
        firms_per_category=args.firms_per_category,
        ticks=args.ticks,
        seed=args.seed,
        output_root=args.output_root,
        chrome_path=args.chrome_path,
        viewport=args.viewport,
        timeout_seconds=args.timeout_seconds,
        headed=args.headed,
        tick_batch_size=args.tick_batch_size,
        cycle_views=_parse_view_list(args.cycle_views),
        view_cycle_interval=args.view_cycle_interval,
    )
    print(f"Wrote full app evidence artifacts to {result['paths'].run_dir}")
    print(f"run_id: {result['metadata']['run_id']}")
    print(f"frames: {result['stream_summary']['frame_count']} final_tick: {result['stream_summary']['last_tick']}")
    print(f"tick_metrics rows: {result['table_counts'].get('tick_metrics', 0)}")
    print(f"p95 payload bytes: {result['stream_summary']['payload_bytes']['p95']}")
    print(f"p95 backend tick compute ms: {result['browser_performance']['p95_backend_tick_compute_ms']}")
    print(f"summary: {result['artifacts']['summary_md']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
