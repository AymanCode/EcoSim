"""Typed per-tick events for the frontend feed, plus the firm directory and closed-firm archive.

Pure module: takes an Economy-like object and returns plain dicts. Bankrupt firms
leave economy.firms before we see them, so the collector keeps its own directory
of names from earlier ticks and the set of firms active on the previous tick.
Every event is emitted once: policy records and default claims are remembered
by identity, because their producers stamp ticks differently from the frame.
Default counts follow the producer's running total, because its claim history
keeps only the latest claims.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, Iterable, List, Optional, Set, Tuple

DETAIL_CAP = 50
ARCHIVE_WINDOW_TICKS = 52
CLAIM_MEMORY = 4096

_STRUCTURAL_PRIORITY = ("firm_closed", "firm_opened", "policy_changed", "loan_default", "shock", "regime")
_COUNT_KEYS = ("hired", "laidOff", "careDenied", "careCompleted", "firmsOpened", "firmsClosed",
               "loanDefaults", "policyChanges", "shocks", "regime", "detailed", "dropped")


def _event(tick: int, kind: str, key: Any, **fields: Any) -> Dict[str, Any]:
    base = {"id": f"{tick}:{kind}:{key}", "tick": int(tick), "type": kind, "householdId": None,
            "firmId": None, "firmName": None, "sector": None, "value": None, "text": None}
    base.update(fields)
    return base


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class TickEventCollector:
    def __init__(self) -> None:
        self._directory: Dict[int, Dict[str, Any]] = {}   # every firm ever seen: name, sector, last staff
        self._active_ids: Set[int] = set()                 # firms present on the previous tick
        self._closed: List[Dict[str, Any]] = []
        self._seen_policy: Deque[Tuple[Any, ...]] = deque(maxlen=64)
        self._seen_claims: Set[Any] = set()                # membership; _claim_order bounds it
        self._claim_order: Deque[Any] = deque()
        self._default_total = 0                            # producer's running default count last tick

    # directory -----------------------------------------------------------
    def reset(self, economy: Any) -> None:
        self._directory = {}
        self._active_ids = set()
        self._closed = []
        self._seen_policy.clear()
        self._seen_claims = set()
        self._claim_order = deque()
        self._refresh_directory(economy)
        self._active_ids = {int(f.firm_id) for f in (getattr(economy, "firms", []) or [])}
        # Defaults that happened before this point are not news.
        history, total = self._default_source(economy)
        for row in history:
            self._remember_claim(row.get("claim_id"))
        self._default_total = total if total is not None else 0

    @staticmethod
    def _default_source(economy: Any) -> Tuple[Iterable[Dict[str, Any]], Optional[int]]:
        state = getattr(economy, "payment_state", {}) or {}
        total = state.get("loan_default_history_total")
        return state.get("loan_default_history", ()) or (), int(total) if total is not None else None

    def _remember_claim(self, claim_id: Any) -> None:
        self._seen_claims.add(claim_id)
        self._claim_order.append(claim_id)
        if len(self._claim_order) > CLAIM_MEMORY:
            self._seen_claims.discard(self._claim_order.popleft())

    def _refresh_directory(self, economy: Any) -> None:
        for firm in getattr(economy, "firms", []) or []:
            self._directory[int(firm.firm_id)] = {
                "name": str(firm.good_name),
                "sector": str(firm.good_category or ""),
                "staff": len(getattr(firm, "employees", []) or []),
            }

    def firm_name(self, firm_id: Optional[int]) -> Optional[str]:
        if firm_id is None:
            return None
        entry = self._directory.get(int(firm_id))
        return entry["name"] if entry else None

    def closed_archive(self, current_tick: int) -> List[Dict[str, Any]]:
        # Rows from after current_tick come from before a legacy RESET zeroed the tick.
        self._closed = [row for row in self._closed
                        if 0 <= current_tick - row["closedTick"] <= ARCHIVE_WINDOW_TICKS]
        return [dict(row) for row in self._closed]

    # collection ----------------------------------------------------------
    def collect(
        self,
        *,
        economy: Any,
        tick: int,
        tracked_household_ids: Set[int],
        policy_changes: Iterable[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        counts = {key: 0 for key in _COUNT_KEYS}
        structural: List[Dict[str, Any]] = []
        household: List[Dict[str, Any]] = []

        current_ids = {int(f.firm_id) for f in (getattr(economy, "firms", []) or [])}
        reasons: Dict[int, Optional[str]] = {}
        other_regime: List[Dict[str, Any]] = []
        for event in getattr(economy, "last_regime_events", []) or []:
            etype = str(event.get("event_type", ""))
            if etype == "firm_bankrupt" and event.get("entity_id") is not None:
                reasons[int(event["entity_id"])] = event.get("reason_code")
            else:
                other_regime.append(event)

        for firm_id in sorted(self._active_ids - current_ids):
            entry = self._directory.get(firm_id, {"name": f"Firm {firm_id}", "sector": "", "staff": 0})
            counts["firmsClosed"] += 1
            self._closed.append({"id": firm_id, "name": entry["name"], "sector": entry["sector"],
                                 "closedTick": int(tick), "lastStaff": entry["staff"]})
            structural.append(_event(tick, "firm_closed", firm_id, firmId=firm_id, firmName=entry["name"],
                                     sector=entry["sector"], text=reasons.get(firm_id)))
        self._refresh_directory(economy)
        for firm_id in sorted(current_ids - self._active_ids):
            entry = self._directory[firm_id]
            counts["firmsOpened"] += 1
            structural.append(_event(tick, "firm_opened", firm_id, firmId=firm_id, firmName=entry["name"],
                                     sector=entry["sector"], value=float(entry["staff"])))
        self._active_ids = current_ids

        for change in policy_changes or []:
            key = (change.get("tick"), change.get("policy"), change.get("actionId"), repr(change.get("value")))
            if key in self._seen_policy:
                continue
            self._seen_policy.append(key)
            counts["policyChanges"] += 1
            ident = f"{change.get('actionId') or 'auto'}:{change.get('policy')}"
            value = change.get("value")
            structural.append(_event(tick, "policy_changed", ident, text=f"{change.get('policy')}={value}",
                                     value=float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None))

        history, default_total = self._default_source(economy)
        new_claims = 0
        for row in history:
            claim_id = row.get("claim_id")
            if claim_id in self._seen_claims:
                continue
            self._remember_claim(claim_id)
            new_claims += 1
            borrower_type = row.get("borrower_type")
            borrower_id = row.get("borrower_id")
            event = _event(tick, "loan_default", claim_id, value=_num(row.get("written_off")))
            if borrower_type == "firm" and borrower_id is not None:
                event.update(firmId=int(borrower_id), firmName=self.firm_name(borrower_id))
                structural.append(event)
            elif borrower_type == "household" and borrower_id is not None:
                event["householdId"] = int(borrower_id)
                if int(borrower_id) in tracked_household_ids:
                    household.append(event)
            else:
                structural.append(event)
        if default_total is not None:
            counts["loanDefaults"] = max(0, default_total - self._default_total)
            self._default_total = default_total
        else:
            counts["loanDefaults"] = new_claims

        for index, event in enumerate(other_regime):
            etype = str(event.get("event_type", ""))
            kind = "shock" if etype.startswith("shock_") else "regime"
            counts["shocks" if kind == "shock" else "regime"] += 1
            metric = event.get("metric_value")
            item = _event(tick, kind, f"{etype}:{index}", sector=event.get("sector"), text=etype,
                          value=_num(metric if metric is not None else event.get("severity")))
            entity_type = event.get("entity_type")
            entity_id = event.get("entity_id")
            if kind == "regime" and entity_type == "household" and entity_id is not None:
                item["householdId"] = int(entity_id)
                if int(entity_id) in tracked_household_ids:
                    household.append(item)
                continue
            if kind == "regime" and entity_type == "firm" and entity_id is not None:
                item.update(firmId=int(entity_id), firmName=self.firm_name(entity_id))
            structural.append(item)

        for index, event in enumerate(getattr(economy, "last_labor_events", []) or []):
            kind = "hired" if event.get("event_type") == "hire" else "laid_off"
            counts["hired" if kind == "hired" else "laidOff"] += 1
            hid = int(event["household_id"])
            if hid in tracked_household_ids:
                fid = int(event["firm_id"])
                household.append(_event(tick, kind, f"{hid}:{index}", householdId=hid, firmId=fid,
                                        firmName=self.firm_name(fid), value=_num(event.get("actual_wage"))))

        for index, event in enumerate(getattr(economy, "last_healthcare_events", []) or []):
            etype = str(event.get("event_type", ""))
            if etype.startswith("visit_denied"):
                kind = "care_denied"
                counts["careDenied"] += 1
            elif etype == "visit_completed":
                kind = "care_completed"
                counts["careCompleted"] += 1
            else:
                continue
            hid = int(event["household_id"])
            if hid in tracked_household_ids:
                fid = int(event["firm_id"])
                household.append(_event(tick, kind, f"{hid}:{index}", householdId=hid, firmId=fid,
                                        firmName=self.firm_name(fid), value=_num(event.get("visit_price")), text=etype))

        structural.sort(key=lambda e: _STRUCTURAL_PRIORITY.index(e["type"]))
        ordered = structural + household
        detailed = ordered[:DETAIL_CAP]
        counts["detailed"] = len(detailed)
        counts["dropped"] = len(ordered) - len(detailed)
        return detailed, counts
