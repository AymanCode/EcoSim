# EcoSim Refactoring Plan

**Date**: 2026-05-04  
**Auditor**: Roo (Architect mode)  
**Based on**: PROJECT_MAP.md, DOCUMENTATION_AUDIT.md, CLEANUP_AUDIT.md  

---

## Executive Summary

This refactoring plan synthesizes findings from three audit documents to create a prioritized, phased approach to improving the EcoSim codebase. The plan strictly prefers **small surgical refactors over large rewrites**, preserves current behavior unless a bug is confirmed, and separates **confirmed issues** (verified by code review) from **possible issues** (suspected but not fully verified).

**Key Principles:**
- No file splits (economy.py at 5769 lines and agents.py at 5718 lines stay monolithic)
- No method renames
- No JSON key changes (frontend consumes camelCase)
- No behavior changes unless a bug is confirmed
- Every change must be mechanical or test-only
- Run existing contract tests after each step
- **All documentation claims must be verified by grep before editing**

---

## Verification Results (Pre-Work Grep)

### CONFIRMED Claims (Verified by Code Search)

| Claim | Source | Verification Result |
|-------|--------|---------------------|
| warmup_ticks default is 10 | `config.py:16` | **CONFIRMED** - `warmup_ticks: int = 10` |
| warmup_ticks fallback is 52 | `economy.py:71` | **CONFIRMED** - `getattr(CONFIG.time, "warmup_ticks", 52)` |
| README.md wrong test path | README.md:110 | **CONFIRMED** - References `backend/data/tests`, actual dirs are `backend/tests_contracts/`, `backend/tests_server/` |
| _plan_labor_adjustment() missing | SIMULATION.md | **CONFIRMED** - Search found 0 results in codebase |
| adjust_wages_if_overpaying() missing | SIMULATION.md | **CONFIRMED** - Search found 0 results in codebase |
| maybe_active_education() returns float | agents.py:1913-1932 | **CONFIRMED** - Returns `cost` (float), not bool |
| RNG is seeded | agents.py, economy.py | **CONFIRMED** - Uses `random.Random(CONFIG.random_seed + ...)` throughout |
| "Deterministic when seeded" is correct | agents.py:72 | **CORRECT** - Code uses seeded RNG, behavior IS deterministic with same seed |

### REJECTED Claims (Verification Failed)

| Claim | Source | Why Rejected |
|-------|--------|--------------|
| "Deterministic when seeded" is misleading | DOCUMENTATION_AUDIT.md D7 | **FALSE** - Code uses `random.Random(CONFIG.random_seed + ...)` making behavior deterministic when seeded |
| SIMULATION.md has 15 phases | DOCUMENTATION_AUDIT.md D3 | **INACCURATE** - SIMULATION.md actually shows 21 phases (lines 226-249) |
| economy.py has 16 phases | PROJECT_MAP.md, DOCUMENTATION_AUDIT.md | **INACCURATE** - `economy.py:863-876` docstring shows 12 phases |

### POSSIBLE Issues (Need Further Verification)

| # | Issue | Files | Verification Needed |
|---|-------|-------|---------------------|
| P1 | FRONTEND.md: Tick metrics payload field names may not match | `docs/FRONTEND.md:91`, `backend/server.py` | Verify payload structure |
| P2 | BANKING_SYSTEM.md: Phase numbering may not match economy.py | `docs/BANKING_SYSTEM.md:99-100`, `backend/economy.py:863-876` | Verify phase mapping |
| P3 | FIRM_DYNAMICS.md: `smoothed_profit_margin` needs verification | `docs/FIRM_DYNAMICS.md:107`, `backend/agents.py`, `backend/economy.py` | Search codebase |
| P4 | FIRM_DYNAMICS.md: `category_wage_anchor_p75` needs verification | `docs/FIRM_DYNAMICS.md:108`, `backend/agents.py`, `backend/economy.py` | Search codebase |
| P5 | TECHNICAL.md: Missing `tools/` directory documentation | `docs/TECHNICAL.md:81-82`, `backend/tools/` | Review tools/ structure |
| P6 | DATA_STORAGE_ARCHITECTURE.md: Migration numbering stale | `docs/DATA_STORAGE_ARCHITECTURE.md:126`, `backend/data/migrations/` | Verify migration numbers |

