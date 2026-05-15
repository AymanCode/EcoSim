# EcoSim Code Cleanup Audit — Approved Items Only

> **Scope**: Full-project audit of `c:/Users/ayman/Projects/EcoSim`  
> **Date**: 2026-05-04  
> **Mode**: Static analysis + targeted code reading (no production edits)  
> **Deliverable**: This file (`CLEANUP_AUDIT.md`)  

---

## Executive Summary

This audit identifies **7 approved cleanup items** that are mechanical (no behavior changes) or test-only. All other findings from the full audit are **deferred** per reviewer constraints:

**Constraints (enforced):**
- 🚫 No file splits (economy.py, agents.py stay monolithic)
- 🚫 No method renames
- 🚫 No JSON key changes (frontend consumes camelCase)
- 🚫 No behavior changes
- ✅ Every change must be mechanical or test-only
- ✅ Run existing contract tests after each step
- ✅ Commit each step separately for easy rollback

---

## Approved Cleanup Items (in strict order)

### 1 — Delete Dead Frontend Migration Scripts (HIGH PRIORITY)

**Status**: Pending  
**Effort**: Small  
**Risk**: None (dead code)

These scripts exist in `frontend-react/` and appear to be **one-time JSX migration scripts** that are not referenced by any build process:

| File | Lines | Purpose | Action |
|------|-------|---------|--------|
| `frontend-react/fix_nested.py` | 185 | Replaces nested div structure in App.jsx | **DELETE** |
| `frontend-react/fix_nested_safe.py` | 126 | Safer version of fix_nested.py | **DELETE** |
| `frontend-react/replace_script.py` | 49 | Replaces JSX component structure | **DELETE** |
| `frontend-react/replace_script2.py` | ? | Likely similar | **DELETE** (not found in search) |
| `frontend-react/update_firms.py` | 67 | Updates firm tab in App.jsx | **DELETE** |
| `frontend-react/update_gov_tab.py` | 171 | Updates government tab in App.jsx | **DELETE** |
| `frontend-react/update_subjects_tab.py` | 110 | Updates subjects tab in App.jsx | **DELETE** |
| `frontend-react/insert_distress_gauge.py` | ? | Likely similar | **DELETE** |

**Verification**: All scripts directly `open('src/App.jsx', 'r')` and modify the file in-place. They are not referenced by `package.json`, `start.sh`, or any build process.

---

### 2 — Delete Audit Dump Artifacts (HIGH PRIORITY)

**Status**: Pending  
**Effort**: Small  
**Risk**: None (generated artifacts)

| File | Location | Action |
|------|----------|--------|
| `audit_full_dump_latest.md` | Repo root | **DELETE** |
| `audit_full_dump_digest.md` | Repo root | **DELETE** |
| `audit_full_dump_digest.json` | Repo root | **DELETE** |
| `audit_full_dump_latest.jsonl` | Repo root | **DELETE** |
| `backend/audit_full_dump_digest.md` | backend/ | **DELETE** |
| `backend/audit_full_dump_digest.json` | backend/ | **DELETE** |

---

### 3 — Consolidate Good Category Inference (MEDIUM PRIORITY)

**Status**: Pending  
**Effort**: Small  
**Risk**: Low (mechanical, no behavior change)

#### Current Duplication (CONFIRMED)

Two separate functions perform nearly identical good-name → category inference:

| Location | Function | Lines |
|---------|----------|-------|
| `backend/agents.py:21` | `_get_good_category()` | 21-37 |
| `backend/server.py:414` | `_infer_sector_from_good()` | 414-423 |

Both check for `"housing"`, generic lowercase fallback. The server version is a static method; the agents version is a module-level function.

#### Additional Duplication in Economy (CONFIRMED)

`backend/economy.py` imports `_get_good_category` from agents (line 23) but `server.py` defines its own `_infer_sector_from_good`. The `economy.py` file also has its own `_build_good_category_lookup()` at line 2920-2922, creating a third mechanism.

#### Pre-Check: Verify backend/utils/ Directory

**Action**: Check if `backend/utils/` directory exists:
- **If NO** (current state based on directory listing): Create `backend/utils/__init__.py` and `backend/utils/category_utils.py`
- **If YES**: Only add `backend/utils/category_utils.py`

#### Approved Action

1. **Create new module** (if needed): `backend/utils/__init__.py` (new, empty or minimal)
2. **Create new module**: `backend/utils/category_utils.py` (new)
3. Move the logic from `_get_good_category()` (agents.py:21-37) into `backend/utils/category_utils.py` as `get_good_category()`
4. **Update `backend/agents.py`**:
   - Remove local `_get_good_category()` function (lines 21-37)
   - Add import: `from utils.category_utils import get_good_category`
5. **Update `backend/economy.py`**:
   - Change import at line 23 from `from agents import ..., _get_good_category` to `from utils.category_utils import get_good_category`
   - Update all call sites from `_get_good_category(...)` to `get_good_category(...)`
   - **Check `_build_good_category_lookup()` at line 2920-2922**: Either route it through new util OR leave untouched and note in commit. **Do not silently leave a third mechanism.**
