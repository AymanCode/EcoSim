from collections import Counter

from run_bank_simulation import create_economy


NON_MARKET_CATEGORIES = {"Housing", "Healthcare", "PublicWorks"}


def _correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0.0 or var_y <= 0.0:
        return 0.0
    return cov / ((var_x * var_y) ** 0.5)


def test_tier1_validation_checkpoint():
    economy = create_economy(num_households=120, enable_bank=True)
    economy._apply_random_shocks = lambda: None

    money_drift_history: list[float] = []
    money_unexplained_history: list[float] = []
    bank_can_lend_ticks = 0
    negative_household_cash_events = 0
    reservation_floor_violations = 0
    max_firm_missed_payments = 0
    zero_revenue_tier1_loans = 0
    price_floor_violations = Counter()

    firm_histories: dict[int, dict[str, object]] = {}
    private_quality_by_firm: dict[int, float] = {}
    private_revenue_by_firm: dict[int, float] = {}
    private_revenue_by_category: dict[str, dict[int, float]] = {}

    for _ in range(104):
        economy.step()
        money_drift_history.append(float(economy.last_tick_money_drift))
        money_unexplained_history.append(float(economy.last_tick_money_unexplained_flow))
        negative_household_cash_events += sum(1 for hh in economy.households if hh.cash_balance < -1e-6)
        reservation_floor_violations += sum(1 for hh in economy.households if hh.reservation_wage < 1.0 - 1e-9)

        if economy.bank is not None and economy.bank.can_lend():
            bank_can_lend_ticks += 1

        if economy.bank is not None:
            for loan in economy.bank.active_loans:
                if loan["borrower_type"] == "firm":
                    max_firm_missed_payments = max(max_firm_missed_payments, int(loan.get("missed_payments", 0)))
                    if not loan["govt_backed"]:
                        borrower = economy.firm_lookup.get(loan["borrower_id"])
                        if borrower is not None and borrower.trailing_revenue_12t <= 0.0:
                            zero_revenue_tier1_loans += 1

        for firm in economy.firms:
            firm_histories.setdefault(
                firm.firm_id,
                {
                    "name": firm.good_name,
                    "category": firm.good_category,
                    "is_baseline": bool(firm.is_baseline),
                    "revenue": [],
                    "wage": [],
                },
            )
            firm_histories[firm.firm_id]["revenue"].append(float(firm.last_revenue))
            avg_actual_wage = (
                sum(firm.actual_wages.values()) / len(firm.actual_wages)
                if firm.actual_wages
                else firm.wage_offer
            )
            firm_histories[firm.firm_id]["wage"].append(float(avg_actual_wage))

            if economy.current_tick <= 52:
                continue

            if firm.good_category not in NON_MARKET_CATEGORIES:
                if firm.unit_cost > 0.0 and firm.price + 1e-6 < firm.unit_cost * 1.05:
                    price_floor_violations[firm.good_category] += 1

            if firm.good_category in NON_MARKET_CATEGORIES or firm.is_baseline:
                continue

            private_quality_by_firm[firm.firm_id] = float(firm.quality_level)
            private_revenue_by_firm[firm.firm_id] = private_revenue_by_firm.get(firm.firm_id, 0.0) + float(firm.last_revenue)
            private_revenue_by_category.setdefault(firm.good_category, {})
            private_revenue_by_category[firm.good_category][firm.firm_id] = (
                private_revenue_by_category[firm.good_category].get(firm.firm_id, 0.0) + float(firm.last_revenue)
            )

    declining_revenue_wage_violations = []
    rising_revenue_wage_violations = []
    for firm_id, history in firm_histories.items():
        category = str(history["category"])
        if category in NON_MARKET_CATEGORIES or bool(history["is_baseline"]):
            continue

        revenues = history["revenue"][52:]
        wages = history["wage"][52:]
        for start in range(len(revenues) - 9):
            revenue_window = revenues[start:start + 10]
            wage_window = wages[start:start + 10]
            if max(revenue_window) - min(revenue_window) < 25.0:
                continue

            if (
                all(revenue_window[idx + 1] <= revenue_window[idx] + 1e-9 for idx in range(9))
                and any(revenue_window[idx + 1] < revenue_window[idx] - 1e-9 for idx in range(9))
                and any(wage_window[idx + 1] > wage_window[idx] + 1e-9 for idx in range(9))
            ):
                declining_revenue_wage_violations.append((firm_id, history["name"], start + 53))

            if (
                all(revenue_window[idx + 1] >= revenue_window[idx] - 1e-9 for idx in range(9))
                and any(revenue_window[idx + 1] > revenue_window[idx] + 1e-9 for idx in range(9))
                and any(wage_window[idx + 1] < wage_window[idx] - 1e-9 for idx in range(9))
            ):
                rising_revenue_wage_violations.append((firm_id, history["name"], start + 53))

    quality_scores = [private_quality_by_firm[firm_id] for firm_id in sorted(private_quality_by_firm)]
    revenue_scores = [private_revenue_by_firm[firm_id] for firm_id in sorted(private_quality_by_firm)]
    quality_revenue_corr = _correlation(quality_scores, revenue_scores)

    category_top_shares = {}
    for category, revenue_map in private_revenue_by_category.items():
        total_revenue = sum(revenue_map.values())
        if total_revenue <= 0.0:
            continue
        category_top_shares[category] = max(revenue_map.values()) / total_revenue

    assert abs(money_drift_history[-1]) < 100.0
    assert max(abs(value) for value in money_drift_history) < 100.0
    assert max(abs(value) for value in money_unexplained_history) < 1.0
    assert negative_household_cash_events == 0
    assert reservation_floor_violations == 0
    assert bank_can_lend_ticks / 104.0 >= 0.80
    assert max_firm_missed_payments <= 12
    assert zero_revenue_tier1_loans == 0
    assert not price_floor_violations
    assert not declining_revenue_wage_violations
    assert not rising_revenue_wage_violations
    assert quality_revenue_corr > 0.0
    assert all(share <= 0.601 for share in category_top_shares.values())