---

## Phase 1: Quick Wins (High Impact, No Risk)

**Goal**: Remove dead code and fix obvious documentation errors. These changes are mechanical with zero risk of breaking functionality.

### 1.1 Delete Dead Frontend Migration Scripts
**Priority**: HIGH  
**Risk**: None (dead code)  
**Impact**: Medium (reduces clutter)

These scripts were one-time JSX migration tools that directly modify `App.jsx` in-place. They are not referenced by any build process (`package.json`, `start.sh`, or Vite config).

**Files to DELETE**:
- `frontend-react/fix_nested.py` (185 lines)
- `frontend-react/fix_nested_safe.py` (126 lines)
- `frontend-react/replace_script.py` (49 lines)
- `frontend-react/replace_script2.py` (if exists)
- `frontend-react/update_firms.py` (67 lines)
- `frontend-react/update_gov_tab.py` (171 lines)
- `frontend-react/update_subjects_tab.py` (110 lines)
- `frontend-react/insert_distress_gauge.py` (if exists)

**Verification**: All scripts directly `open('src/App.jsx', 'r')` and modify the file in-place. Not imported or called anywhere.

---

### 1.2 Delete Audit Dump Artifacts
**Priority**: HIGH  
**Risk**: None (generated artifacts)  
**Impact**: Low (repo cleanliness)

These are generated audit files that should not be version-controlled.

**Files to DELETE**:
- `audit_full_dump_latest.md` (repo root)
- `audit_full_dump_digest.md` (repo root)
- `audit_full_dump_digest.json` (repo root)
- `audit_full_dump_latest.jsonl` (repo root)
- `backend/audit_full_dump_digest.md` (backend/)
- `backend/audit_full_dump_digest.json` (backend/)

---

### 1.3 Fix README.md Documentation Errors
**Priority**: HIGH  
**Risk**: None (documentation only)  
**Impact**: Medium (accuracy)

**Confirmed Issues to Fix**:
1. **Testing paths** (line 110): Change `backend/data/tests` to `backend/tests_contracts/` and `backend/tests_server/`
   - Verification: Grep found `backend/data/tests` does NOT exist; actual dirs are `backend/tests_contracts/` and `backend/tests_server/`
2. **Add note**: Clarify that `start.sh`/`start.ps1` must be run from project root (line 33-34)

**Note on warmup_ticks**: `config.py:16` shows default is 10, but `README.md` doesn't mention warmup_ticks default. The `economy.py:71` has fallback of 52. No change needed to README.md for this item.

**Files to Edit**:
- `README.md`

---

## Phase 2: Medium-Risk Improvements (Low Risk, Structural Improvements)

**Goal**: Consolidate duplicated logic and move configuration to proper locations. All changes are mechanical with low risk.

### 2.1 Consolidate Good Category Inference
**Priority**: MEDIUM  
**Risk**: Low (mechanical, no behavior change)  
**Impact**: Medium (reduces duplication)

**Current Duplication (CONFIRMED)**:
| Location | Function | Lines |
|---------|----------|-------|
| `backend/agents.py:21-37` | `_get_good_category()` | Module-level function |
| `backend/server.py:414-423` | `_infer_sector_from_good()` | Static method |
| `backend/economy.py:2920-2922` | `_build_good_category_lookup()` | Third mechanism |

**Approved Action**:
1. Check if `backend/utils/` directory exists
   - If not: Create `backend/utils/__init__.py` and `backend/utils/category_utils.py`
   - If yes: Only add `backend/utils/category_utils.py`