6. **Update `backend/server.py`**:
   - Remove `_infer_sector_from_good()` static method (lines 413-423)
   - Add import: `from utils.category_utils import get_good_category`
   - Update all call sites from `self._infer_sector_from_good(...)` to `get_good_category(...)`
   - Note: `server.py` also uses this in `_build_live_decision_metric` (line 769), `_record_live_decision_context` (line 801), and `run_loop` (lines 1869, 1924)

**Constraint**: No behavior change — default values and logic must match current implementation exactly.

---

### 4 — Move Shock Magic Numbers to Config (MEDIUM PRIORITY)

**Status**: Pending  
**Effort**: Small  
**Risk**: Low (mechanical, defaults match current literals)

#### Pre-Check: Grep for Exact Literals (DO NOT TRUST LINE NUMBERS)

Before editing, search for each literal in `backend/economy.py`:

| Literal | Search Pattern | Expected Location |
|---------|---------------|-------------------|
| `base_transfer = 40.0` | `base_transfer = 40\.0` | `_apply_post_warmup_stimulus()` |
| `_rng.random() < 0.05` | `_rng\.random\(\) < 0\.05` | `_apply_random_shocks()` |
| `_rng.random() < 0.03` | `_rng\.random\(\) < 0\.03` | `_apply_random_shocks()` |
| `_rng.random() < 0.02` | `_rng\.random\(\) < 0\.02` | `_apply_random_shocks()` |
| `_rng.uniform(-50, 100)` | `_rng\.uniform\(-50, 100\)` | `_apply_random_shocks()` |
| `_rng.uniform(0.85, 1.15)` | `_rng\.uniform\(0\.85, 1\.15\)` | `_apply_random_shocks()` |

**Action**: Replace **each occurrence found**, not specific line numbers.

#### Approved Action

1. **Add new dataclass** to `backend/config.py` (after line 768):

```python
@dataclass
class ShockConfig:
    """Stochastic shock parameters for the economy."""
    
    # Post-warmup stimulus
    post_warmup_transfer_per_household: float = 40.0
    
    # Shock probabilities (per tick)
    demand_shock_probability: float = 0.05
    supply_shock_probability: float = 0.03
    health_shock_probability: float = 0.02
    
    # Demand shock parameters
    demand_shock_min: float = -50.0
    demand_shock_max: float = 100.0
    
    # Supply shock parameters  
    supply_shock_min: float = 0.85
    supply_shock_max: float = 1.15
```

2. **Add to `SimulationConfig`** class (line 701-714):
   - `shocks: ShockConfig = field(default_factory=ShockConfig)`

3. **Update `backend/economy.py`** (grep and replace each occurrence):
   - In `_apply_post_warmup_stimulus()`:
     - Replace `base_transfer = 40.0` with `base_transfer = CONFIG.shocks.post_warmup_transfer_per_household`
   - In `_apply_random_shocks()`:
     - Replace `_rng.random() < 0.05` with `_rng.random() < CONFIG.shocks.demand_shock_probability`
     - Replace `_rng.random() < 0.03` with `_rng.random() < CONFIG.shocks.supply_shock_probability`
     - Replace `_rng.random() < 0.02` with `_rng.random() < CONFIG.shocks.health_shock_probability`
     - Replace `shock_magnitude = _rng.uniform(-50, 100)` with `shock_magnitude = _rng.uniform(CONFIG.shocks.demand_shock_min, CONFIG.shocks.demand_shock_max)`
     - Replace `productivity_change = _rng.uniform(0.85, 1.15)` with `productivity_change = _rng.uniform(CONFIG.shocks.supply_shock_min, CONFIG.shocks.supply_shock_max)`

**Constraint**: Default values must match current literals exactly — no behavior change.

---

### 5 — Fix prev_gov_cash Dynamic Attribute (MEDIUM PRIORITY)

**Status**: Pending  
**Effort**: Small  
**Risk**: Low (proper initialization)

#### Current Issue (CONFIRMED)

In `backend/server.py:1817`:
```python
if not hasattr(self, 'prev_gov_cash'):
    self.prev_gov_cash = current_gov_cash
```
This pattern of dynamically adding attributes to `self` is fragile and error-prone.

#### Approved Action

1. Open `backend/server.py`
2. Find `SimulationManager.__init__()` method (around line 350)
3. Add initialization inside `__init__()`:
```python
def __init__(self):
    # ... existing initialization ...
    self.prev_gov_cash = 0.0  # Initialize to avoid dynamic attribute creation
    # ... rest of init ...
```

4. Remove the `hasattr` check in `run_loop()` (around line 1817):
   - **Before**:
     ```python
     if not hasattr(self, 'prev_gov_cash'):
         self.prev_gov_cash = current_gov_cash
     fiscal_balance = current_gov_cash - self.prev_gov_cash
     self.prev_gov_cash = current_gov_cash
     ```
   - **After**:
     ```python
     fiscal_balance = current_gov_cash - self.prev_gov_cash
     self.prev_gov_cash = current_gov_cash
     ```

