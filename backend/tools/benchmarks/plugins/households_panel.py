"""#58 evidence-panel metrics for the food-first reserve and the skills plugin.

Combines the sibling modules in this directory. Read-only; draws no random
numbers. Pass this file to ``--metrics-plugin``.
"""
import importlib.util
from pathlib import Path

_DIR = Path(__file__).resolve().parent


def _load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load metrics plugin {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.extra_metrics


_skills = _load("households_skills.py", "households_skills_metrics")
_food = _load("households_foodfirst.py", "households_foodfirst_metrics")


def extra_metrics(economy):
    out = dict(_skills(economy))
    out.update(_food(economy))
    return out
