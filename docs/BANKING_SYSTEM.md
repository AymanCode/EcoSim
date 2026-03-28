# EcoSim 2.0 — Banking System Design Document

## 1. Purpose and Vision

The `BankAgent` introduces a credit channel to the EcoSim economy. Before the bank, the economy had no monetary dimension — cash existed and moved between agents, but there was no credit creation, no savings, no interest, and no debt dynamics. Firms could only grow from accumulated revenue, unemployment caused immediate spending collapse with no buffer, and the government was doing banking work (emergency loans, seed loans) through the wrong agent.

The bank exists to **make fiscal policy interesting**. When the LLM government agent adjusts tax rates or subsidies, those decisions now ripple through a credit channel: tax changes affect firm cash flow, which affects borrowing capacity, which affects hiring and investment. Without the bank, the government's 7 policy levers operate in a partial vacuum. With it, policy decisions have deeper, delayed, and less predictable consequences — exactly the kind of environment where an LLM policy agent can demonstrate real reasoning.

### Design Principles

**The bank is an add-on, not a dependency.** The simulation must run identically if the bank is disabled. No firm logic requires a loan to function. Borrowing is an enhancement to cash-constrained decisions, never a requirement. Setting `self.bank = None` reverts the entire economy to pre-bank behavior. Every loan migration from government to bank follows a try-bank-first, fall-back-to-government pattern.

**Minimum viable credit system.** This is not a fractional reserve banking simulation. There is one bank, one interest rate, no interbank market, no bond market, no money supply mechanics. The goal is the simplest system that creates a meaningful credit channel for fiscal policy to transmit through.

**The market filters firms, not a planning algorithm.** Firm creation is not centrally planned around "what the market needs." Firms spawn, most start small and underfunded, and the economy determines which survive through demand, competition, and access to credit. The bank's role is evaluating which firms deserve capital, not deciding how many firms should exist.

---

## 2. Architecture Overview

### What the Bank Owns

- Firm credit lines (revolving, revenue-backed commercial lending)
- Emergency loans (migrated from government — bank executes, government authorizes and subsidizes)
- Seed loans for new firms (migrated from government — bank provides capital, government guarantees)
- Inventory liquidation loans (migrated from government — now pure commercial banking, no government involvement)
- Medical/education loans (migrated from government — existing mechanic rerouted through bank)
- Household deposit accounts (excess cash earns interest)
- Credit scoring for firms and households

### What Stays with the Government

- Initial startup capitalization for baseline firms ($2M / $800K grants at simulation start — these are grants, not loans)
- Tax collection, benefits, subsidies, public works
- The 7-lever policy action space
- Authorization and rate subsidization for emergency and seed loan programs

### Clean Separation

The government influences the bank through one mechanism: a **base interest rate** that the bank adopts. This becomes a natural 8th policy lever for the future LLM government. The government does not bail out the bank, guarantee deposits, or override lending decisions. The bank does not collect taxes, pay benefits, or make policy decisions.

---

## 3. Firm Creation and Funding Tiers

### The Problem We Solved

The original simulation gave every new firm $50-250K in automatic seed capital. Combined with a firm creation target that could only ratchet upward (a bug where `target = max(current_count, ...)` meant the target never decreased), this produced 100-200 firms for 1000 households, drained government cash to -$2M, and exhausted bank reserves immediately.

### The Fix: Three-Tier Funding

Firms are independent agents — they are not attached to or owned by households. Funding at creation works as follows:

**Tier 1 — Bootstrapped** (majority, ~60-70% of new firms). Firm spawns with a small random starting capital drawn from a distribution, roughly $5K-30K. No loan, no grant. This represents a small business starting lean. Most die fast. The market does the filtering — firms that find customers survive, the rest don't.

**Tier 2 — Bank-backed** (~20-30% of new firms). The firm's target sector has measurable unmet demand. Bank issues a seed loan based on sector conditions and the firm's default credit score (0.5 for new firms). These firms start with more capital and better survival odds but carry debt from day one.

**Tier 3 — Government-backed** (~5-10%, special circumstances). High unemployment, critical sector underserved, or post-crisis recovery. Government authorizes a seed loan through the bank with subsidized interest rate. Rare by design.

