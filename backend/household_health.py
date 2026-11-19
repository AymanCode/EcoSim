"""Scalar weekly health steps shared by the simulation and validation."""


def health_recovery_step(h: float, F: float, r: float) -> float:
    """Rising branch, bounded by the old health and the recovery target."""
    return min(F, max(h, (1.0 - r) * h + r * F))


def health_condition_step(h: float, Bd: float, r: float) -> float:
    """Falling branch, bounded by the condition target and the old health."""
    return max(Bd, min(h, (1.0 - r) * h + r * Bd))
