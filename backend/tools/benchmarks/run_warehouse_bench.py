"""Warehouse ingest/query benchmark CLI.

Examples:
    python -m backend.tools.benchmarks.run_warehouse_bench --backend sqlite --households 1000 --ticks 40
    python -m backend.tools.benchmarks.run_warehouse_bench --backend postgres --households 1000 --ticks 40
"""

from __future__ import annotations

import argparse
import contextlib
import io
import random
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG
from data.db_manager import DatabaseManager
from data.models import (
    DecisionFeature,
    FirmSnapshot,
    HouseholdSnapshot,
    SectorTickMetrics,
    SimulationRun,
    TickMetrics,
)
from data.postgres_manager import PostgresDatabaseManager
from tools.runners.run_large_simulation import (
    compute_firm_snapshot_rows,
    compute_household_snapshot_rows,
    compute_household_stats,
    compute_sector_tick_rollups,
    create_large_economy,
)

from .common import (
    BenchmarkPaths,
    build_run_id,
    collect_metadata,
    default_results_root,
    percentile,
    parse_int_list,
    repo_root,
    write_json,
    write_markdown,
    write_rows_csv,
)
from .reporting import render_warehouse_summary, summarize_warehouse_rows


def _file_size_bytes(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    return int(path.stat().st_size)


def _sqlite_file_sizes(db_path: Path | None) -> dict[str, int]:
    if db_path is None:
        return {}
    return {
        "db_file_bytes": _file_size_bytes(db_path),
        "wal_file_bytes": _file_size_bytes(Path(f"{db_path}-wal")),
        "shm_file_bytes": _file_size_bytes(Path(f"{db_path}-shm")),
    }


def _sqlite_pragmas(manager: Any, db_path: Path | None) -> dict[str, Any]:
    if db_path is None or not isinstance(manager.conn, sqlite3.Connection):
        return {}
    cursor = manager.conn.cursor()
    page_count = int(cursor.execute("PRAGMA page_count").fetchone()[0])
    page_size = int(cursor.execute("PRAGMA page_size").fetchone()[0])
    freelist_count = int(cursor.execute("PRAGMA freelist_count").fetchone()[0])
    journal_mode = str(cursor.execute("PRAGMA journal_mode").fetchone()[0])
    synchronous = int(cursor.execute("PRAGMA synchronous").fetchone()[0])
    return {
        **_sqlite_file_sizes(db_path),
        "page_count": page_count,
        "page_size": page_size,
        "freelist_count": freelist_count,
        "logical_db_bytes": page_count * page_size,
        "journal_mode": journal_mode,
        "synchronous": synchronous,
    }


def _table_counts(manager: Any, run_id: str) -> dict[str, int]:
    rows = manager.execute_query(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    counts: dict[str, int] = {}
    for row in rows:
        table = str(row["name"])
        columns = {
            str(column["name"])
            for column in manager.execute_query(f"PRAGMA table_info({table})")
        }
        if "run_id" in columns:
            count_row = manager.execute_query(
                f"SELECT COUNT(*) AS count FROM {table} WHERE run_id = ?",
                (run_id,),
            )[0]
        else:
            count_row = manager.execute_query(f"SELECT COUNT(*) AS count FROM {table}")[0]
        counts[table] = int(count_row["count"])
    return counts


def _timed_query(query_name: str, func) -> dict[str, Any]:
    started = time.perf_counter()
    result = func()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    try:
        result_count = len(result)
    except TypeError:
        result_count = 1 if result else 0
    return {
        "query_name": query_name,
        "query_ms": round(elapsed_ms, 3),
        "result_count": int(result_count),
    }


def _query_suite(manager: Any, run_id: str, ticks: int, household_snapshot_stride: int) -> list[dict[str, Any]]:
    last_tick = max(0, ticks - 1)
    recent_start = max(0, last_tick - 25)
    snapshot_stride = max(1, int(household_snapshot_stride))
    latest_household_snapshot_tick = last_tick - (last_tick % snapshot_stride)
    return [
        _timed_query("run_summary", lambda: manager.get_run_summary(run_id)),
        _timed_query(
            "recent_tick_metrics",
            lambda: manager.get_tick_metrics(run_id, tick_start=recent_start, tick_end=last_tick),
        ),
        _timed_query(
            "sector_rollup_full_run",
            lambda: manager.get_sector_summary(run_id, tick_start=0, tick_end=last_tick),
        ),
        _timed_query(
            "firm_snapshots_latest",
            lambda: manager.get_firm_snapshots(run_id, tick_start=last_tick, tick_end=last_tick),
        ),
        _timed_query(
            "household_snapshots_latest_sample",
            lambda: manager.get_household_snapshots(
                run_id,
                tick_start=latest_household_snapshot_tick,
                tick_end=latest_household_snapshot_tick,
            ),
        ),
        _timed_query(
            "decision_features_recent",
            lambda: manager.get_decision_features(run_id, tick_start=recent_start, tick_end=last_tick),
        ),
    ]


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    CONFIG.random_seed = int(seed)


def _create_economy_quietly(num_households: int, firms_per_category: int, verbose: bool):
    if verbose:
        return create_large_economy(num_households, firms_per_category)
    with contextlib.redirect_stdout(io.StringIO()):
        return create_large_economy(num_households, firms_per_category)


def _create_manager(backend: str, paths: BenchmarkPaths):
    backend = backend.strip().lower()
    if backend == "sqlite":
        db_path = paths.run_dir / "warehouse_bench.sqlite3"
        manager = DatabaseManager(str(db_path))
        schema_path = repo_root() / "backend" / "data" / "schema.sql"
        manager.conn.executescript(schema_path.read_text(encoding="utf-8"))
        manager.conn.commit()
        return manager, db_path
    if backend in {"postgres", "postgresql", "timescale", "timescaledb"}:
        manager = PostgresDatabaseManager()
        manager.apply_schema()
        return manager, None
    raise ValueError(f"Unsupported warehouse backend: {backend}")


def _tick_metric(run_id: str, tick: int, metrics: dict[str, Any], stats: dict[str, Any], tick_duration_ms: float) -> TickMetrics:
    return TickMetrics(
        run_id=run_id,
        tick=tick,
        gdp=float(metrics.get("gdp_this_tick", 0.0)),
        unemployment_rate=float(stats.get("unemployment_rate", metrics.get("unemployment_rate", 0.0))),
        mean_wage=float(stats.get("mean_wage", metrics.get("mean_wage", 0.0))),
        median_wage=float(stats.get("median_wage", metrics.get("median_wage", 0.0))),
        avg_happiness=float(stats.get("mean_happiness", metrics.get("mean_happiness", 0.0))),
        avg_health=float(stats.get("mean_health", metrics.get("mean_health", 0.0))),
        avg_morale=float(stats.get("mean_morale", metrics.get("mean_morale", 0.0))),
        total_net_worth=float(metrics.get("total_net_worth", metrics.get("total_economy_cash", 0.0))),
        gini_coefficient=float(stats.get("gini_coefficient", metrics.get("gini_coefficient", 0.0))),
        top10_wealth_share=float(stats.get("top10_wealth_share", metrics.get("top_10_percent_share", 0.0))),
        bottom50_wealth_share=float(stats.get("bottom50_wealth_share", metrics.get("bottom_50_percent_share", 0.0))),
        gov_cash_balance=float(metrics.get("government_cash", 0.0)),
        gov_profit=float(metrics.get("gov_net_flow_this_tick", 0.0)),
        total_firms=int(metrics.get("total_firms", 0)),
        struggling_firms=int(metrics.get("struggling_firms", metrics.get("firm_survival_mode_count", 0))),
        tick_duration_ms=float(tick_duration_ms),
        labor_force_participation=float(metrics.get("labor_force_size", 0.0)) / max(1.0, float(metrics.get("total_households", 1.0))),
        open_vacancies=int(metrics.get("open_vacancies", metrics.get("labor_unfilled_vacancies", 0)) or 0),
        total_hires=int(metrics.get("labor_actual_hires", metrics.get("total_hires", 0)) or 0),
        total_layoffs=int(metrics.get("labor_layoffs", metrics.get("total_layoffs", 0)) or 0),
        healthcare_queue_depth=int(metrics.get("healthcare_queue_depth", 0) or 0),
        avg_food_price=float(metrics.get("avg_price_food", 0.0) or 0.0),
        avg_housing_price=float(metrics.get("avg_price_housing", 0.0) or 0.0),
        avg_services_price=float(metrics.get("avg_price_services", 0.0) or 0.0),
    )


def _decision_feature(run_id: str, tick: int, metric: TickMetrics) -> DecisionFeature:
    return DecisionFeature(
        run_id=run_id,
        tick=tick,
        unemployment_short_ma=float(metric.unemployment_rate),
        unemployment_long_ma=float(metric.unemployment_rate),
        inflation_short_ma=0.0,
        hiring_momentum=float(metric.total_hires or 0),
        layoff_momentum=float(metric.total_layoffs or 0),
        vacancy_fill_ratio=float(metric.total_hires or 0) / max(1.0, float((metric.total_hires or 0) + (metric.open_vacancies or 0))),
        wage_pressure=float(metric.mean_wage - metric.median_wage),
        healthcare_pressure=float(metric.healthcare_queue_depth or 0),
        consumer_distress_score=float(metric.unemployment_rate),
        fiscal_stress_score=max(0.0, -float(metric.gov_cash_balance)),
        inequality_pressure_score=float(metric.gini_coefficient),
    )


def _sector_metrics(run_id: str, tick: int, economy) -> list[SectorTickMetrics]:
    return [
        SectorTickMetrics(run_id=run_id, tick=tick, **row)
        for row in compute_sector_tick_rollups(economy.firms)
    ]


def _firm_snapshots(run_id: str, tick: int, economy) -> list[FirmSnapshot]:
    return [
        FirmSnapshot(run_id=run_id, tick=tick, **row)
        for row in compute_firm_snapshot_rows(economy.firms, household_lookup=economy.household_lookup)
    ]


def _household_snapshots(run_id: str, tick: int, economy) -> list[HouseholdSnapshot]:
    return [
        HouseholdSnapshot(run_id=run_id, tick=tick, **row)
        for row in compute_household_snapshot_rows(economy.households)
    ]


def run_warehouse_benchmark(
    *,
    backend: str,
    households: list[int],
    seeds: list[int],
    ticks: int,
    firms_per_category: int,
    output_root: Path,
    flush_every: int,
    household_snapshot_stride: int,
    verbose: bool,
) -> dict[str, Any]:
    paths = BenchmarkPaths.create(output_root, f"warehouse-{backend}")
    manager, db_path = _create_manager(backend, paths)
    rows: list[dict[str, Any]] = []
    flush_rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []
    table_count_rows: list[dict[str, Any]] = []
    try:
        for household_count in households:
            for seed in seeds:
                if verbose:
                    print(
                        f"[warehouse] backend={backend} households={household_count} seed={seed} ticks={ticks}",
                        flush=True,
                    )
                _set_seed(seed)
                run_id = build_run_id("warehouse", {"backend": backend, "households": household_count, "seed": seed})
                economy = _create_economy_quietly(household_count, firms_per_category, verbose=verbose)
                manager.create_run(
                    SimulationRun(
                        run_id=run_id,
                        status="running",
                        seed=seed,
                        num_households=household_count,
                        num_firms=len(economy.firms),
                        schema_version="benchmark",
                        description="EcoSim warehouse benchmark",
                        tags=f"benchmark,{backend}",
                    )
                )

                tick_batch: list[TickMetrics] = []
                sector_batch: list[SectorTickMetrics] = []
                decision_batch: list[DecisionFeature] = []
                firm_batch: list[FirmSnapshot] = []
                household_batch: list[HouseholdSnapshot] = []
                rows_written = 0
                insert_seconds = 0.0
                step_seconds = 0.0
                flush_index = 0

                def flush(last_tick: int) -> None:
                    nonlocal rows_written, insert_seconds, flush_index
                    if not any((tick_batch, sector_batch, decision_batch, firm_batch, household_batch)):
                        return
                    batch_counts = {
                        "tick_metric_rows": len(tick_batch),
                        "sector_tick_metric_rows": len(sector_batch),
                        "decision_feature_rows": len(decision_batch),
                        "firm_snapshot_rows": len(firm_batch),
                        "household_snapshot_rows": len(household_batch),
                    }
                    batch_rows = sum(batch_counts.values())
                    started = time.perf_counter()
                    manager.persist_flush_bundle(
                        run_id=run_id,
                        last_fully_persisted_tick=last_tick,
                        tick_metrics=list(tick_batch),
                        sector_tick_metrics=list(sector_batch),
                        decision_features=list(decision_batch),
                        firm_snapshots=list(firm_batch),
                        household_snapshots=list(household_batch),
                    )
                    flush_seconds = time.perf_counter() - started
                    insert_seconds += flush_seconds
                    rows_written += batch_rows
                    flush_rows.append(
                        {
                            "backend": backend,
                            "run_id": run_id,
                            "seed": seed,
                            "households": household_count,
                            "flush_index": flush_index,
                            "last_tick": last_tick,
                            "batch_rows": batch_rows,
                            "flush_ms": round(flush_seconds * 1000.0, 3),
                            "rows_per_second": round(batch_rows / flush_seconds, 2) if flush_seconds > 0 else 0.0,
                            **batch_counts,
                            **_sqlite_file_sizes(db_path),
                        }
                    )
                    flush_index += 1
                    tick_batch.clear()
                    sector_batch.clear()
                    decision_batch.clear()
                    firm_batch.clear()
                    household_batch.clear()

                for tick in range(ticks):
                    if verbose and (tick == 0 or tick % max(1, flush_every) == 0):
                        print(f"[warehouse] run={run_id} tick={tick}/{ticks}", flush=True)
                    step_started = time.perf_counter()
                    economy.step()
                    tick_duration_ms = (time.perf_counter() - step_started) * 1000.0
                    step_seconds += tick_duration_ms / 1000.0
                    metrics = economy.get_economic_metrics()
                    stats = compute_household_stats(economy.households)
                    metric = _tick_metric(run_id, tick, metrics, stats, tick_duration_ms)
                    tick_batch.append(metric)
                    sector_batch.extend(_sector_metrics(run_id, tick, economy))
                    decision_batch.append(_decision_feature(run_id, tick, metric))
                    firm_batch.extend(_firm_snapshots(run_id, tick, economy))
                    if tick == 0 or (household_snapshot_stride > 0 and tick % household_snapshot_stride == 0):
                        household_batch.extend(_household_snapshots(run_id, tick, economy))
                    if (tick + 1) % flush_every == 0:
                        flush(tick)
                flush(ticks - 1)

                run_query_rows = _query_suite(manager, run_id, ticks, household_snapshot_stride)
                for query_row in run_query_rows:
                    query_rows.append(
                        {
                            "backend": backend,
                            "run_id": run_id,
                            "seed": seed,
                            "households": household_count,
                            **query_row,
                        }
                    )
                summary_query_ms = next(
                    (float(row["query_ms"]) for row in run_query_rows if row["query_name"] == "run_summary"),
                    0.0,
                )
                summary = manager.get_run_summary(run_id)
                manager.update_run_status(
                    run_id,
                    "completed",
                    total_ticks=ticks,
                    last_fully_persisted_tick=ticks - 1,
                    analysis_ready=True,
                    final_metrics={
                        "gdp": summary.get("avg_gdp", 0.0),
                        "unemployment_rate": summary.get("avg_unemployment", 0.0),
                        "gini_coefficient": summary.get("avg_gini", 0.0),
                        "avg_happiness": summary.get("avg_happiness", 0.0),
                        "avg_health": 0.0,
                        "gov_cash_balance": economy.government.cash_balance,
                    },
                )
                table_counts = _table_counts(manager, run_id) if db_path else {}
                for table, count in table_counts.items():
                    table_count_rows.append(
                        {
                            "backend": backend,
                            "run_id": run_id,
                            "seed": seed,
                            "households": household_count,
                            "table_name": table,
                            "row_count": count,
                        }
                    )
                flush_latencies = [
                    float(row["flush_ms"])
                    for row in flush_rows
                    if row["run_id"] == run_id
                ]
                query_latencies = [
                    float(row["query_ms"])
                    for row in query_rows
                    if row["run_id"] == run_id
                ]
                sqlite_stats = _sqlite_pragmas(manager, db_path)
                rows.append(
                    {
                        "backend": backend,
                        "run_id": run_id,
                        "seed": seed,
                        "households": household_count,
                        "ticks": ticks,
                        "rows_written": rows_written,
                        "insert_seconds": round(insert_seconds, 4),
                        "rows_per_second": round(rows_written / insert_seconds, 2) if insert_seconds > 0 else 0.0,
                        "step_seconds": round(step_seconds, 4),
                        "write_overhead_pct": round((insert_seconds / max(step_seconds, 1e-9)) * 100.0, 3),
                        "summary_query_ms": round(summary_query_ms, 3),
                        "p50_flush_ms": round(percentile(flush_latencies, 50), 3),
                        "p95_flush_ms": round(percentile(flush_latencies, 95), 3),
                        "p99_flush_ms": round(percentile(flush_latencies, 99), 3),
                        "p95_query_suite_ms": round(percentile(query_latencies, 95), 3),
                        "database_size_mb": round(float(sqlite_stats.get("db_file_bytes", 0)) / (1024.0 * 1024.0), 3),
                        "wal_size_mb": round(float(sqlite_stats.get("wal_file_bytes", 0)) / (1024.0 * 1024.0), 3),
                        "logical_db_size_mb": round(float(sqlite_stats.get("logical_db_bytes", 0)) / (1024.0 * 1024.0), 3),
                        "journal_mode": sqlite_stats.get("journal_mode", ""),
                        "synchronous": sqlite_stats.get("synchronous", ""),
                        "database_path": str(db_path) if db_path else "",
                    }
                )
                if verbose:
                    print(
                        f"[warehouse] completed run={run_id} rows={rows_written} "
                        f"rows_per_sec={rows[-1]['rows_per_second']} write_overhead_pct={rows[-1]['write_overhead_pct']}",
                        flush=True,
                    )
    finally:
        manager.close()

    summary = summarize_warehouse_rows(rows)
    metadata = collect_metadata(
        {
            "benchmark": "warehouse-ingest",
            "backend": backend,
            "households": households,
            "seeds": seeds,
            "ticks": ticks,
            "flush_every": flush_every,
            "household_snapshot_stride": household_snapshot_stride,
        }
    )
    markdown = render_warehouse_summary(metadata=metadata, summary=summary)
    rows_csv = write_rows_csv(paths, "warehouse_rows", rows)
    flush_csv = write_rows_csv(paths, "warehouse_flush_rows", flush_rows)
    query_csv = write_rows_csv(paths, "warehouse_query_rows", query_rows)
    table_counts_csv = write_rows_csv(paths, "warehouse_table_counts", table_count_rows)
    summary_md = write_markdown(paths, "summary", markdown)
    raw_json = write_json(
        paths,
        "raw",
        {
            "metadata": metadata,
            "summary": summary,
            "rows": rows,
            "flush_rows": flush_rows,
            "query_rows": query_rows,
            "table_count_rows": table_count_rows,
        },
    )
    return {
        "paths": paths,
        "metadata": metadata,
        "summary": summary,
        "rows": rows,
        "flush_rows": flush_rows,
        "query_rows": query_rows,
        "table_count_rows": table_count_rows,
        "artifacts": {
            "rows_csv": rows_csv,
            "flush_csv": flush_csv,
            "query_csv": query_csv,
            "table_counts_csv": table_counts_csv,
            "summary_md": summary_md,
            "raw_json": raw_json,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark EcoSim warehouse ingest and query latency.")
    parser.add_argument("--backend", default="sqlite", choices=["sqlite", "postgres", "timescale"], help="Warehouse backend.")
    parser.add_argument("--households", default="1000,10000", help="Comma-separated household counts.")
    parser.add_argument("--ticks", type=int, default=200, help="Ticks per run.")
    parser.add_argument("--seeds", default="42", help="Comma-separated random seeds.")
    parser.add_argument("--firms-per-category", type=int, default=10)
    parser.add_argument("--flush-every", type=int, default=25, help="Ticks per warehouse flush.")
    parser.add_argument("--household-snapshot-stride", type=int, default=25)
    parser.add_argument("--output-root", type=Path, default=default_results_root())
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_warehouse_benchmark(
        backend=args.backend,
        households=parse_int_list(args.households),
        seeds=parse_int_list(args.seeds),
        ticks=args.ticks,
        firms_per_category=args.firms_per_category,
        output_root=args.output_root,
        flush_every=max(1, args.flush_every),
        household_snapshot_stride=max(1, args.household_snapshot_stride),
        verbose=args.verbose,
    )
    print(f"Wrote warehouse benchmark artifacts to {result['paths'].run_dir}")
    print(f"Rows/sec: {result['summary']['overall_rows_per_second']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