### Ratchet Fix

The firm creation target is now **bidirectional**. It can decrease when firms die and demand doesn't justify replacements, driven by household-to-firm ratio and labor market signals rather than a one-way max of the current firm count.

### Results

After implementing this fix: firm count stabilized at 15 for 500 households (vs 59 before), government cash improved from -$1.5M to -$33K, and bank reserves remained healthy at $2.7M with only $58 in seed lending. The credit channel is available but dormant — it activates when economic conditions push firms to borrow.

---

## 4. Loan Products

### 4a. Commercial Firm Loans

**Purpose:** Firms borrow to fund hiring, investment, or inventory when they have growth opportunity but insufficient cash.

**Approval criteria:**
- Credit score >= 0.25 (not blacklisted)
- Leverage ceiling: total outstanding debt < 3x trailing 12-tick average revenue
- Amount capped at 10% of bank reserves per loan (concentration risk limit)

**Terms:**
- Rate: `base_interest_rate + (1.0 - credit_score) * 0.05` (risk premium)
- Term: 104 ticks (2 years)
- Simple interest: `total_repayment = principal * (1 + rate * years)`
- Repayment: equal installments per tick

**When firms borrow:** During production planning, a firm evaluates whether demand exceeds capacity and cash runway is below 8 weeks. If both conditions hold and the firm isn't in survival mode, it flags a loan request. The economy routes the request to the bank. Firms also cannot borrow if existing debt exceeds a leverage threshold relative to their cash balance.

### 4b. Emergency Loans (Migrated from Government)

**Trigger:** Firm cash < 2x weekly payroll AND credit score >= 0.25.

**New flow:** Economy detects unemployment above threshold -> economy calls bank to evaluate the loan -> bank provides capital at a government-subsidized rate (`base_rate * 0.25`, government covers 75% of interest cost) -> government pays the subsidy from its own cash -> hiring commitment enforcement stays in the economy.

**Fallback:** If bank cannot fund the loan (reserves insufficient), government issues it directly using pre-bank logic.

### 4c. Seed Loans (Migrated from Government)

**Purpose:** Capitalize new firms created during runtime (post-warmup).

