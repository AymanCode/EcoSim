# Policy Stress-Testing & Forecasting — V1 Consensus Spec (rev 3)

**Status:** Two Codex adversarial rounds. Rev 3 resolves rev-2 residuals (B1/B2/M5/M7/M9/M10) + 5 new Codex issues. Frozen schema is now a real artifact: `docs/POLICY_FORECASTING_SCHEMA.md`. NOT implementation-ready until a Codex pass on rev 3 + frozen schema returns clean.

## One-line story

> Build one deterministic 10k-agent policy-sweep dataset with full per-tick economy/sector/firm telemetry (household as aggregates only), then use it for two co-equal deliverables: matched-seed policy-effect analysis and leakage-safe ML forecasting of future economic stress.

Spine: *Can early labor/firm/household/fiscal/policy signals forecast future economic stress under controlled policy interventions in a 10k-agent simulator?*

## Interview defense (scripted — Codex hardened)

- **Synthetic-data killing question:** *"Which structural feature-outcome relationships are invariant between EcoSim and a real economy, and what evidence would falsify that?"* **Answer:** Simulator system identification / surrogate modeling only. Transfer assumption = structural invariance / transportability; **V1 does not test it** (no real-data calibration/validation). Contribution = experimental design + leakage-safe methodology over a known complex stochastic system, not macro prediction.
- **Matched seeds:** same seed fixes initial population/firm setup/stochastic events → paired treatment-vs-baseline deltas isolate policy effect, low variance. Simulation treatment analysis, not real-world causality.
- **No LLM in V1:** LLM decisions inject nondeterminism, break matched-seed isolation.
- **No deep learning:** tabular time-series, limited runs → gradient boosting appropriate, explainable, validatable.

## Blocker fixes

### B1 — Per-tick dataset contract → FROZEN in `docs/POLICY_FORECASTING_SCHEMA.md`
Row grain `(run_id, policy_canonical, seed, tick)`. Per-tick economy/sector/firm metrics + household *aggregates/distributional summaries* (NOT per-household rows). **Frozen-base capture (user decision): zero `backend/` edits.** A new self-contained `policy_forecasting/` package (own venv, same branch) imports the sim read-only and drives the existing `Economy` object tick-by-tick via its **public API**, snapshotting the frozen feature manifest from public attributes / existing to-dict surfaces (`agents.py:1185`, `backend/data/models.py`). `run_policy_sweep.py` is NOT modified — the wrapper is a new external driver. Any manifest column not reachable on the public surface is **dropped + documented**, never added via a base edit.

### B2 — Policy split by canonical lever vector + exclusion list
Canonicalize each policy to its lever vector; dedupe arms equal to baseline/defaults. **Split held-out by canonical lever vector.** Hard-excluded from features: `run_id`, `policy_canonical`, `levers_json`, `seed`, `tick`, all `*__t+8`. Policy-*state* values at t allowed as features (observable at t); the split guarantees test arms are unseen lever vectors. Mandatory no-policy-state ablation reported alongside. **Generalization claim is narrow:** held-out performance *among 6 pre-registered interventions*, NOT broad policy-space generalization (Codex NEW-d). All wording uses this phrasing.

### B3 — Determinism MEASURED + disclosed (user decision: frozen base, no RNG fix)
Base is set in stone → the flagged nondeterminism sources (string-set iteration `agents.py:1587-1593`/`economy.py:978-983`, global `random.randint/sample` `run_large_simulation.py:257-259`) are **NOT modified**. Instead the wrapper runs each canonical arm twice in **fresh processes**, fixed env (`PYTHONHASHSEED=0`), hashes the full per-tick manifest series (no rounding), and **quantifies the run-to-run noise floor**. Outcome:
- If byte-identical → matched-seed deltas are exact; report so.
- If not → report the measured noise floor. **Interpretive rule (Codex rev5): compare each treatment effect against the replicate-delta distribution / noise threshold — NOT a "magic subtraction" that pretends to remove nondeterminism.** An effect counts only if it exceeds the replicate-delta noise band. Interview defense states determinism was **measured, not engineered** — honest and still defensible (user decision: measure + disclose). 2k = smoke; the 10k measurement is the binding number. `regression_snapshot.py` insufficient → gate is a new harness **inside `policy_forecasting/`**, zero base edits.

## Major fixes

