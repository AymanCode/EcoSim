"""The LLM government builds its LangGraph state machine, and says so when it cannot."""

import importlib.util
import logging
import sys
from pathlib import Path

import pytest

from config import CONFIG
from tools.llm import llm_government
from tools.llm.llm_provider import LLMProvider

pytestmark = pytest.mark.llm

GRAPH_NODES = {"observe", "apply_info_constraints", "decide", "apply", "fallback", "log"}


class SilentProvider(LLMProvider):
    """Provider that is never called: these tests only build the graph."""

    @property
    def name(self) -> str:
        return "mock/unused"

    async def health_check(self) -> bool:
        return True

    async def complete(self, system: str, user: str, temperature: float = 0.4, top_p=None, response_format=None) -> str:
        raise AssertionError("building the graph must not call the provider")


def test_langgraph_is_installed_and_the_government_graph_builds(tiny_economy_factory):
    # langgraph is a declared dependency. If this fails, decide() has silently fallen
    # back to running the nodes in sequence, and the other advisor tests no longer
    # exercise the graph.
    assert llm_government.HAS_LANGGRAPH, llm_government._LANGGRAPH_IMPORT_ERROR
    economy = tiny_economy_factory(num_households=10, num_firms_per_category=1, disable_shocks=True, seed=11)
    graph = llm_government.build_government_graph(SilentProvider(), CONFIG.llm, economy, [])
    assert GRAPH_NODES <= set(graph.get_graph().nodes)


def test_missing_langgraph_logs_a_warning_and_disables_the_graph(monkeypatch, caplog, tiny_economy_factory):
    # Load a separate copy of the module with langgraph hidden, so the real module
    # (and everything that imported it) is untouched.
    path = Path(llm_government.__file__)
    spec = importlib.util.spec_from_file_location("llm_government_without_langgraph", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "langgraph", None)
    monkeypatch.setitem(sys.modules, "langgraph.graph", None)
    with caplog.at_level(logging.WARNING):
        spec.loader.exec_module(module)
    assert module.HAS_LANGGRAPH is False
    assert isinstance(module._LANGGRAPH_IMPORT_ERROR, ImportError)
    warnings = [r for r in caplog.records if r.name == "llm_government_without_langgraph"]
    assert warnings and "LangGraph could not be imported" in warnings[0].getMessage()
    economy = tiny_economy_factory(num_households=10, num_firms_per_category=1, disable_shocks=True, seed=11)
    assert module.build_government_graph(SilentProvider(), CONFIG.llm, economy, []) is None