**New flow:** Economy creates the firm -> bank provides seed capital as a loan -> government guarantees the loan (covers bank's loss if firm defaults).

**Terms:** $50K-250K at `base_interest_rate` (no risk premium for new firms), 156 ticks (3 years).

**Fallback:** Government funds directly if bank cannot.

### 4d. Inventory Liquidation Loans (Migrated from Government)

**Purpose:** Provide working capital to underselling firms with inventory buildup.

Now **pure commercial banking**. Bank identifies eligible firms and offers loans proactively. No government involvement, standard interest rate, same 3x revenue leverage ceiling. This is the only migrated loan type where the government has no role.

### 4e. Medical/Education Loans (Migrated from Government)

**Purpose:** Fund medical students during their education before they become earning professionals.

**Flow:** Student enters medical education -> bank issues education loan -> student graduates and begins earning -> repayments of 10% of minimum wage per tick -> default if student drops out or can't find work.

**Constraints:** One active medical loan per household (no stacking). Rate includes risk premium based on household credit score.

---

## 5. Credit Scoring

### Firm Credit Score

Range `[0.0, 1.0]`, initialized at 0.5 for new firms. Updated per-tick based on financial behavior.

| Signal | Effect |
|---|---|
| On-time repayment (per tick) | +0.01 |
| Missed payment | -0.05 |
| Default (bankruptcy) | -0.20 |
| Revenue > 2x payroll | +0.01 |
| Zero revenue for 4+ ticks | -0.03 |
| Existing debt > 3x trailing revenue | -0.02 |

**Design decisions:**

- **Buildup is slow** (+0.01/tick, ~50 ticks from 0.5 to 1.0) so credit scores remain a meaningful discriminator over time, not something every firm maxes out in 6 months.
- **Penalties are fast** (asymmetric by design) — trust is hard to earn and easy to lose.
- **Default penalty is -0.20** (not -0.30 as initially proposed). At -0.30, a single default from the 0.5 starting score drops a firm to 0.2, permanently below the 0.25 lending threshold. At -0.20, a defaulted firm drops to 0.3, just above threshold, and can claw back to creditworthiness in ~15 ticks of good behavior. The economy needs firms to recover from recessions, not spiral into permanent credit exclusion.
- **Two defaults triggers blacklisting** (permanent credit denial). This is the hard cutoff.

### Household Credit Score

Same range and initialization. Used primarily for medical/education loans.

| Signal | Effect |
|---|---|
| On-time repayment | +0.01 |
| Missed payment | -0.05 |
| Default | -0.20 |
| Employed continuously 8+ ticks | +0.01 |
| Unemployed 4+ ticks | -0.01 |

---

## 6. Household Deposits

Households with excess cash deposit into the bank, earning interest on their balance.

### How It Works

- **Threshold:** Households keep a buffer of liquid cash (varies per household based on `saving_tendency`) before depositing
- **Deposit fraction:** Only a portion of excess is deposited per tick (also varies per household)
- **Interest:** `deposit * (deposit_rate / 52)` per tick (annualized weekly)
- **Withdrawals:** Deposits are demand deposits, freely accessible

### Heterogeneous Savings Behavior

Each household has a `saving_tendency` drawn from a distribution at initialization. This controls both how much cash they keep liquid and how aggressively they save. The population average produces behavior equivalent to roughly keeping 6 weeks of expenses liquid and depositing about 20% of excess per tick, but individual households vary — some are aggressive savers, some barely save at all.

**Parameters derived from `saving_tendency` (st):**
- `deposit_buffer_weeks = 3.0 + 7.0 * st` — range [3, 10] weeks
- `deposit_fraction = 0.05 + 0.35 * st` — range [5%, 40%]

### Design History

The initial implementation used a uniform `(cash_balance - 2 * weekly_expenses) * 0.5` deposit formula, which was too aggressive. Households drained their spending cash into deposits faster than the bank could lend it back out, causing an economic contraction. The fix had two parts: raising the liquidity threshold, reducing the deposit fraction, and introducing per-household variation so deposits trickle into the bank gradually rather than as a synchronized wave.

### Spending and Deposits

Household spending power includes both cash and deposits. When purchasing, households draw from cash first. If cash is insufficient, they do not auto-withdraw from deposits — they spend what they have. Deposits are accessible but represent intentional savings, not a checking account. This keeps deposited money somewhat sticky, giving the bank a stable funding base for lending while not completely removing it from circulation.

---

## 7. Tick Ordering

Bank operations integrate into the economy's `step()` function with explicit phase ordering:

| Phase | Operation |
|---|---|
| 3 | Wage payments (firms -> households) |
| 3.5 | Loan repayments (firms/households -> bank) |
| 4 | Goods purchasing |
| 11 | Government taxes & transfers |
| 11.3 | Bank deposit sweep & interest |
| 11.5 | Bank lending decisions (replaces government loan methods) |
| 11.7 | Budget pressure update |

**Why repayments come after wages (Phase 3.5, not Phase 3):** Households and firms need wage income in hand before loan payments are deducted. If repayment runs first, a firm that just received revenue would show artificially low cash, triggering false survival-mode entries and potentially causing unemployment spikes as firms can't make payroll because the bank already took their cash.

---

## 8. Safety Mechanisms

### Debt Stacking Prevention

Two mechanisms prevent runaway debt:

1. **Leverage ceiling (firms):** Total debt outstanding must be < 3x trailing 12-tick average revenue. Checked at loan origination. If a new loan would breach this, the bank reduces the amount or denies.
2. **Single-loan cap (households):** Only one medical loan active at a time.
3. **Per-loan reserve cap:** No single loan can exceed 10% of bank reserves. Prevents single-borrower concentration risk.

### Circuit Breaker

If `cash_reserves < total_deposits * reserve_ratio`, the bank stops issuing new commercial loans until reserves recover through repayments and interest income.

**Exception:** Government-authorized emergency loans can still be issued during circuit breaker activation. In this case, funds come from government cash, not bank reserves. The bank is the execution channel; the government takes the risk. This prevents a death spiral where recession -> defaults -> reserves drop -> lending stops -> more defaults.

### Fallback Pattern

Every loan migration follows the same pattern:

```python
def _offer_emergency_loans(self):
    for firm in eligible_firms:
        if self.bank and self.bank.can_lend():
            self.bank.evaluate_emergency_loan(firm)
        else:
            self._government_emergency_loan(firm)
```

If the bank is `None`, depleted, or unable to fund a loan, the government handles it using pre-bank logic. The simulation never breaks due to bank state.

---

## 9. Observable Signals

The banking system produces the following metrics, all derivable from `BankAgent` state without additional tracking infrastructure:

| Metric | Description | Why It Matters |
|---|---|---|
| `bank_reserves` | Bank's available cash | Lending capacity |
| `bank_total_loans_outstanding` | Sum of all active loan balances | Credit in the economy |
| `bank_loans_issued_this_tick` | Count of new loans this tick | Credit growth rate |
| `bank_loans_issued_amount` | Dollar amount of new loans this tick | Credit flow |
| `bank_defaults_this_tick` | Count of loan defaults this tick | Credit stress |
| `bank_defaults_amount` | Dollar amount of defaults this tick | Loss severity |
| `bank_default_rate` | Defaults / total loans | Portfolio health |
| `bank_interest_collected` | Interest income this tick | Bank profitability |
| `bank_avg_credit_score` | Mean firm credit score | Economy creditworthiness |
| `bank_credit_utilization` | Outstanding / total capacity | Economy leverage |
| `bank_avg_debt_to_revenue` | Mean firm debt/revenue ratio | Corporate leverage |
| `bank_total_deposits` | Household deposits held | Bank funding base |
| `bank_base_interest_rate` | Current rate | Future lever readout |

These signals feed into the government's observation space. When the LLM government is integrated, it will see these alongside fiscal metrics, giving it visibility into the credit channel effects of its policy decisions.

---

## 10. Interest Rate as Future Lever

The `base_interest_rate` field on `BankAgent` is architecturally prepared as the 8th government policy lever but is **NOT wired in this phase**.

**Current state:** Fixed at 3% annual. Affects all new loan terms through `total_repayment = principal * (1 + rate * years)`. Government-subsidized loans use `rate * subsidy_factor`.

**Future integration:** When the LLM government is added, the lever maps directly:

| Option | Rate |
|---|---|
| very_low | 1% |
| low | 2% |
| neutral | 4% |
| high | 6% |
| restrictive | 10% |

**Observable downstream signals:** `credit_outstanding`, `loan_approval_rate`, `firm_debt_to_revenue`, `default_rate`, `bank_reserves`. Changing the value propagates to all new loan terms immediately. No additional plumbing required.

---

## 11. What's Deferred

| Feature | Status | Rationale |
|---|---|---|
| Household savings accounts | Implemented (simple) | Deposits earn interest, but spending does not auto-withdraw from deposits |
| General consumer credit | Deferred | Medical loans are the only household borrowing. No mortgages, credit cards, or personal loans. |
| Multiple interest rates | Deferred | One base rate for everything. Product-specific rates can be added later. |
| Firm viability/intangibles score | Deferred | Will be a composite score assigned at firm creation that affects bank lending decisions and product quality. Designed but not implemented. |
| Compound interest / amortization | Deferred | Simple interest is a deliberate simplification for v1. Documented so reviewers know it's intentional. |
| Interest rate as government lever | Plumbing ready, not wired | Waiting for LLM government integration phase. |

---

## 12. Known Open Issues

**Deposit pooling:** Bank deposits grew monotonically to ~$2M in testing while lending remained minimal ($58 total). The credit channel is available but dormant — money flows into the bank through deposits and barely recirculates as loans. This is expected to resolve naturally when the LLM government's policy decisions create economic conditions that push firms to borrow (recessions, demand shocks, tax changes). If it persists, the firm borrowing conditions in `should_request_loan()` may be too strict.

**Warmup unemployment:** During the 52-tick warmup phase, only baseline government firms exist. With 5 firms for 500 households, unemployment reaches 20%+ by tick 40. The bank correctly does not lend during warmup (government firms don't need credit). This is a baseline firm sizing issue, not a banking problem.