- **M5 distress — FROZEN formula** in schema doc: bounded [0,1], weighted (cash 0.40 / food 0.25 / health 0.20 / happy 0.15), **food insecurity included** (repo formula omitted it; this overrides). Label-only at t+8; components allowed as ≤ t features, aggregate-distress@t+8 is not.
- **M7 + Codex NEW-a — numeric power/MDE.** Wilcoxon signed-rank, n=24 paired seed deltas, two-sided α=0.05, Holm/BH over 5 non-baseline arms × 2 outcomes = 10 comparisons (effective α≈0.005). **Pre-registered MDE: standardized paired effect dz ≈ 0.8** (≈0.8 SD of the per-seed delta) detectable at ~80% power post-correction. Deltas with |dz| < 0.8 are reported as **exploratory point estimates + paired-bootstrap CI, no significance claim**. Inference downgraded for small effects, never forced. (If a richer power budget is wanted later, raise seed count — out of V1.)
- **M8 — protected.** Disjoint train / validation / frozen-final-test blocks by `(canonical-policy, seed)`; policy-aware persistence + trend baselines; bootstrap CI on the performance delta; **no claim if CI crosses zero**. CI/error estimation also blocks by run AND time-regime (early/mid/late tick bands) for autocorrelation + non-stationarity (Codex NEW-c). Rows within a run are not independent.
- **M9 + Codex NEW-e — runtime AND storage/IO budgeted.** Per-tick household-aggregate-only schema caps dataset at ~6×24×120 ≈ 17k rows × ~80 cols (trivial), NOT ~170M household-rows. Sim CPU is the cost, not IO. Sweep is currently serial — **parallelization across (policy, seed) is mandatory implementation work**, not optional. Confirm sweep ≈ 144 runs × ~14 min ≈ 4–5 hr at 8-way.
- **M10 — interim bullet de-risked.** No "leakage-safe" / "deterministic" / "beat persistence" wording until the gate passes, schema/leak checks run, frozen test read. Interim bullet below avoids all three.

## Locked V1 scope

| Component | Decision |
|---|---|
| Dataset | One deterministic 10k-agent matched-seed sweep; per-tick economy/sector/firm + household aggregates per `POLICY_FORECASTING_SCHEMA.md` |
| Sweep harness | **New external wrapper in `policy_forecasting/`** (per-tick dump + parallel across (policy, seed)); `run_policy_sweep.py` NOT modified — frozen base |
| Policies | **6 distinct-lever-vector arms** post-dedupe: baseline + wage tax + profit tax + benefits + minimum wage + sector subsidy |
| Seeds | 24 matched seeds (confirm); ≈4 at 2k dev smoke scale |
| Horizon | t+8 ticks |
| Forecast targets | unemployment rate @ t+8 (primary), consumer distress @ t+8 (secondary, frozen formula) |
| Models | policy-aware persistence + trend (required) + linear/ElasticNet + gradient boosting |
| Validation | held-out canonical lever vectors + held-out seeds; features ≤ t; frozen final test; CI blocked by run/time-regime |
| Explainability | SHAP, one economic finding |
| Demo | thin slider UI: policy → predicted t+8 unemployment/distress + delta vs baseline |
| Packaging | standalone repo; README problem/approach/result first 200 words; one architecture diagram |
| Emphasis | balanced: policy-effect = interview headline; forecasting = resume bullet |

## Runtime — LOCKED: pilot 2k smoke → one 10k confirm

- **Dev (2k agents, ~3 min/run, ≈4 seeds):** pipeline build, leakage validation, schema conformance, determinism **smoke** (NOT the gate).
- **Confirm (10k, 6 arms, 24 seeds, ≥80 ticks, parallel (policy,seed)):** ≈4–5 hr 8-way. Produces headline numbers.
- **Determinism gate runs at 10k** (binding) — 2k pass is necessary-not-sufficient.
- Forecasting samples come from ticks/run (≥80 → ~70 windows/run after warmup); seeds spent on CI validity.
- Front-load: persistence-beat number on unemployment@t+8 from confirm run BEFORE polishing demo/SHAP/diagram.

## Out of scope V1

LLM-in-loop; RAG advisor consuming forecaster (future, post-numbers); GDP/gov-cash/shortages/happiness as ML targets (Deliverable-A context only); 3-horizon / 5-target; broad policy-space generalization claims.

## Interim honest resume bullet (pre-results)

> *Designed a controlled simulation experiment on a 10k-agent economic simulator: matched-seed policy treatments with a byte-identical determinism gate and a forecasting pipeline benchmarked against policy-aware persistence/trend baselines, validated on held-out seeds and held-out lever vectors among 6 pre-registered interventions.*

Upgrade to quantified wording (incl. "leakage-safe", "beat persistence by X%") only after the frozen test is read.

## Open risks tracked

- Codex rev-3 pass must return clean before implementation.
- 10k determinism gate is THE gate; 2k is smoke.
- Distress constants (k, F, health_max, happiness_max) frozen at implementation, recorded, never post-tuned.
- Generalization claim stays narrow (6 pre-registered interventions).
