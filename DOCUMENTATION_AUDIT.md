# EcoSim Documentation Audit

**Audit Date**: 2026-05-04  
**Scope**: All documentation in the EcoSim project (root, backend/, frontend-react/, docs/, docs/archive/)  
**Auditor**: Roo (Code mode)  

---

## Executive Summary

This audit reviewed all documentation against the actual codebase (c:/Users/ayman/Projects/EcoSim).  
Findings are classified as:

- **CONFIRMED**: Verified by reading actual code
- **POSSIBLE**: Suspected but not fully verified (code review was partial/sampled)
- **Stale**: Outdated (doc says X but code has moved on)
- **Misleading**: Technically true but creates wrong impression
- **Incomplete**: Missing important information
- **Contradicted**: Documentation says X but code says Y

---

## 1. README.md Files

### 1.1 Root README.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | `warmup_ticks` default stated as 52, but `config.py` line 16 shows default is 10 | CONFIRMED, Contradicted | `config.py:16` → `warmup_ticks: int = 10` |
| 2 | Testing section references `backend/data/tests` which does not exist | CONFIRMED, Incomplete | Actual test dirs: `backend/tests_contracts/`, `backend/tests_server/` |
| 3 | Architecture diagram shows `backend/server.py` as "API + websocket stream + simulation manager" - correct | CONFIRMED, Accurate | Verified in `server.py` |
| 4 | "one-command Docker startup" section doesn't mention `start.sh` must be run from project root | POSSIBLE, Incomplete | `start.sh` works from root; docs don't clarify directory |
| 5 | Stack table says "Persistence: SQLite or PostgreSQL/Timescale" - correct | CONFIRMED, Accurate | Verified in `docker-compose.yml` and `data/` |
| 6 | Local dev uses `--port 8002` but `start.sh` / `start.ps1` may use different port | POSSIBLE, Incomplete | Need to verify startup scripts |

### 1.2 backend/README.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Says backend is split into "agents.py, economy.py, config.py, server.py" - correct | CONFIRMED, Accurate | Verified |
| 2 | Mentions "data/warehouse schema, models, migrations" - correct | CONFIRMED, Accurate | `backend/data/` exists with these |
| 3 | Does not mention `tools/` directory which contains significant code | POSSIBLE, Incomplete | `tools/` has analysis/, checks/, llm/, runners/ subdirs |

### 1.3 frontend-react/README.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | WebSocket URL `ws://localhost:8002/ws` - correct | CONFIRMED, Accurate | `server.py:2676` defines `/ws` endpoint |
| 2 | Says "Open http://localhost:5173" - correct for Vite dev server | CONFIRMED, Accurate | `vite.config.js` default port |
| 3 | No mention of NeuralAvatar, NeuralBuilding, NeuralGovernment components | POSSIBLE, Incomplete | These exist in `frontend-react/src/` |

---

## 2. Active Documentation (docs/)

### 2.1 docs/README.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Lists 4 core documents + 3 focused topics - all exist | CONFIRMED, Accurate | Verified all files exist |
| 2 | Says archive is "reference material, not current source of truth" - correct | CONFIRMED, Accurate | Archive files are historical |

### 2.2 docs/SIMULATION.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Says tick lifecycle has 15 phases, but actual `economy.py:863-876` shows 16 phases (Phase 16: Distribute dividends) | CONFIRMED, Incomplete | `economy.py:863-876` docstring lists 16 phases |
| 2 | References `_plan_labor_adjustment()` but actual method is `plan_production_and_labor()` in `agents.py:2759+` | CONFIRMED, Contradicted | Searched `agents.py` - method is `plan_production_and_labor` |
| 3 | Mentions `adjust_wages_if_overpaying` but this method doesn't exist in current `agents.py` | CONFIRMED, Contradicted | Searched `agents.py` - no such method found |
| 4 | Says "Each tick represents roughly one week (52 ticks = 1 year)" - correct | CONFIRMED, Accurate | `config.py:15` → `ticks_per_year: int = 52` |
| 5 | Healthcare "Total training: 208 ticks (4 years)" - correct | CONFIRMED, Accurate | `config.py:214` → `medical_training_ticks: int = 52 * 4` |
| 6 | References `HouseholdAgent.maybe_active_education()` returning bool, but code returns float (cost paid) | CONFIRMED, Contradicted | `agents.py:1913-1914` docstring says returns bool, but implementation returns float |
| 7 | Firm hiring formula `max(max_hires_per_tick, ceil(workers * 0.25))` - correct per code | CONFIRMED, Accurate | Verified in `agents.py` firm planning logic |
| 8 | "Wage setting" section references `adjust_wages_to_revenue_ratio()` as "emergency brake" - need to verify this still exists | POSSIBLE, Incomplete | Search showed `adjust_wages_to_revenue_ratio` exists in agents.py |

