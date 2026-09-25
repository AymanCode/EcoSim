"""Server-owned experiment records: which sessions are arms of one matched comparison.

Pure module: no FastAPI, no Economy. The registry enforces the household budget
across arms, one owner per experiment, and one shared world configuration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional

HOUSEHOLD_BUDGET = 10_000
MAX_ARMS = 4


class ExperimentError(ValueError):
    """A reservation request that the registry refuses."""


@dataclass
class ArmReservation:
    experiment_id: str
    arm_label: str
    session_id: str
    households: int


@dataclass
class ExperimentRecord:
    experiment_id: str
    arm_count: int
    owner: Optional[str]
    world_key: str
    created_at: float = field(default_factory=time.time)
    arms: Dict[str, ArmReservation] = field(default_factory=dict)  # keyed by arm_label

    @property
    def households_reserved(self) -> int:
        return sum(arm.households for arm in self.arms.values())


class ExperimentRegistry:
    def __init__(self, budget: int = HOUSEHOLD_BUDGET, max_arms: int = MAX_ARMS):
        self.budget = int(budget)
        self.max_arms = int(max_arms)
        self._experiments: Dict[str, ExperimentRecord] = {}
        self._by_session: Dict[str, ArmReservation] = {}

    def per_arm_cap(self, arm_count: int) -> int:
        return self.budget // max(1, int(arm_count))

    def reserve(
        self,
        *,
        experiment_id: str,
        arm_label: str,
        arm_count: int,
        households: int,
        session_id: str,
        owner: Optional[str],
        world_key: str,
    ) -> ArmReservation:
        experiment_id = str(experiment_id).strip()
        arm_label = str(arm_label).strip()
        if not experiment_id or not arm_label:
            raise ExperimentError("experiment_id and arm_label are required")
        if not 1 <= int(arm_count) <= self.max_arms:
            raise ExperimentError(f"arm_count must be between 1 and {self.max_arms} arms")
        cap = self.per_arm_cap(arm_count)
        if int(households) > cap:
            raise ExperimentError(f"{households} households exceeds the per-arm cap of {cap} for {arm_count} arms")
        # A session that reserves again replaces its earlier reservation.
        self.release(session_id)

        record = self._experiments.get(experiment_id)
        if record is None:
            record = ExperimentRecord(experiment_id=experiment_id, arm_count=int(arm_count), owner=owner, world_key=world_key)
        else:
            if record.arm_count != int(arm_count):
                raise ExperimentError(
                    f"experiment {experiment_id} was created with arm count {record.arm_count}, not {arm_count}"
                )
            if record.owner != owner:
                raise ExperimentError(f"experiment {experiment_id} belongs to another owner")
            if record.world_key != world_key:
                raise ExperimentError(f"experiment {experiment_id} uses a different world (seed, firms, payment rules)")
        if arm_label in record.arms:
            raise ExperimentError(f"arm label '{arm_label}' is already taken in experiment {experiment_id}")
        if len(record.arms) >= record.arm_count:
            raise ExperimentError(f"experiment {experiment_id} is full ({record.arm_count} arms)")
        if record.households_reserved + int(households) > self.budget:
            raise ExperimentError(f"experiment {experiment_id} would exceed the household budget of {self.budget}")

        reservation = ArmReservation(
            experiment_id=experiment_id, arm_label=arm_label, session_id=str(session_id), households=int(households)
        )
        record.arms[arm_label] = reservation
        self._experiments[experiment_id] = record
        self._by_session[str(session_id)] = reservation
        return reservation

    def release(self, session_id: str) -> None:
        reservation = self._by_session.pop(str(session_id), None)
        if reservation is None:
            return
        record = self._experiments.get(reservation.experiment_id)
        if record is None:
            return
        record.arms.pop(reservation.arm_label, None)
        if not record.arms:
            self._experiments.pop(reservation.experiment_id, None)

    def describe(self, experiment_id: str) -> Optional[dict]:
        record = self._experiments.get(str(experiment_id))
        if record is None:
            return None
        return {
            "experiment_id": record.experiment_id,
            "arm_count": record.arm_count,
            "owner": record.owner,
            "per_arm_cap": self.per_arm_cap(record.arm_count),
            "households_reserved": record.households_reserved,
            "arms": {label: arm.households for label, arm in record.arms.items()},
        }