2. Create `backend/utils/category_utils.py` with `get_good_category()` function (move logic from `agents.py:21-37`)
3. Update `backend/agents.py`:
   - Remove local `_get_good_category()` (lines 21-37)
   - Add import: `from utils.category_utils import get_good_category`
4. Update `backend/economy.py`:
   - Change import at line 23: `from agents import ..., _get_good_category` → `from utils.category_utils import get_good_category`
   - Update all call sites from `_get_good_category(...)` to `get_good_category(...)`
   - Review `_build_good_category_lookup()` at line 2920-2922 (either route through new util or document why not)
5. Update `backend/server.py`:
   - Remove `_infer_sector_from_good()` static method (lines 414-423)
   - Add import: `from utils.category_utils import get_good_category`
   - Update all call sites (lines 769, 801, 1869, 1924)

**Test Required**: `pytest backend/tests_contracts/ -v` and `pytest backend/tests_server/ -v`

---

### 2.2 Move Shock Magic Numbers to Config
**Priority**: MEDIUM  
**Risk**: Low (mechanical, defaults match exactly)  
**Impact**: Medium (configurability)

**Current Hardcoded Values in `backend/economy.py`**:
| Literal | Location | Description |
|---------|----------|-------------|
| `base_transfer = 40.0` | `_apply_post_warmup_stimulus()` | Post-warmup stimulus amount |
| `_rng.random() < 0.05` | `_apply_random_shocks()` | Demand shock probability |
| `_rng.random() < 0.03` | `_apply_random_shocks()` | Supply shock probability |
| `_rng.random() < 0.02` | `_apply_random_shocks()` | Health shock probability |
| `_rng.uniform(-50, 100)` | `_apply_random_shocks()` | Demand shock range |
| `_rng.uniform(0.85, 1.15)` | `_apply_random_shocks()` | Supply shock range |

**Approved Action**:
1. Add new dataclass to `backend/config.py` (after line 768):
   ```python
   @dataclass
   class ShockConfig:
       """Stochastic shock parameters for the economy."""
       post_warmup_transfer_per_household: float = 40.0
       demand_shock_probability: float = 0.05
       supply_shock_probability: float = 0.03
       health_shock_probability: float = 0.02
       demand_shock_min: float = -50.0
       demand_shock_max: float = 100.0
       supply_shock_min: float = 0.85
       supply_shock_max: float = 1.15
   ```

2. Add to `SimulationConfig` class in `backend/config.py` (line 701-714):
   - `shocks: ShockConfig = field(default_factory=ShockConfig)`

3. Update `backend/economy.py` (grep and replace each occurrence):
   - `base_transfer = 40.0` → `base_transfer = CONFIG.shocks.post_warmup_transfer_per_household`
   - `_rng.random() < 0.05` → `_rng.random() < CONFIG.shocks.demand_shock_probability`
   - `_rng.random() < 0.03` → `_rng.random() < CONFIG.shocks.supply_shock_probability`
   - `_rng.random() < 0.02` → `_rng.random() < CONFIG.shocks.health_shock_probability`
   - `_rng.uniform(-50, 100)` → `_rng.uniform(CONFIG.shocks.demand_shock_min, CONFIG.shocks.demand_shock_max)`
   - `_rng.uniform(0.85, 1.15)` → `_rng.uniform(CONFIG.shocks.supply_shock_min, CONFIG.shocks.supply_shock_max)`

**Constraint**: Default values must match current literals exactly — no behavior change.

**Test Required**: `pytest backend/tests_contracts/ -v` and `pytest backend/tests_server/ -v`

---

### 2.3 Fix prev_gov_cash Dynamic Attribute
**Priority**: MEDIUM  
**Risk**: Low (proper initialization)  
**Impact**: Low (code quality)

**Current Issue (CONFIRMED)**:
In `backend/server.py:1817`:
```python
if not hasattr(self, 'prev_gov_cash'):
    self.prev_gov_cash = current_gov_cash
```
This pattern of dynamically adding attributes is fragile.

