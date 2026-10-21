"""Original renderer/repair root causes remain distinct from quality scores."""
from copy import deepcopy
from pathlib import Path
import src.layout.capacity_repair as repair_module
from src.agents.layout_with_balancer import LayoutWithBalancerAgent
from src.agents.renderer import Renderer
from src.config.critic_config import load_critic_config
from utils.persistence import read_json as read

def _state(output: Path):
    return {
        "output_dir": str(output),
        "poster_name": "paper",
        "poster_width": 54,
        "poster_height": 36,
        "verification_passed": True,
        "errors": [],
        "raw_text": "same paper identity",
        "page_records": [],
        "section_chunks": [],
        "images": {},
        "tables": {},
        "classified_visuals": {},
        "evidence_bank": {"version": 1, "items": []},
        "academic_entities": {},
        "narrative_plan": {"sections": []},
        "poster_claims": {},
        "verified_claims": {
            "claims": [{"claim_id": "c1", "text": "One", "evidence_ids": []}]
        },
        "verification_report": {},
    }

def test_layout_repair_exception_retains_measured_fit_and_root_cause(tmp_path, monkeypatch):
    state = _state(tmp_path / "run")
    state.update(generation_route="optimization_family", text_model=object(), tokens=object(),
                 critic_config=load_critic_config(),
                 iteration_context={"generation_purpose": "explore", "layout_family": "result_dashboard_cards"})
    state["story_board"] = {"spatial_content_plan": {"sections": [{"section_id": "one", "claim_ids": ["c1"], "text_content": ["One"], "visual_assets": []}]}}
    report = {"status": "feasible", "zone_utilization": {"main": 0.7}, "worst_zone_utilization": 0.7}
    spec = {"zones": [{"zone_id": "main", "section_ids": ["one"]}]}
    monkeypatch.setattr("src.agents.layout_with_balancer.fit_family_layout", lambda *_, **__: (deepcopy(state["story_board"]), spec, report))
    def crash(*_, **__):
        raise TypeError("original repair crash")
    monkeypatch.setattr(repair_module, "content_optimizer", crash)
    result = LayoutWithBalancerAgent()(state)
    assert result["attempt_failure_report"]["phase"] == "capacity_repair/content_optimizer"
    assert "original repair crash" in result["attempt_failure_report"]["traceback"]
    assert result["layout_feasibility_report"]["status"] == "feasible"
    assert result["capacity_repair_report"]["status"] == "error"
    assert result["capacity_repair_report"]["rounds_attempted"] == 1
    assert read(tmp_path / "run/content/layout_feasibility_report.json")["status"] == "feasible"

def test_renderer_preserves_original_exception(tmp_path, monkeypatch):
    state = _state(tmp_path / "run")
    state["generation_route"] = "optimization_family"
    agent = Renderer()
    monkeypatch.setattr(agent, "_load_styling_interfaces", lambda _: {})
    def crash(*_):
        raise RuntimeError("renderer conversion failed")
    monkeypatch.setattr(agent, "_render_presentation", crash)
    agent(state)
    assert state["attempt_failure_report"]["exception_type"] == "RuntimeError"
    assert state["attempt_failure_report"]["phase"] == "renderer"
