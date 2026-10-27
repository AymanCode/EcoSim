"""Bounded Food/Services research projects and entry-quality distributions."""

import math
import random
from dataclasses import asdict, dataclass, field
from typing import Literal, Optional, Sequence

import numpy as np


ResearchVariant = Literal["project_outcome", "project_cost"]
PROJECT_MODELS = frozenset({"project_outcome", "project_cost"})
QUALITY_MODELS = frozenset({"instant", "scale_only", *PROJECT_MODELS})
RESEARCH_CATEGORIES = frozenset({"food", "services"})


def _finite(value: float, name: str, *, nonnegative: bool = False) -> None:
    if not math.isfinite(value) or (nonnegative and value < 0.0):
        raise ValueError(f"{name} must be finite" + (" and nonnegative" if nonnegative else ""))


def _quality(value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 10.0:
        raise ValueError("quality must be finite and in [0, 10]")


def _rng(seed: int, identity: str, purpose: str, sequence: int = 0) -> random.Random:
    return random.Random(f"firm-research-v1|{seed}|{identity}|{purpose}|{sequence}")


def _founder_bias(founder_skill: Optional[float]) -> float:
    if founder_skill is not None:
        _finite(founder_skill, "founder skill")
    return 0.0 if founder_skill is None else max(-1.0, min(1.0, (founder_skill - 0.5) / 0.4))


def sample_initial_quality(*, seed: int, identity: str, founder_skill: Optional[float] = None) -> float:
    z = _founder_bias(founder_skill)
    rng = _rng(seed, identity, "initial-quality")
    if rng.random() < 0.01:
        return max(math.nextafter(1.11, math.inf),
                   min(math.nextafter(4.99, 0.0), 1.11 + 3.88 * rng.betavariate(1.0, 4.0)))
    return 0.11 + rng.betavariate(2.0 + 0.6 * max(z, 0.0), 2.0 + 0.6 * max(-z, 0.0))


def sample_entry_quality(
    *, seed: int, identity: str, peer_qualities: Sequence[float], founder_skill: Optional[float] = None,
) -> float:
    z = _founder_bias(founder_skill)
    for quality in peer_qualities:
        _quality(quality)
    if not peer_qualities:
        return sample_initial_quality(seed=seed, identity=identity, founder_skill=founder_skill)
    middle = float(np.median(peer_qualities))
    upside = 0.5 * (1.0 - middle / 10.0)
    deviation = 2.0 * _rng(seed, identity, "entry-quality").betavariate(
        3.0 + 0.6 * max(z, 0.0), 3.0 + 0.6 * max(-z, 0.0),
    ) - 1.0
    draw = middle + deviation * (upside if deviation > 0.0 else 0.5)
    return max(0.11, min(middle + upside, max(peer_qualities), draw))


@dataclass(frozen=True, slots=True)
class ResearchBudget:
    generation: float
    cash: float
    available_cash: float
    operating_costs: float
    debt_reserve: float
    risk_tolerance: float

    def __post_init__(self) -> None:
        for name in ("generation", "cash", "available_cash", "risk_tolerance"):
            _finite(getattr(self, name), name)
        for name in ("operating_costs", "debt_reserve"):
            _finite(getattr(self, name), name, nonnegative=True)
        _finite(self.reserve, "research reserve", nonnegative=True)

    @property
    def reserve(self) -> float:
        return 6.0 * self.operating_costs + self.debt_reserve

    def allowance(self, cash_ema: float) -> float:
        share = 0.15 + 0.25 * max(0.0, min(1.0, self.risk_tolerance))
        headroom = max(0.0, min(self.cash, self.available_cash) - self.reserve)
        return min(share * max(0.0, cash_ema), headroom)


@dataclass(slots=True)
class ResearchProject:
    variant: ResearchVariant
    sequence: int
    started_tick: int
    start_quality: float
    required_ticks: int
    installment: float
    funded_ticks: int = 0
    spent: float = 0.0
    status: Literal["active", "paused"] = "active"

    @classmethod
    def quote(cls, variant: ResearchVariant, quality: float, tick: int, sequence: int) -> "ResearchProject":
        _quality(quality)
        if variant not in PROJECT_MODELS:
            raise ValueError("unsupported research project variant")
        duration = 40 if variant == "project_outcome" else int(round(36.0 + 2.0 * quality))
        cost = 1200.0 if variant == "project_outcome" else 1200.0 * math.exp(0.25 * quality)
        return cls(variant, sequence, tick, quality, duration, cost / duration)

    def outcome(self, *, seed: int, identity: str) -> tuple[float, bool]:
        rng = _rng(seed, identity, "outcome", self.sequence)
        roll = rng.random()
        difficulty = max(0.0, 1.0 - self.start_quality / 10.0)
        if self.variant == "project_outcome":
            if roll < 0.15:
                return 0.0, True
            return 0.35 * difficulty ** 1.5 * min(3.0, math.exp(rng.gauss(0.0, 0.5))), False
        if roll < 0.10:
            return 0.0, True
        return 0.25 * difficulty * (2.5 if roll >= 0.95 else 1.0), False


@dataclass(frozen=True, slots=True)
class ResearchResult:
    spending: float = 0.0
    gain: float = 0.0
    completed: bool = False
    failed: bool = False


@dataclass(slots=True)
class ResearchState:
    seed: int
    identity: str
    project: Optional[ResearchProject] = None
    sequence: int = 0
    cash_ema: float = 0.0
    last_tick: int = -1
    completed: int = 0
    failed: int = 0
    paused_ticks: int = 0
    last_spend: float = 0.0
    last_gain: float = 0.0
    gains: list[tuple[int, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def advance(
        self, *, tick: int, quality: float, variant: ResearchVariant, budget: ResearchBudget, blocked: bool,
    ) -> ResearchResult:
        _quality(quality)
        if not isinstance(tick, int) or tick < 0:
            raise ValueError("research tick must be a nonnegative integer")
        if variant not in PROJECT_MODELS:
            raise ValueError("unsupported research project variant")
        if tick <= self.last_tick:
            return ResearchResult()
        # Weighted terms avoid overflow from subtracting large opposite-signed inputs.
        cash_ema = (6.0 / 7.0) * self.cash_ema + (1.0 / 7.0) * budget.generation
        _finite(cash_ema, "research cash EMA")
        allowance = budget.allowance(cash_ema)
        self.cash_ema = cash_ema
        self.last_tick = tick
        self.last_spend = self.last_gain = 0.0
        self.gains = [(at, gain) for at, gain in self.gains if at > tick - 52]
        if self.project is None and quality < 10.0 and not blocked:
            candidate = ResearchProject.quote(variant, quality, tick, self.sequence + 1)
            if allowance >= candidate.installment:
                self.sequence += 1
                self.project = candidate
        project = self.project
        if project is None:
            return ResearchResult()
        if blocked or allowance < project.installment:
            project.status = "paused"
            self.paused_ticks += 1
            return ResearchResult()
        project.status = "active"
        project.funded_ticks += 1
        project.spent += project.installment
        self.last_spend = project.installment
        if project.funded_ticks < project.required_ticks:
            return ResearchResult(spending=project.installment)
        raw_gain, failed = project.outcome(seed=self.seed, identity=self.identity)
        gain = max(0.0, min(raw_gain, 1.0 - sum(g for _, g in self.gains), 10.0 - quality))
        self.gains.append((tick, gain))
        self.last_gain = gain
        self.completed += 1
        self.failed += int(failed)
        self.project = None
        return ResearchResult(project.installment, gain, True, failed)
