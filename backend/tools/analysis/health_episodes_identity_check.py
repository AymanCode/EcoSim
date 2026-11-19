"""Compare the disabled health flag with 5c66095 in a separate worktree.

Run from the candidate worktree with the project's interpreter:
    python backend/tools/analysis/health_episodes_identity_check.py BASELINE_WORKTREE

The two simulations run serially in fresh processes with the same interpreter
and the same evaluator from the candidate checkout.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


CANDIDATE = Path(__file__).resolve().parents[3]
BASELINE_REVISION = "5c66095"
CARE_FIELDS = (
    "pending_healthcare_visits",
    "payment_care_due_tick",
    "payment_care_due_retry",
    "next_healthcare_request_tick",
    "pending_visit_heal_delta",
    "payment_care_episode_id",
    "payment_care_accepted_quote",
    "queued_healthcare_firm_id",
)
EXCLUDED_DIAGNOSTICS = {
    "health_illnesses_this_tick": "new diagnostic counter, absent at the baseline revision",
}


def capture(root: Path) -> list[dict[str, str]]:
    # Use the same measuring code for both arms, loading it independently
    # of the simulator imports that must come from the selected worktree.
    worker_path = CANDIDATE / "backend/tools/benchmarks/evidence_panel_worker.py"
    spec = importlib.util.spec_from_file_location("_identity_evaluator", worker_path)
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)

    sys.path.insert(0, str(root / "backend"))
    from config import CONFIG, clone_config, use_config
    from sim_setup import build_economy_from_setup

    setup = SimpleNamespace(num_households=1000, num_firms=5, payment_sequence="income_first",
                            enable_llm_government=False, disable_stabilizers=False,
                            disabled_agents=[], initial_policy={})
    with use_config(clone_config()), redirect_stdout(io.StringIO()):
        for flag in ("health_episodes", "realistic_initial_population"):
            if hasattr(CONFIG.households, flag):
                setattr(CONFIG.households, flag, False)
        economy, _ = build_economy_from_setup(setup, seed=42)
        economy._apply_random_shocks = lambda: None

        def state():
            households = sorted(economy.households, key=lambda h: h.household_id)
            firms = sorted([*economy.firms, *economy.queued_firms], key=lambda f: f.firm_id)
            result = evaluator.state_components(economy)
            result["firm_owners"] = evaluator._digest([(f.firm_id, f.owners) for f in firms])
            result["ordered_care_queues"] = evaluator._digest([
                (f.firm_id, list(f.healthcare_queue)) for f in firms if f.good_category.lower() == "healthcare"
            ])
            for field in CARE_FIELDS:
                result[field] = evaluator._digest([
                    (h.household_id, getattr(h, field)) for h in households
                ])
            if economy.external_injection_total != 0.0:
                raise RuntimeError(f"External injection at tick {economy.current_tick}")
            return result

        opening = state()
        opening["age"] = evaluator._digest([(h.household_id, h.age) for h in economy.households])
        trace = [opening]
        for _ in range(30):
            economy.step()
            trace.append(state())
    return trace


def git_revision(root: Path, revision: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", revision], text=True).strip()


def run_arm(root: Path) -> list[dict[str, str]]:
    return json.loads(subprocess.check_output(
        [sys.executable, str(Path(__file__).resolve()), "--worker", str(root)],
        cwd=root, text=True,
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_worktree", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    baseline = args.baseline_worktree.resolve()
    if args.worker:
        print(json.dumps(capture(baseline)))
        return

    if baseline == CANDIDATE or not (baseline / "backend/sim_setup.py").is_file():
        parser.error("supply a separate baseline worktree root")
    baseline_head = git_revision(baseline, "HEAD")
    if baseline_head != git_revision(CANDIDATE, BASELINE_REVISION):
        parser.error(f"baseline worktree must be at {BASELINE_REVISION}")
    if subprocess.run(["git", "-C", str(baseline), "diff", "--quiet", "HEAD", "--", "backend"]).returncode:
        parser.error("baseline backend differs from the pinned commit")

    candidate_head = git_revision(CANDIDATE, "HEAD")
    print(f"Baseline {baseline_head}\nCandidate {candidate_head}", flush=True)
    for field, reason in EXCLUDED_DIAGNOSTICS.items():
        print(f"Excluded {field} ({reason})", flush=True)
    reference = run_arm(baseline)
    candidate = run_arm(CANDIDATE)
    if len(reference) != 31 or len(candidate) != 31:
        raise SystemExit("Expected opening state and 30 completed ticks")
    for tick, (expected, actual) in enumerate(zip(reference, candidate)):
        differences = sorted(key for key in expected.keys() | actual.keys()
                             if expected.get(key) != actual.get(key))
        if differences:
            raise SystemExit(f"Identity failed at tick {tick}: {', '.join(differences)}")
    print("Opening and 30 ticks matched for 1,000 households, income_first, seed 42.")
    print("Compared " + ", ".join(sorted(reference[0])))


if __name__ == "__main__":
    main()
