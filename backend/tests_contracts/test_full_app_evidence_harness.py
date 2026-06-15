import hashlib

import pytest

import tools.integration.run_full_app_evidence as full_app
from tools.integration.run_full_app_evidence import (
    compute_duplicate_summary,
    hash_json_rows,
    run_full_app_evidence,
    summarize_stream_rows,
)


def test_summarize_stream_rows_reports_ticks_payloads_and_rate():
    rows = [
        {"tick": 1, "receivedAtMs": 1000.0, "payloadBytes": 100, "trackedSubjects": 3, "trackedFirms": 2},
        {"tick": 2, "receivedAtMs": 1500.0, "payloadBytes": 200, "trackedSubjects": 4, "trackedFirms": 3},
        {"tick": 3, "receivedAtMs": 2000.0, "payloadBytes": 1000, "trackedSubjects": 5, "trackedFirms": 4},
    ]

    summary = summarize_stream_rows(rows)

    assert summary["frame_count"] == 3
    assert summary["first_tick"] == 1
    assert summary["last_tick"] == 3
    assert summary["duration_seconds"] == 1.0
    assert summary["frames_per_second"] == 3.0
    assert summary["payload_bytes"]["min"] == 100
    assert summary["payload_bytes"]["p50"] == 200
    assert summary["payload_bytes"]["p95"] == 1000
    assert summary["payload_bytes"]["max"] == 1000
    assert summary["payload_bytes"]["total"] == 1300
    assert summary["max_tracked_subjects"] == 5
    assert summary["max_tracked_firms"] == 4


def test_hash_json_rows_is_stable_for_key_order():
    left = [{"tick": 1, "gdp": 10.5}, {"tick": 2, "gdp": 11.0}]
    right = [{"gdp": 10.5, "tick": 1}, {"gdp": 11.0, "tick": 2}]

    digest = hash_json_rows(left)

    assert digest == hash_json_rows(right)
    assert digest == hashlib.sha256(
        b'[{"gdp":10.5,"tick":1},{"gdp":11.0,"tick":2}]'
    ).hexdigest()


def test_compute_duplicate_summary_counts_duplicate_event_keys():
    rows_by_table = {
        "labor_events": [{"event_key": "a", "count": 2}, {"event_key": "b", "count": 3}],
        "healthcare_events": [],
        "policy_actions": [{"event_key": "p", "count": 2}],
    }

    summary = compute_duplicate_summary(rows_by_table)

    assert summary["duplicate_event_key_count"] == 3
    assert summary["tables_with_duplicates"] == ["labor_events", "policy_actions"]
    assert summary["by_table"]["labor_events"]["duplicate_keys"] == 2
    assert summary["by_table"]["labor_events"]["duplicate_rows_over_unique"] == 3
    assert summary["by_table"]["healthcare_events"]["duplicate_keys"] == 0


def test_run_full_app_evidence_rejects_unclaimed_frontend_controls(tmp_path):
    with pytest.raises(ValueError, match="does not expose a firm-count control"):
        run_full_app_evidence(
            households=100,
            firms_per_category=10,
            ticks=1,
            seed=42,
            output_root=tmp_path,
            chrome_path=None,
            viewport="800x600",
            timeout_seconds=1,
            headed=False,
            tick_batch_size=1,
            cycle_views=[],
            view_cycle_interval=1,
        )


def test_run_full_app_evidence_passes_seed_to_dashboard_flow(monkeypatch, tmp_path):
    observed: dict[str, int] = {}

    monkeypatch.setattr(
        full_app,
        "_initialize_sqlite_schema",
        lambda sqlite_path, paths: {"table_count": 1, "schema_sha256": "schema-hash"},
    )
    monkeypatch.setattr(full_app, "_free_port", lambda: 51000)
    monkeypatch.setattr(full_app, "_start_backend", lambda **kwargs: object())
    monkeypatch.setattr(full_app, "_start_frontend", lambda **kwargs: object())
    monkeypatch.setattr(full_app, "_wait_for_http_with_process", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(full_app, "_build_frontend", lambda **kwargs: tmp_path / "frontend-build.log")
    monkeypatch.setattr(full_app, "_terminate_process", lambda process: 0)
    monkeypatch.setattr(full_app, "_write_process_log", lambda paths, stem, process: paths.run_dir / f"{stem}.log")
    monkeypatch.setattr(full_app, "_wait_for_warehouse_run_finalized", lambda **kwargs: {"status": "stopped", "total_ticks": 1})
    monkeypatch.setattr(full_app, "sqlite_table_counts", lambda sqlite_path, run_id: {
        "tick_metrics": 1,
        "decision_features": 1,
        "llm_government_decisions": 0,
    })
    monkeypatch.setattr(full_app, "sqlite_duplicate_rows", lambda sqlite_path, run_id: {})
    monkeypatch.setattr(full_app, "_collect_rest_readback", lambda base_url, run_id: {
        "tick_metrics": {"count": 1, "payload": {"tickMetrics": [{"tick": 0, "gdp": 1.0}]}},
        "summary": {"status": "ok", "count": 1, "payload": {}},
        "llm_government_decisions": {"count": 0, "payload": []},
    })

    def fake_browser_flow(**kwargs):
        observed["seed"] = kwargs["seed"]
        return {
            "run_id": "run_seed_7",
            "snapshot": {"messages": [], "longTasks": [], "errors": []},
            "console_rows": [],
            "midrun_counts": {"tick_metrics": 1},
            "browser_product": "fake",
            "chrome_path": "fake-chrome",
            "stop_result": {"method": "ui-button"},
            "stop_sent": True,
            "stop_ack": True,
            "launch_details": {"set_seed": {"ok": True, "value": 7}},
            "screenshot": str(tmp_path / "frontend-final.png"),
        }

    monkeypatch.setattr(full_app, "_run_browser_flow", fake_browser_flow)

    result = run_full_app_evidence(
        households=100,
        firms_per_category=5,
        ticks=1,
        seed=7,
        output_root=tmp_path,
        chrome_path=None,
        viewport="800x600",
        timeout_seconds=1,
        headed=False,
        tick_batch_size=1,
        cycle_views=[],
        view_cycle_interval=1,
    )

    assert observed["seed"] == 7
    assert result["metadata"]["seed"] == 7
    assert result["metadata"]["seed_source"] == "visible dashboard seed control sent in SETUP config"