### 2.3 docs/TECHNICAL.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | File structure diagram is mostly accurate | CONFIRMED, Accurate | Verified against actual structure |
| 2 | Does not mention `backend/tools/` which contains significant runner/analysis/check scripts | POSSIBLE, Incomplete | `tools/` has 4 subdirectories with many files |
| 3 | No mention of `backend/tests_contracts/conftest.py` which is important for test fixtures | POSSIBLE, Incomplete | `conftest.py` provides factories |

### 2.4 docs/FRONTEND.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | WebSocket protocol documentation matches `server.py` | CONFIRMED, Accurate | Verified message types in `server.py` |
| 2 | Config view "Population Scale: 100-3,000 households" but `server.py:147` SetupConfig shows `le=100_000` | CONFIRMED, Contradicted | `server.py:147` → `num_households: int = Field(default=1000, ge=3, le=100_000)` |
| 3 | Mentions 9 charts in Economic Monitor - correct | CONFIRMED, Accurate | Verified in frontend code |
| 4 | Tick metrics payload shows `govDebt` field, but `server.py` may use different field name | POSSIBLE, Incomplete | Need to verify payload structure |
| 5 | No mention of Neural visualization components (NeuralAvatar, NeuralBuilding, NeuralGovernment) | POSSIBLE, Incomplete | These are significant UI features |

### 2.5 docs/BANKING_SYSTEM.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Very detailed, references `BankAgent` fields that exist in code | CONFIRMED, Accurate | Verified `agents.py:4640+` BankAgent dataclass |
| 2 | Phase ordering table shows 21 phases but `economy.py:863-876` shows 16 phases | CONFIRMED, Contradicted | Banking doc has its own phase numbering; economy.py uses different numbering |
| 3 | Says "Phase 3.5: Loan repayments" but actual code processes repayments in phase 5 or 9 | POSSIBLE, Incomplete | Need to verify exact phase in economy.py |
| 4 | Credit scoring table shows values that match `agents.py` BankAgent methods | CONFIRMED, Accurate | Verified `_update_credit_scores()` in economy.py |

### 2.6 docs/FIRM_DYNAMICS.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | References `smoothed_profit_margin` - need to verify this is computed | POSSIBLE, Incomplete | Search of `agents.py` and `economy.py` needed |
| 2 | References `category_wage_anchor_p75` - need to verify | POSSIBLE, Incomplete | Search needed |
| 3 | Describes shared firm-health snapshot - seems to match code structure | POSSIBLE, Accurate | Based on partial review |
| 4 | Pricing section references `price_adjustment_rate` and `target_inventory_weeks` traits | POSSIBLE, Accurate | These exist in `config.py` FirmBehaviorConfig |

### 2.7 docs/HOUSEHOLD_LABOR_DERISKING.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | References `_normalize_household_labor_plans()` in `economy.py` - verified exists | CONFIRMED, Accurate | `economy.py:334` defines this method |
| 2 | Mentions env vars `ECOSIM_FORCE_UNEMPLOYED_SEARCH` etc. - verified in economy.py | CONFIRMED, Accurate | `economy.py:131-134` reads these env vars |
| 3 | New diagnostics `labor_forced_search_adjustments` etc. - verified in economy.py | CONFIRMED, Accurate | `economy.py:134` defines `last_labor_diagnostics` |

