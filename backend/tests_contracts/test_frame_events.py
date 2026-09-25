from types import SimpleNamespace

from frame_events import ARCHIVE_WINDOW_TICKS, DETAIL_CAP, TickEventCollector


def _firm(firm_id, name, sector="Food", employees=3, cash=100.0):
    return SimpleNamespace(firm_id=firm_id, good_name=name, good_category=sector, employees=list(range(employees)), cash_balance=cash)


def _economy(firms, labor=(), care=(), regime=(), defaults=(), default_total=None):
    payment_state = {"loan_default_history": list(defaults)}
    if default_total is not None:
        payment_state["loan_default_history_total"] = default_total
    return SimpleNamespace(
        firms=list(firms),
        firm_lookup={f.firm_id: f for f in firms},
        last_labor_events=list(labor),
        last_healthcare_events=list(care),
        last_regime_events=list(regime),
        payment_state=payment_state,
    )


def _collect(collector, economy, tick, tracked=frozenset(), changes=()):
    return collector.collect(economy=economy, tick=tick, tracked_household_ids=set(tracked), policy_changes=list(changes))


def test_closure_is_reported_once_and_opening_comes_from_the_directory():
    collector = TickEventCollector()
    collector.reset(_economy([_firm(1, "Corner Bakery")]))
    clinic = _firm(2, "Riverside Clinic", "Healthcare")
    regime = [{"tick": 5, "event_type": "firm_bankrupt", "entity_type": "firm", "entity_id": 1, "sector": "Food",
               "reason_code": "cash_threshold"}]
    events, counts = _collect(collector, _economy([clinic], regime=regime), 5)
    assert {(e["type"], e["firmId"]) for e in events} == {("firm_closed", 1), ("firm_opened", 2)}
    closed = next(e for e in events if e["type"] == "firm_closed")
    assert closed["firmName"] == "Corner Bakery" and closed["text"] == "cash_threshold"
    assert counts["firmsClosed"] == 1 and counts["firmsOpened"] == 1
    assert collector.closed_archive(5) == [{"id": 1, "name": "Corner Bakery", "sector": "Food", "closedTick": 5, "lastStaff": 3}]
    # next tick: nothing new, no repeat
    events, counts = _collect(collector, _economy([clinic]), 6)
    assert events == [] and counts["firmsClosed"] == 0 and counts["firmsOpened"] == 0
    assert len(collector.closed_archive(6)) == 1
    assert collector.closed_archive(5 + ARCHIVE_WINDOW_TICKS + 1) == []
    assert collector.firm_name(1) == "Corner Bakery"  # names outlive the firm


def test_household_events_are_detailed_only_for_tracked_households_but_counted_for_all():
    collector = TickEventCollector()
    firm = _firm(1, "Corner Bakery")
    collector.reset(_economy([firm]))
    labor = [
        {"tick": 3, "household_id": 10, "firm_id": 1, "event_type": "hire", "actual_wage": 40.0},
        {"tick": 3, "household_id": 11, "firm_id": 1, "event_type": "layoff", "actual_wage": None},
        {"tick": 3, "household_id": 12, "firm_id": 1, "event_type": "hire", "actual_wage": 42.0},
    ]
    care = [{"tick": 3, "household_id": 10, "firm_id": 1, "event_type": "visit_denied_affordability", "visit_price": 9.0}]
    defaults = [{"tick": 2, "claim_id": "c1", "borrower_type": "household", "borrower_id": 12, "written_off": 50.0}]
    events, counts = _collect(collector, _economy([firm], labor=labor, care=care, defaults=defaults), 3, tracked={10, 11})
    assert {(e["type"], e["householdId"]) for e in events} == {("hired", 10), ("laid_off", 11), ("care_denied", 10)}
    assert counts["hired"] == 2 and counts["laidOff"] == 1 and counts["careDenied"] == 1 and counts["loanDefaults"] == 1
    assert counts["detailed"] == 3 and counts["dropped"] == 0
    hired = next(e for e in events if e["type"] == "hired")
    assert hired["firmName"] == "Corner Bakery" and hired["value"] == 40.0


