"""The one-shot classic path and loop family path must stay independent."""

import json
from copy import deepcopy

import pytest

from src.agents.layout_with_balancer import LayoutWithBalancerAgent
from src.config.critic_config import load_critic_config
from src.layout.families import LayoutFamilyRegistry


def test_layout_optimizer_dispatches_classic_by_explicit_route(monkeypatch):
    agent = LayoutWithBalancerAgent.__new__(LayoutWithBalancerAgent)
    agent.name = "layout_with_balancer"
    calls = []

    def family_engine(state, family_id):
        calls.append(("family", family_id))
        return state

    def old_layout(_state, *, mode):
        calls.append(("classic", mode))
        raise RuntimeError("old route reached")

    monkeypatch.setattr(agent, "_run_family_constraint_engine", family_engine)
    agent.layout_agent = old_layout
    agent.balancer_agent = None

    loop_state = {
        "generation_route": "optimization_family",
        "iteration_context": {"layout_family": "classic_three_column"},
    }
    assert agent(loop_state) is loop_state
    assert calls == [("family", "classic_three_column")]

    calls.clear()
    standalone = {
        "generation_route": "standalone_classic",
        "iteration_context": {"layout_family": "top_hero_bottom_grid"},
    }
    agent(standalone)
    assert calls == [("classic", "initial")]
    assert any("old route reached" in item for item in standalone["errors"])


def test_classic_family_is_available_for_regular_loop_selection():
    registry = LayoutFamilyRegistry()
    compatible = registry.compatible_ids({"kind": "balanced"})
    assert "classic_three_column" in compatible
    assert len(compatible) > 1