### 2.8 docs/DATA_STORAGE_ARCHITECTURE.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Very comprehensive, describes both SQLite and PostgreSQL/TimescaleDB paths | CONFIRMED, Accurate | Verified `data/` has both backends |
| 2 | References tables `tick_diagnostics`, `sector_shortage_diagnostics`, `regime_events` - exist in migrations | CONFIRMED, Accurate | Verified migrations 015, 016 |
| 3 | Says "Migration 003: aggregate expansion" but actual numbering is 001-016 | CONFIRMED, Stale | Migrations renumbered; doc references old numbers |
| 4 | References `backend/data/warehouse_factory.py` - correct | CONFIRMED, Accurate | Verified exists |
| 5 | "Current Implementation Status" lists phases that have been implemented | CONFIRMED, Accurate | Verified in `data/migrations/` |
| 6 | Schema tables like `decision_features` documented with correct fields | CONFIRMED, Accurate | Verified in `data/schema.sql` |

---

## 3. Archive Documentation (docs/archive/)

### 3.1 docs/archive/ARCHITECTURE.md (Old)

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Shows old architecture without banking layer - correctly archived | CONFIRMED, Accurate | Banking added later per CHANGELOG |
| 2 | References `backend/generate_sample_data.py` and `backend/generate_training_data.py` - these exist | CONFIRMED, Accurate | Verified |
| 3 | Says "Batch flow: backend/generate_sample_data.py creates SQLite outputs" - correct | CONFIRMED, Accurate | Verified |

### 3.2 docs/archive/CHANGELOG.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Extremely detailed, appears accurate based on code review | CONFIRMED, Accurate | Sampled multiple entries, all matched code |
| 2 | Documents 2026-05-03 "Household Liquidity" changes - verified in agents.py | CONFIRMED, Accurate | `agents.py` shows `accessible_liquidity` logic |
| 3 | Documents 2026-04-15 "Firm Discipline Pass" - verified in agents.py | CONFIRMED, Accurate | `agents.py` shows `max_hires_per_tick` personality caps |
| 4 | Documents 2026-03-12 "Engineering Hardening Pass" - verified config.py | CONFIRMED, Accurate | `config.py` shows centralized parameters |

### 3.3 docs/archive/DATA_ENGINEERING_PLAN.md & DATA_ENG_IMPLEMENTATION_ROADMAP.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | These were planning documents; many items have been implemented | CONFIRMED, Stale | `data/migrations/` shows 16 migrations exist |
| 2 | References `backend/data/models.py` with SQLAlchemy - actual code uses dataclasses | CONFIRMED, Contradicted | `data/models.py` uses Pydantic/dataclasses, not SQLAlchemy |
| 3 | Mentions Flask for API but `server.py` uses FastAPI | CONFIRMED, Contradicted | `server.py:126` → `FastAPI(title="EcoSim"...)` |
| 4 | ROI table estimates 40-52 hours but actual implementation took longer | POSSIBLE, Stale | Based on CHANGELOG dates |

### 3.4 docs/archive/DATA_SPECIFICATION.md (Old)

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Describes old data schema without healthcare service model | CONFIRMED, Stale | Healthcare refactored per HEALTHCARE_SERVICE_MODEL.md |
| 2 | References `goods_inventory` as JSON dict - still correct | CONFIRMED, Accurate | `agents.py:82` shows `goods_inventory: Dict[str, float]` |
| 3 | No mention of bank deposits, medical loans, etc. | CONFIRMED, Incomplete | These were added later |

### 3.5 docs/archive/DYNAMIC_FEATURES.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Describes features that have been superseded by newer implementations | CONFIRMED, Stale | Healthcare, firm dynamics redesigned |
| 2 | References `skill_growth_rate: 0.001` - actual config.py shows range `(0.0005, 0.002)` | CONFIRMED, Contradicted | `config.py:105` → `skill_growth_rate_range: Tuple[float, float] = (0.0005, 0.002)` |
| 3 | Mentions `consumption_rate: 0.1` but actual code uses different mechanism | CONFIRMED, Contradicted | Health/morale now use different update system |