def test_laid_off_keeps_firm_name_when_the_firm_closed_this_tick():
    collector = TickEventCollector()
    collector.reset(_economy([_firm(1, "Corner Bakery")]))
    labor = [{"tick": 4, "household_id": 10, "firm_id": 1, "event_type": "layoff"}]
    regime = [{"tick": 4, "event_type": "firm_bankrupt", "entity_type": "firm", "entity_id": 1, "sector": "Food"}]
    events, _ = _collect(collector, _economy([], labor=labor, regime=regime), 4, tracked={10})
    assert next(e for e in events if e["type"] == "laid_off")["firmName"] == "Corner Bakery"


def test_policy_changes_and_defaults_are_emitted_once_regardless_of_their_recorded_tick():
    collector = TickEventCollector()
    collector.reset(_economy([]))
    # server records human changes with the pre-increment tick and payment defaults with the zero-based tick,
    # so the collector must key on identity, not tick equality
    changes = [{"tick": 5, "policy": "benefit_level", "value": "high", "reason": "User", "actionId": "abc"},
               {"tick": 5, "policy": "wage_tax_rate", "value": 0.2, "reason": "User", "actionId": "abc"}]
    defaults = [{"tick": 5, "claim_id": "c1", "borrower_type": "firm", "borrower_id": 3, "written_off": 500.0}]
    events, counts = _collect(collector, _economy([], defaults=defaults), 6, changes=changes)
    assert [e["type"] for e in events] == ["policy_changed", "policy_changed", "loan_default"]
    assert {e["id"] for e in events} == {"6:policy_changed:abc:benefit_level:0", "6:policy_changed:abc:wage_tax_rate:1",
                                         "6:loan_default:c1"}
    assert events[0]["text"] == "benefit_level=high" and events[2]["value"] == 500.0
    assert counts["policyChanges"] == 2 and counts["loanDefaults"] == 1
    events, counts = _collect(collector, _economy([], defaults=defaults), 7, changes=changes)
    assert events == [] and counts["policyChanges"] == 0 and counts["loanDefaults"] == 0


def test_two_records_for_one_lever_in_one_tick_get_distinct_ids():
    collector = TickEventCollector()
    collector.reset(_economy([]))
    changes = [{"tick": 5, "policy": "benefit_level", "value": "high", "reason": "auto", "actionId": None},
               {"tick": 5, "policy": "benefit_level", "value": "crisis", "reason": "auto", "actionId": None}]
    events, counts = _collect(collector, _economy([]), 6, changes=changes)
    ids = [e["id"] for e in events if e["type"] == "policy_changed"]
    assert ids == ["6:policy_changed:auto:benefit_level:0", "6:policy_changed:auto:benefit_level:1"]
    assert counts["policyChanges"] == 2


def test_shock_and_other_regime_events_are_mapped():
    collector = TickEventCollector()
    collector.reset(_economy([]))
    regime = [{"tick": 9, "event_type": "shock_demand", "entity_type": "economy", "metric_value": 42.0, "payload": {"affected": 7}},
              {"tick": 9, "event_type": "sector_shortage_start", "entity_type": "sector", "sector": "Food", "severity": 0.3}]
    events, counts = _collect(collector, _economy([], regime=regime), 9)
    assert [(e["type"], e["text"]) for e in events] == [("shock", "shock_demand"), ("regime", "sector_shortage_start")]
    assert events[0]["value"] == 42.0 and events[1]["sector"] == "Food"
    assert counts["shocks"] == 1 and counts["regime"] == 1


def test_detail_cap_keeps_structural_events_first():
    collector = TickEventCollector()
    collector.reset(_economy([_firm(1, "Corner Bakery")]))
    labor = [{"tick": 1, "household_id": i, "firm_id": 1, "event_type": "hire"} for i in range(DETAIL_CAP + 10)]
    regime = [{"tick": 1, "event_type": "firm_bankrupt", "entity_type": "firm", "entity_id": 1, "sector": "Food"}]
    events, counts = _collect(collector, _economy([], labor=labor, regime=regime), 1, tracked=set(range(DETAIL_CAP + 10)))
    assert len(events) == DETAIL_CAP and events[0]["type"] == "firm_closed"
    assert counts["hired"] == DETAIL_CAP + 10 and counts["dropped"] == 11