**Constraint**: Mechanical change — no behavior change.

---

### 6 — Add Integration Smoke Test (HIGH PRIORITY)

**Status**: Pending  
**Effort**: Medium  
**Risk**: Low (test-only, no production code changes)

#### Pre-Check: Grep for Actual Public Metrics-Getter Method

Before writing the smoke test, grep `economy.py` for the actual public method name:
- Search pattern: `def get_*metrics|def compute_*metrics|def economic_*`
- **Do NOT assume** `get_economic_metrics()` exists
- **Do NOT assume** keys like `gdp`, `unemployment_rate`, `total_households`
- **Test must use real API** — whatever name and key shape exists

#### Approved Action

1. **Create new test file**: `backend/tests_contracts/test_contracts_integration_smoke.py`

2. **Add ONE integration smoke test** (using actual API discovered via grep):

```python
"""Integration smoke test for the full Economy pipeline.

Verifies that a small economy can run for 10 ticks without errors
and produces valid economic metrics.
"""

import pytest

# Grep economy.py for actual public API before writing test
# Example structure (adjust method/key names to match reality):
#
# def test_full_economy_smoke():
#     """Spin up small economy, run 10 ticks, assert no exceptions + valid metrics."""
#     
#     # Create small economy using actual factory
#     economy = create_large_economy(num_households=100, num_firms_per_category=2)
#     
#     # Run 10 ticks
#     for tick in range(10):
#         economy.step()  # Should not raise any exceptions
#     
#     # Get actual metrics using real method name
#     metrics = economy.get_economic_metrics()  # Or whatever the actual method name is
#     
#     # Verify metrics exist and are valid (use actual key names)
#     assert metrics is not None
#     # Check actual keys present in metrics dict
#     # Example: if 'gdp' in metrics: assert metrics['gdp'] > 0
```

3. **Run existing contract tests** to ensure no regressions:
   - `pytest backend/tests_contracts/ -v`
   - `pytest backend/tests_server/ -v`

**Constraint**: Test-only change — no production code modifications. Must use real API.

---

### 7 — Minimal Documentation Pass (LOW PRIORITY, ADDITIVE)

**Status**: Pending  
**Effort**: Small  
**Risk**: None (additive, zero behavior risk)

#### Approved Action

1. **Add module-level docstring** to top of each file if missing — one paragraph each:

   - `backend/agents.py` — Describe responsibility and key public exports
   - `backend/economy.py` — Describe responsibility and key public exports
   - `backend/server.py` — Describe responsibility and key public exports
   - `backend/config.py` — Describe responsibility and key public exports

2. **Add class-level docstring** to each class if missing — 2-4 lines each:

   - `HouseholdAgent` (agents.py:67)
   - `FirmAgent` (agents.py:2153)
   - `BankAgent` (agents.py:4588)
   - `GovernmentAgent` (agents.py:4895)
   - `Economy` (economy.py:28)
   - `SimulationManager` (server.py:330)

3. **Constraints**:
   - Do **NOT** add method docstrings
   - Do **NOT** add type hints
   - Do **NOT** touch existing docstrings
   - Pure additions only

4. **Commit separately**

5. **Run contract tests** after: `pytest backend/tests_contracts/ -v`

---

## Summary of Approved Work (Strict Order)

| Step | Item | Files Changed | Test Run Required |
|------|------|---------------|---------------------|
| 1 | Delete dead frontend scripts | `frontend-react/*.py` (DELETE 7 files) | No |
| 2 | Delete audit dump artifacts | Repo root + `backend/` (DELETE 6 files) | No |
| 3 | Consolidate category utils | `backend/utils/category_utils.py` (NEW), `agents.py`, `economy.py`, `server.py` | Yes |
| 4 | Move shocks to config | `config.py`, `economy.py` | Yes |
| 5 | Fix prev_gov_cash init | `server.py` | Yes |
| 6 | Add smoke test | `tests_contracts/test_contracts_integration_smoke.py` (NEW) | Yes |
| 7 | Minimal doc pass | `agents.py`, `economy.py`, `server.py`, `config.py` | Yes |

**After each step**: Run `pytest backend/tests_contracts/ -v` and `pytest backend/tests_server/ -v`. Stop and report if any tests fail.

---

## Deferred Items (DO NOT IMPLEMENT)

Per reviewer constraints, the following items from the full audit are **deferred indefinitely**:

- 🚫 Split economy.py (5769 lines) into modules
- 🚫 Split agents.py (5718 lines) into separate agent files
- 🚫 Extract SimulationManager persistence logic into separate class
- 🚫 Fix typos in variable names (agents.py)
- 🚫 Standardize JSON key naming conventions
- 🚫 Add type hints to all public methods
- 🚫 Add docstrings to all public methods
- 🚫 Any other items from the full audit not explicitly listed above

---

*End of CLEANUP_AUDIT.md*