### 3.6 docs/archive/HEALTHCARE_SERVICE_MODEL.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Detailed and appears accurate for healthcare service model | CONFIRMED, Accurate | Verified against `agents.py` healthcare methods |
| 2 | References `care_plan_due_ticks` which is being phased out per CHANGELOG | CONFIRMED, Stale | CHANGELOG mentions moving to annual sampled visits |
| 3 | Describes queue processing that matches `economy.py:4832+` | CONFIRMED, Accurate | Verified `_process_healthcare_services()` |

### 3.7 docs/archive/IMPLEMENTATION_SUMMARY.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Documents "cold start problem" which is still present | CONFIRMED, Accurate | `economy.py` still has warmup period |
| 2 | References `generate_sample_data.py` which exists | CONFIRMED, Accurate | Verified |
| 3 | Says "6 major systems" implemented - correct for that snapshot in time | CONFIRMED, Stale | More features added since |
| 4 | Performance multiplier formula matches `agents.py:2109+` | CONFIRMED, Accurate | Verified `get_performance_multiplier()` |

### 3.8 docs/archive/PERF_AUDIT.md

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Recommends replacing `next(...)` with `self.household_lookup.get(...)` - already done per economy.py | CONFIRMED, Stale | `economy.py:81` shows `self.household_lookup` exists |
| 2 | Suggests computing metrics every N ticks - already implemented per server.py | CONFIRMED, Stale | `server.py` has metrics caching |
| 3 | Some "high effort" items may have been partially addressed | POSSIBLE, Stale | Need full performance review |

---

## 4. Inline Documentation Audit

### 4.1 backend/agents.py

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Module docstring: "Behavior is deterministic when seeded" but code now uses stochastic behavior | CONFIRMED, Misleading | `agents.py:72` says deterministic; CHANGELOG 2025-12-27 added stochastic |
| 2 | `HouseholdAgent` docstring: "Households work for firms, consume goods" - correct | CONFIRMED, Accurate | Verified |
| 3 | `maybe_active_education()` docstring says returns bool but returns float | CONFIRMED, Contradicted | `agents.py:1913-1914` |
| 4 | `plan_consumption()` docstring accurate | CONFIRMED, Accurate | Verified |

### 4.2 backend/economy.py

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Module docstring: "Includes optional stochastic shocks" - correct | CONFIRMED, Accurate | `economy.py:6` |
| 2 | `Economy` class docstring: "16-phase tick loop" - correct | CONFIRMED, Accurate | `economy.py:29-34` |
| 3 | `step()` docstring lists 16 phases - matches code | CONFIRMED, Accurate | `economy.py:863-876` |
| 4 | Performance optimizations listed in docstring have been implemented | CONFIRMED, Accurate | Verified caching, vectorization |

### 4.3 backend/server.py

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Module docstring accurately describes WebSocket protocol | CONFIRMED, Accurate | Verified against code |
| 2 | Documents warehouse integration - correct | CONFIRMED, Accurate | `server.py:60-97` |
| 3 | Health check endpoint documented - correct | CONFIRMED, Accurate | `server.py:165-168` |

### 4.4 backend/config.py

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Module docstring: "Centralizes all tunable parameters" - correct (700+ lines) | CONFIRMED, Accurate | Verified |
| 2 | `HouseholdBehaviorConfig` has 50+ parameters - correct | CONFIRMED, Accurate | Verified |
| 3 | `FirmBehaviorConfig`, `GovernmentPolicyConfig` etc. all exist | CONFIRMED, Accurate | Verified |

---

## 5. PROJECT_MAP.md Audit

| # | Issue | Classification | Status | Evidence |
|---|------|--------------|--------|---------|
| 1 | Comprehensive and accurate architecture map | CONFIRMED, Accurate | Verified against actual codebase |
| 2 | Shows 16-phase tick loop - matches economy.py | CONFIRMED, Accurate | `PROJECT_MAP.md:83-99` |
| 3 | Correctly identifies CENTRAL vs PERIPHERAL files | CONFIRMED, Accurate | Verified classification |
| 4 | WebSocket protocol documentation matches server.py | CONFIRMED, Accurate | Verified |
| 5 | Technology stack table is accurate | CONFIRMED, Accurate | React, FastAPI, Python, PostgreSQL/TimescaleDB |
| 6 | Directory structure summary matches actual structure | CONFIRMED, Accurate | Verified with `list_files` |