def test_every_policy_change_in_a_tick_is_emitted():
    collector = TickEventCollector()
    collector.reset(_economy([]))
    levers = ["benefit_level", "wage_tax_rate", "profit_tax_rate", "ubi", "wealth_tax_rate", "birth_rate"]
    changes = [{"tick": 2, "policy": lever, "value": 0.1, "reason": "User", "actionId": "abc"} for lever in levers]
    events, counts = _collect(collector, _economy([]), 3, changes=changes)
    assert [e["text"] for e in events] == [f"{lever}=0.1" for lever in levers]
    assert counts["policyChanges"] == 6


def test_loan_default_count_follows_the_producer_total_not_the_retained_claims():
    collector = TickEventCollector()
    collector.reset(_economy([], default_total=0))
    # the producer's deque dropped two claims before we saw them; its running total still counts them
    defaults = [{"tick": 4, "claim_id": "c9", "borrower_type": "firm", "borrower_id": 3, "written_off": 20.0}]
    events, counts = _collect(collector, _economy([], defaults=defaults, default_total=3), 5)
    assert counts["loanDefaults"] == 3
    assert [e["id"] for e in events] == ["5:loan_default:c9"]
    events, counts = _collect(collector, _economy([], defaults=defaults, default_total=3), 6)
    assert events == [] and counts["loanDefaults"] == 0


def test_reset_treats_existing_claims_as_already_reported():
    collector = TickEventCollector()
    old = [{"tick": 1, "claim_id": "c1", "borrower_type": "firm", "borrower_id": 3, "written_off": 5.0}]
    collector.reset(_economy([], defaults=old, default_total=1))
    events, counts = _collect(collector, _economy([], defaults=old, default_total=1), 1)
    assert events == [] and counts["loanDefaults"] == 0


def test_claim_memory_is_bounded():
    collector = TickEventCollector()
    collector.reset(_economy([]))
    defaults = [{"tick": 1, "claim_id": f"c{i}", "borrower_type": "bank", "borrower_id": None} for i in range(5000)]
    _, counts = _collect(collector, _economy([], defaults=defaults), 1)
    assert counts["loanDefaults"] == 5000
    assert len(collector._seen_claims) == 4096 and "c0" not in collector._seen_claims and "c4999" in collector._seen_claims


def test_archive_drops_rows_from_after_the_current_tick():
    collector = TickEventCollector()
    collector.reset(_economy([_firm(1, "Corner Bakery")]))
    _collect(collector, _economy([]), 100)
    assert len(collector.closed_archive(100)) == 1
    assert collector.closed_archive(1) == []  # a legacy RESET zeroed the tick


def test_household_regime_events_are_household_level_and_firm_ones_keep_the_firm():
    collector = TickEventCollector()
    firm = _firm(1, "Corner Bakery")
    collector.reset(_economy([firm]))
    evictions = [{"tick": 2, "event_type": "eviction", "entity_type": "household", "entity_id": 100 + i,
                  "sector": "Housing", "severity": 1.0} for i in range(50)]
    failed = {"tick": 2, "event_type": "failed_hiring", "entity_type": "firm", "entity_id": 1, "sector": "Food"}
    labor = [{"tick": 2, "household_id": 7, "firm_id": 1, "event_type": "hire", "actual_wage": 40.0}]
    events, counts = _collect(collector, _economy([firm], labor=labor, regime=evictions + [failed]), 2, tracked={7})
    assert counts["regime"] == 51
    assert [(e["type"], e["text"]) for e in events] == [("regime", "failed_hiring"), ("hired", None)]
    assert events[0]["firmId"] == 1 and events[0]["firmName"] == "Corner Bakery"
    assert not [e for e in events if e["type"] == "regime" and e["firmId"] is None and e["householdId"] is None]

    tracked_eviction = [{"tick": 3, "event_type": "eviction", "entity_type": "household", "entity_id": 7,
                         "sector": "Housing", "severity": 1.0}]
    events, counts = _collect(collector, _economy([firm], regime=tracked_eviction), 3, tracked={7})
    assert [(e["type"], e["householdId"], e["text"]) for e in events] == [("regime", 7, "eviction")]
    assert counts["regime"] == 1
