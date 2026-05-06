"""Utility for inferring good categories from good names.

This module consolidates the previously duplicated logic from:
- ``agents._get_good_category``
- ``server._infer_sector_from_good``
- ``economy._build_good_category_lookup``
"""

from typing import Dict, Optional


def get_good_category(good_name: str, good_categories: Optional[Dict[str, str]] = None) -> str:
    """Infer the category of a good from its name.

    Parameters
    ----------
    good_name:
        The name of the good (e.g., "BasicFood", "HealthcareService").
    good_categories:
        Optional pre-built lookup dict (good_name -> category).  When
        provided, values are assumed to already be lowercased.

    Returns
    -------
    str
        Lowercased category name (e.g., "housing", "food", "healthcare",
        "services").
    """
    if good_categories:
        cat = good_categories.get(good_name)
        if cat:
            return cat  # already lowercased by _build_good_category_lookup

    # Fallback for callers without a lookup
    lowered = good_name.lower()
    if "housing" in lowered:
        return "housing"
    if "service" in lowered:
        return "services"
    if "health" in lowered or "medical" in lowered:
        return "healthcare"
    return "food"


def build_good_category_lookup(firms) -> Dict[str, str]:
    """Build a lookup dict mapping good_name to lowercased category.

    Parameters
    ----------
    firms:
        Iterable of ``FirmAgent`` instances, each having ``good_name``
        and ``good_category`` attributes.

    Returns
    -------
    Dict[str, str]
        Mapping ``{firm.good_name: firm.good_category.lower()}``.
    """
    return {firm.good_name: firm.good_category.lower() for firm in firms}


def get_good_category_capitalized(good_name: str) -> str:
    """Infer the category of a good, returning a capitalized name.

    This is a convenience wrapper for callers that expect capitalized
    category names (e.g., "Housing", "Services", "Healthcare", "Food").

    Parameters
    ----------
    good_name:
        The name of the good.

    Returns
    -------
    str
        Capitalized category name.
    """
    cat = get_good_category(good_name)
    # Map lowercase to capitalized
    mapping = {
        "housing": "Housing",
        "services": "Services",
        "healthcare": "Healthcare",
        "food": "Food",
    }
    return mapping.get(cat, cat.capitalize())