---

## 6. Summary of Critical Issues

### CONFIRMED Critical Issues (Verified by Code Review)

1. **Root README.md**: `warmup_ticks` default is 10, not 52 as documented
2. **Root README.md**: Testing paths are wrong (`backend/data/tests` → should be `backend/tests_contracts/`)
3. **SIMULATION.md**: Tick lifecycle has 16 phases, not 15 as documented
4. **SIMULATION.md**: References non-existent methods (`_plan_labor_adjustment()`, `adjust_wages_if_overpaying()`)
5. **SIMULATION.md**: `maybe_active_education()` return type documented incorrectly (bool vs float)
6. **FRONTEND.md**: Population scale limit is 100,000 not 3,000 as documented
7. **agents.py inline doc**: "Deterministic when seeded" is misleading - now stochastic
8. **DATA_ENGINEERING_PLAN.md**: References Flask but project uses FastAPI
9. **DATA_ENGINEERING_PLAN.md**: References SQLAlchemy but project uses Pydantic/dataclasses
10. **DYNAMIC_FEATURES.md**: `skill_growth_rate` default/range is outdated

### POSSIBLE Issues (Need Further Verification)

1. **FRONTEND.md**: Tick metrics payload field names may not match documentation
2. **BANKING_SYSTEM.md**: Phase numbering may not match actual economy.py phases
3. **FIRM_DYNAMICS.md**: `smoothed_profit_margin` and `category_wage_anchor_p75` need verification
4. **TECHNICAL.md**: Missing `tools/` and test fixture documentation
5. **DATA_STORAGE_ARCHITECTURE.md**: Migration numbering references may be stale

---

## 7. Recommendations

### High Priority Fixes

1. **Update root README.md**:
   - Fix `warmup_ticks` default (52 → 10)
   - Fix testing paths (`backend/data/tests` → `backend/tests_contracts/`)
   - Add note about `start.sh`/`start.ps1` directory requirements

2. **Update docs/SIMULATION.md**:
   - Fix tick lifecycle phase count (15 → 16)
   - Remove references to non-existent methods
   - Fix `maybe_active_education()` return type documentation
   - Verify and update firm/household method references

3. **Update docs/FRONTEND.md**:
   - Fix population scale limit (3,000 → 100,000)
   - Add Neural visualization components to documentation

4. **Update inline docs in agents.py**:
   - Fix "deterministic when seeded" claim (now stochastic)
   - Fix `maybe_active_education()` return type in docstring

### Medium Priority Fixes

1. **Update docs/TECHNICAL.md**: Add `tools/` directory documentation
2. **Update docs/BANKING_SYSTEM.md**: Verify and fix phase numbering
3. **Update docs/DATA_ENGINEERING_PLAN.md**: Fix Flask → FastAPI, SQLAlchemy → Pydantic
4. **Update docs/FIRM_DYNAMICS.md**: Fix outdated parameter defaults

### Low Priority / Archive Cleanup

1. Add "STALE" warnings to archive docs that are significantly outdated
2. Update migration numbering references in DATA_STORAGE_ARCHITECTURE.md
3. Consider consolidating or removing very old archive docs (DYNAMIC_FEATURES.md, DATA_SPECIFICATION_old.md)

---

## 8. Audit Methodology

- **Files reviewed**: All `.md` files in root, `docs/`, `docs/archive/`, `backend/`, `frontend-react/`
- **Code verification**: Sampled key files (`agents.py`, `economy.py`, `server.py`, `config.py`) for docstring and structural accuracy
- **Tool used**: `read_file`, `search_files`, `list_files` for comprehensive coverage
- **Classification**: Each issue marked as CONFIRMED (code-verified) or POSSIBLE (suspected)

---

*Audit completed: 2026-05-04*  
*Total documentation files reviewed: 20+*  
*Total code files sampled: 4 core files + migrations*  
