"""Check food-only settlement and weekly balances with two matched seeds."""
import contextlib
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def check_run(seed, enabled):
    from config import clone_config, use_config
    from payments import PaymentBook
    from server import SetupConfig
    from sim_setup import build_economy_from_setup
    from tools.benchmarks.panel_money import total_money_net_of_injections

    def equal(actual, expected):
        if not math.isclose(actual, expected, abs_tol=1e-6, rel_tol=0):
            raise AssertionError((seed, enabled, week, actual, expected))

    setup = SetupConfig(num_households=1000, seed=seed, payment_sequence="income_first",
                        initial_policy={"wage_tax_rate": 0.20}, enable_llm_government=False,
                        payment_food_credit_enabled=enabled, horizon_ticks=312)
    original_sale = PaymentBook.commit_sale
    purchases = 0
    card_sales = 0

    def observe_sale(book, household, firm, qty, price, **funding):
        nonlocal purchases, card_sales
        hid = household.household_id
        balances = economy.payment_state.get("food_credit", {})
        before = balances.get(hid, 0.0)
        cash = household.cash_balance
        accepted = original_sale(book, household, firm, qty, price, **funding)
        private = qty * price - funding.get("public_amount", 0) - funding.get("bank_amount", 0)
        eligible = funding.get("kind", "goods") == "goods" and firm.good_category.lower() == "food"
        tender = min(before, max(0.0, private)) if eligible and accepted else 0.0
        equal(before - balances.get(hid, 0.0), tender)
        equal(cash - household.cash_balance, max(0.0, private - tender) if accepted else 0.0)
        purchases += int(accepted)
        card_sales += int(tender > 0)
        return accepted

    total_issued = total_redeemed = balance = peak_balance = max_drift = 0.0
    with use_config(clone_config()), open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
        economy, _ = build_economy_from_setup(setup, seed)
        stock = total_money_net_of_injections(economy)
        with patch.object(PaymentBook, "commit_sale", observe_sale):
            for week in range(1, 313):
                economy.step()
                book = economy.payment_book
                wallets = economy.payment_state.get("food_credit", {})
                assert all(v >= 0 for v in wallets.values())
                assert len(set(book.food_credit_recipients)) == (200 if enabled else 0)
                assert 0 <= book.food_credit_issued <= (500 if enabled else 0)
                assert economy.government.wage_tax_rate == 0.20
                close = sum(wallets.values())
                equal(close, balance + book.food_credit_issued - book.food_credit_redeemed)
                balance = close
                peak_balance = max(peak_balance, close)
                total_issued += book.food_credit_issued
                total_redeemed += book.food_credit_redeemed
                max_drift = max(max_drift, abs(total_money_net_of_injections(economy) - stock))
        assert (card_sales > 0) == enabled
        assert max_drift < 0.0001, (seed, enabled, max_drift)
    return dict(seed=seed, enabled=enabled, weeks=312, households=1000, sales=purchases,
                food_credit_sales=card_sales, issued=total_issued, redeemed=total_redeemed,
                closing_balance=balance, peak_weekly_closing_balance=peak_balance,
                max_unexplained_money_drift=max_drift)


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    # The worker starts with the fixed hash seed. Run only one town at a time.
    with ProcessPoolExecutor(max_workers=1) as pool:
        results = list(pool.map(check_run, (42, 42, 43, 43), (False, True, False, True)))
    print(json.dumps(results, indent=2))
