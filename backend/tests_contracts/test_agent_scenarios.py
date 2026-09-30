"""The experiment runner must be repeatable and exercise actual actor behavior."""

import json
import random

import numpy as np
import pytest

from config import CONFIG
from tools.checks import run_agent_scenarios as scenarios


def test_scenarios_repeat_after_unrelated_random_draws_and_restore_process_state():
    cases = list(scenarios.CASES)
    sequence_before, seed_before = CONFIG.payment_sequence, CONFIG.random_seed
    python_before, numpy_before = random.getstate(), np.random.get_state()
    first = scenarios.run_suite(cases, households=24, ticks=18)
    assert random.getstate() == python_before
    np.testing.assert_array_equal(np.random.get_state()[1], numpy_before[1])
    assert np.random.get_state()[2:] == numpy_before[2:]
    assert (CONFIG.payment_sequence, CONFIG.random_seed) == (sequence_before, seed_before)
    random.random()
    np.random.random(100)
    second = scenarios.run_suite(cases, households=24, ticks=18)
    assert first == second
    assert all(check["passed"] for case in first for check in case["checks"])


def test_full_week_uses_credit_and_payday_receipts_for_shopping():
    case = scenarios.run_suite(["household_payday"])[0]
    row = case["rows"][0]
    assert row["wages_received"] > 0
    assert row["consumption_loan_received"] > 0
    assert row["goods_spending"] > 0
    assert row["food_eaten"] > 0


def test_report_keeps_observations_separate_from_check_results(tmp_path):
    assert scenarios.main(["--output-dir", str(tmp_path), "--ticks", "18"]) == 0
    data = json.loads((tmp_path / "results.json").read_text())
    cases = {case["id"]: case for case in data["results"]}
    assert len(cases["small_town"]["traces"]) == 18
    assert all(len(t["households"]) == 24 for t in cases["small_town"]["traces"])
    assert cases["business_payroll"]["rows"][0]["business_cash_after"] < 0
    assert cases["business_payroll"]["findings"]
    report = (tmp_path / "report.md").read_text()
    assert "observations need review" in report
    assert "not a calibration sample" in report
    assert data["metadata"]["source_sha256"]["backend/economy.py"]


def test_failed_mechanism_check_returns_failure_and_keeps_report(tmp_path, monkeypatch):
    def failing_case(seed):
        return scenarios.result("example", "Failure example", "Synthetic runner failure only.",
                                [{"value": 1}], [("Deliberately failed", False)])
    monkeypatch.setitem(scenarios.CASES, "example", failing_case)
    assert scenarios.main(["--case", "example", "--output-dir", str(tmp_path)]) == 1
    assert "FAIL: Deliberately failed" in (tmp_path / "report.md").read_text()


def test_exception_restores_rng_and_config():
    seed_before = CONFIG.random_seed
    python_before, numpy_before = random.getstate(), np.random.get_state()
    with pytest.raises(RuntimeError), scenarios.isolated_run(19):
        random.random()
        np.random.random()
        raise RuntimeError("interrupted scenario")
    assert CONFIG.random_seed == seed_before
    assert random.getstate() == python_before
    np.testing.assert_array_equal(np.random.get_state()[1], numpy_before[1])
    assert np.random.get_state()[2:] == numpy_before[2:]


@pytest.mark.parametrize("args", [["--households", "1000"], ["--ticks", "0"], ["--seed", "-1"]])
def test_rejects_invalid_or_large_runs(args):
    with pytest.raises(SystemExit) as exc:
        scenarios.main(args)
    assert exc.value.code == 2