**Approved Action**:
1. Open `backend/server.py`
2. Find `SimulationManager.__init__()` method (around line 350)
3. Add initialization inside `__init__()`:
   ```python
   def __init__(self):
       # ... existing initialization ...
       self.prev_gov_cash = 0.0  # Initialize to avoid dynamic attribute creation
       # ... rest of init ...
   ```
4. Remove the `hasattr` check in `run_loop()` (around line 1817)

**Test Required**: `pytest backend/tests_contracts/ -v` and `pytest backend/tests_server/ -v`

---

### 2.4 Add Integration Smoke Test
**Priority**: HIGH  
**Risk**: Low (test-only, no production code changes)  
**Impact**: Medium (regression detection)

**Approved Action**:
1. **Pre-Check**: Grep `backend/economy.py` for actual public method name:
   - Search pattern: `def get_*metrics|def compute_*metrics|def economic_*`
   - Do NOT assume method names or metric keys

2. Create new test file: `backend/tests_contracts/test_contracts_integration_smoke.py`

3. Add ONE integration smoke test using actual API discovered via grep:
   - Create small economy using actual factory (reference `backend/tools/runners/run_large_simulation.py:create_large_economy()`)
   - Run 10 ticks using actual method name (e.g., `economy.step()`)
   - Assert no exceptions raised
   - Get actual metrics using real method name
   - Verify metrics exist and are valid (use actual key names from code)

4. Run existing contract tests to ensure no regressions:
   - `pytest backend/tests_contracts/ -v`
   - `pytest backend/tests_server/ -v`

**Constraint**: Test-only change — no production code modifications. Must use real API.

---

## Phase 3: Higher-Risk Refactoring (Structural Changes)

**Note**: Per CLEANUP_AUDIT.md constraints, the following items are **deferred indefinitely**:
- 🚫 Split economy.py (5769 lines) into modules
- 🚫 Split agents.py (5718 lines) into separate agent files
- 🚫 Extract SimulationManager persistence logic into separate class
- 🚫 Any large structural rewrites

**Current Status**: No higher-risk refactoring items approved at this time.

---

## Phase 4: Documentation Updates (After Code Steps 1-7 Complete)

**Goal**: Fix all documentation errors identified in DOCUMENTATION_AUDIT.md. All changes are documentation-only with zero risk.

**IMPORTANT**: Documentation fixes come AFTER code steps 1-7 ship (to avoid merge conflicts and mid-refactor doc drift).

### 4.1 Fix SIMULATION.md Errors
**Priority**: HIGH  
**Risk**: None (documentation only)  
**Impact**: Medium (accuracy)

**Confirmed Issues to Fix**:
1. **Remove non-existent method references**:
   - Delete reference to `_plan_labor_adjustment()` (CONFIRMED: does not exist in codebase)
   - Delete reference to `adjust_wages_if_overpaying()` (CONFIRMED: does not exist in codebase)
   - Note: `adjust_wages_to_revenue_ratio()` exists in `agents.py` - keep reference if present
2. **Fix `maybe_active_education()` return type** (CONFIRMED):
   - Change docstring from "returns bool" to "returns float (cost paid)"
   - Verification: `agents.py:1913-1932` shows return `cost` (float) or `0.0`

**Files to Edit**:
- `docs/SIMULATION.md`

**Note**: SIMULATION.md tick lifecycle shows 21 phases (lines 226-249). The `economy.py:863-876` docstring shows 12 phases. These are different views of the same process. No change needed unless phases are misnumbered.

---

### 4.2 Fix FRONTEND.md Errors
**Priority**: HIGH  
**Risk**: None (documentation only)  
**Impact**: Medium (accuracy)

**Confirmed Issues to Fix**:
1. **Population scale limit** (CONFIRMED): Change "100-3,000 households" to "3-100,000 households"
   - Verification: `server.py:147` shows `num_households: int = Field(default=1000, ge=3, le=100_000)`
