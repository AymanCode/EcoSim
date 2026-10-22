"""The comparison report keeps the pre-debt output contract with borrowing off."""

from types import SimpleNamespace

import pytest

from config import CONFIG, clone_config, use_config
from tools.llm.run_government_control_compare import SCENARIOS, run_scenario, write_markdown


@pytest.mark.parametrize("debt_on", [False, True])
def test_control_report_debt_columns_follow_borrowing_flag(tmp_path, debt_on):
    args = SimpleNamespace(ticks=2, households=20, seed=42, warmup_ticks=1, interval=4, first_decision_tick=15)
    with use_config(clone_config()):
        CONFIG.government.public_debt_enabled = debt_on
        scenarios = {name: run_scenario(args, name) for name in SCENARIOS}
    for run in scenarios.values():
        assert ("public_debt" in run["final"]) is debt_on
        assert ("government_net_position" in run["final"]) is debt_on
        assert ("debt_interest_paid" in run["final"]) is debt_on
        assert ("government_net_position" in run["mins"]) is debt_on
        assert ("public_debt" in run["maxes"]) is debt_on
    report = tmp_path / "comparison.md"
    write_markdown(report, {"scenarios": scenarios, "config": vars(args)})
    text = report.read_text(encoding="utf-8")
    assert ("Final Net Position" in text) is debt_on
    assert ("Peak Debt" in text) is debt_on
    assert ("Debt Interest" in text) is debt_on
    table = [line for line in text.split("## no_government", 1)[0].splitlines() if line.startswith("|")]
    assert len({len(line.split("|")) for line in table}) == 1