2. **Add Neural visualization components**: Document `NeuralAvatar.jsx`, `NeuralBuilding.jsx`, `NeuralGovernment.jsx`
3. **Verify tick metrics payload** (POSSIBLE issue P1): Grep `server.py` for actual payload structure before documenting

**Files to Edit**:
- `docs/FRONTEND.md`

---

### 4.3 Keep agents.py "Deterministic" Docstring (No Change Needed)
**Priority**: N/A  
**Risk**: N/A  
**Impact**: N/A  

**Verification Result**: The claim that "Behavior is deterministic when seeded" at `agents.py:72` is **CORRECT**.
- Code uses `random.Random(CONFIG.random_seed + ...)` throughout (`agents.py`, `economy.py`)
- Same seed produces same results → behavior IS deterministic when seeded
- **NO CHANGE NEEDED** - DOCUMENTATION_AUDIT.md was wrong about this being "misleading"

---

### 4.4 Fix Archive Documentation
**Priority**: LOW  
**Risk**: None (documentation only)  
**Impact**: Low (historical accuracy)

**Confirmed Issues to Fix**:
1. **DATA_ENGINEERING_PLAN.md**:
   - Change "Flask for API" to "FastAPI" (line 158, verification: `server.py:126` shows FastAPI)
   - Change "SQLAlchemy" to "Pydantic/dataclasses" (line 157, verification: `data/models.py` uses Pydantic/dataclasses)
2. **DYNAMIC_FEATURES.md**:
   - Update `skill_growth_rate` to reflect range `(0.0005, 0.002)` (line 174, verification: `config.py:105`)
3. **DATA_STORAGE_ARCHITECTURE.md**:
   - Fix migration numbering references (line 126, verification: migrations are now 001-016)

**Add "STALE" Warning Banners** (DO NOT modify archive body content):
Add to top of these files:
```markdown
> **WARNING: This document is STALE and kept for historical reference only.**
> It may contain outdated information. For current documentation, see [docs/README.md](docs/README.md).
```

Target files:
- `docs/archive/DYNAMIC_FEATURES.md`
- `docs/archive/DATA_SPECIFICATION.md` (old)
- `docs/archive/DATA_ENGINEERING_PLAN.md`
- `docs/archive/DATA_ENG_IMPLEMENTATION_ROADMAP.md`

---

### 4.5 Minimal Documentation Pass (Additive, After Step 7)
**Priority**: LOW  
**Risk**: None (additive)  
**Impact**: Low (code clarity)

**Approved Action (from CLEANUP_AUDIT.md Item 7)**:
1. **Add module-level docstring** to top of each file if missing (one paragraph each):
   - `backend/agents.py` — Describe responsibility and key public exports
   - `backend/economy.py` — Describe responsibility and key public exports
   - `backend/server.py` — Describe responsibility and key public exports
   - `backend/config.py` — Describe responsibility and key public exports

2. **Add class-level docstring** to each class if missing (2-4 lines each):
   - `HouseholdAgent` (grep confirmed at `agents.py:67`)
   - `FirmAgent` (grep confirmed at `agents.py:2153`)
   - `BankAgent` (grep confirmed at `agents.py:4588`)
   - `GovernmentAgent` (grep confirmed at `agents.py:4895`)
   - `Economy` (grep confirmed at `economy.py:28`)
   - `SimulationManager` (grep confirmed at `server.py:330`)

3. **Constraints**:
   - Do NOT add method docstrings
   - Do NOT add type hints
   - Do NOT touch existing docstrings
   - Pure additions only

4. **Commit separately**

5. **Run contract tests**: `pytest backend/tests_contracts/ -v`

---

### 4.6 Verify and Fix POSSIBLE Issues (Optional)
**Priority**: LOW  
**Risk**: None (documentation only, after verification)  
**Impact**: Low (accuracy)

**Items to Verify**:
1. **P1**: FRONTEND.md tick metrics payload field names — grep `server.py` for actual payload structure
2. **P2**: BANKING_SYSTEM.md phase numbering — compare with actual economy.py step() implementation
3. **P3**: FIRM_DYNAMICS.md `smoothed_profit_margin` — search `agents.py` and `economy.py`
4. **P4**: FIRM_DYNAMICS.md `category_wage_anchor_p75` — search `agents.py` and `economy.py`
5. **P5**: TECHNICAL.md missing `tools/` documentation — review `backend/tools/` structure
6. **P6**: DATA_STORAGE_ARCHITECTURE.md migration numbering — verify `backend/data/migrations/`

**Action**: For each verified issue, update the corresponding documentation file. Skip if verification fails.

---

## Summary of Work by Phase

| Phase | Description | Items | Risk Level | Test Run Required |
|-------|-------------|-------|------------|---------------------|
| **Phase 1** | Quick wins (dead code removal, obvious fixes) | 1.1, 1.2, 1.3 | None | No |
| **Phase 2** | Medium-risk improvements (consolidation, config) | 2.1, 2.2, 2.3, 2.4 | Low | Yes |
| **Phase 3** | Higher-risk refactoring | None (deferred) | N/A | N/A |
| **Phase 4** | Documentation updates (AFTER Phase 2 completes) | 4.1, 4.2, 4.3 (no-op), 4.4, 4.5, 4.6 | None | Yes (for 4.5) |

---

## Execution Order (Strict)

Per CLEANUP_AUDIT.md, approved cleanup items must be executed in this strict order:

### Code Steps (Do First)
1. **Step 1**: Delete dead frontend scripts (1.1) — No test run needed
2. **Step 2**: Delete audit dump artifacts (1.2) — No test run needed
3. **Step 3**: Consolidate category utils (2.1) — **Run tests**
4. **Step 4**: Move shocks to config (2.2) — **Run tests**
5. **Step 5**: Fix prev_gov_cash init (2.3) — **Run tests**
6. **Step 6**: Add smoke test (2.4) — **Run tests**
7. **Step 7**: Minimal doc pass (4.5) — **Run tests**

### Documentation Steps (Do After Step 7 Ships)
8. **Step 8**: Fix README.md (1.3) — No test run needed
9. **Step 9**: Fix SIMULATION.md (4.1) — No test run needed
10. **Step 10**: Fix FRONTEND.md (4.2) — No test run needed
11. **Step 11**: Fix archive docs (4.4) — No test run needed
12. **Step 12**: Verify POSSIBLE issues (4.6) — No test run needed

**After each step**: Run `pytest backend/tests_contracts/ -v` and `pytest backend/tests_server/ -v` (for code steps). Stop and report if any tests fail.

---

## Deferred Items (DO NOT IMPLEMENT)

Per reviewer constraints, the following items are **deferred indefinitely**:
- 🚫 Split economy.py (5769 lines) into modules
- 🚫 Split agents.py (5718 lines) into separate agent files
- 🚫 Extract SimulationManager persistence logic into separate class
- 🚫 Fix typos in variable names (agents.py)
- 🚫 Standardize JSON key naming conventions
- 🚫 Add type hints to all public methods
- 🚫 Add docstrings to all public methods (only minimal pass approved)
- 🚫 Any other items from the full audit not explicitly listed above

---

## Verification Methodology

For each refactoring step:
1. **Before**: Read the relevant code to confirm the issue exists
2. **During**: Make the minimal change required
3. **After**: Run contract tests to verify no regressions
4. **Commit**: Each step separately for easy rollback

For documentation fixes:
1. **Before**: Verify against actual code (grep/search as needed)
2. **During**: Update documentation to match code reality
3. **After**: No tests needed (documentation only)

---

*End of REFACTOR_PLAN.md*  
*Generated: 2026-05-04*  
*Based on: PROJECT_MAP.md, DOCUMENTATION_AUDIT.md, CLEANUP_AUDIT.md*  
*Verification: All documentation claims grep-verified against current source*
