"""Candidate-local storyboard restoration through real parent selection."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from src.config.critic_config import load_critic_config
from src.layout.families import FAMILIES, LayoutArchitect, LayoutFamilyRegistry
from src.layout.feasibility import generate_zone_variants
from src.workflow.campaign import CampaignManager
from src.workflow.campaign_runner import _prepare_improve_parent


def board(owner):
    return {"spatial_content_plan": {"sections": [
        {"section_id": f"s{i}", "claim_ids": [f"{owner}_c{i}"],
         "text_content": ["Synthetic verified statement."], "visual_assets": []}
        for i in range(3)
    ]}}


def payload(family_id, fields, candidate_id="selected"):
    value = {"candidate_id": candidate_id, "accepted": True,
             "fields": {**deepcopy(fields), "critic_report": {"candidate_id": candidate_id}}}
    if family_id == "future_family":
        spec = {"family_id": family_id}
    else:
        family = LayoutFamilyRegistry().get(family_id)
        variant = generate_zone_variants(family, random_seed=7, maximum=1)[0]
        assignments = {z["zone_id"]: [] for z in variant["zones"]}
        for i in range(3):
            zone_id = variant["zones"][i % len(variant["zones"])]["zone_id"]
            assignments[zone_id].append(f"s{i}")
        spec = LayoutArchitect().build({"story_board": board("layout")}, family_id,
            zones_override=variant["zones"], assignments_override=assignments,
            variant_metadata=variant)
    value["fields"].update({"layout_spec": spec, "layout_preflight_report": {"passed": True},
        "layout_feasibility_report": {"status": "feasible", "family_id": family_id,
                                      "geometry_fingerprint": spec.get("geometry_fingerprint")}})
    return value


def setup_parent(tmp_path, value, filename="latest_state.json"):
    manager = CampaignManager(tmp_path / "store", load_critic_config())
    handle = SimpleNamespace(path=tmp_path / "campaign")
    path = handle.path / "lineages" / "selected" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return manager, handle, path


def stale_state():
    return {"story_board": board("previous"), "optimized_story_board": board("previous"),
            "verified_content_bank": {"claims": [{"claim_id": "shared"}]},
            "supplemental_evidence_bank": {"items": [{"evidence_id": "shared"}]}}


@pytest.mark.parametrize("family_id", [f.family_id for f in FAMILIES] + ["future_family"])
@pytest.mark.parametrize("case", ["raw_only", "fitted_only", "both", "fitted_null", "raw_null"])
def test_restored_parent_uses_only_its_own_boards(tmp_path, family_id, case):
    fields = {}
    if case in {"raw_only", "both", "fitted_null"}:
        fields["story_board"] = board("raw")
    if case in {"fitted_only", "both", "raw_null"}:
        fields["optimized_story_board"] = board("fitted")
    if case == "fitted_null":
        fields["optimized_story_board"] = None
    if case == "raw_null":
        fields["story_board"] = None
    manager, handle, path = setup_parent(tmp_path, payload(family_id, fields))
    source = path.read_bytes()
    state = stale_state()
    memory = state["verified_content_bank"]
    evidence = state["supplemental_evidence_bank"]
    assert manager.lineage_parent_status(handle, "selected")["eligible"]
    loaded = manager.load_lineage_snapshot(handle, "selected", state)
    assert loaded["candidate_id"] == "selected"
    assert state["story_board"] == fields.get("story_board")
    assert state["optimized_story_board"] == fields.get("optimized_story_board")
    expected = fields.get("optimized_story_board") or fields["story_board"]
    frozen = _prepare_improve_parent(state, loaded)
    assert frozen["effective_board"] == expected
    assert state["story_board"] == expected
    assert state["verified_content_bank"] is memory
    assert state["supplemental_evidence_bank"] is evidence
    state["story_board"]["spatial_content_plan"]["sections"][0]["claim_ids"].append("edited")
    assert frozen["effective_board"] == expected
    assert path.read_bytes() == source


@pytest.mark.parametrize("fields", [
    {}, {"story_board": None, "optimized_story_board": None},
    {"story_board": {}, "optimized_story_board": {}},
    {"story_board": {"spatial_content_plan": {"sections": []}}},
    {"story_board": "invalid"},
    {"story_board": {"spatial_content_plan": {"sections": [None]}}},
    {"story_board": board("raw"), "optimized_story_board": "corrupt_active_board"},
])
@pytest.mark.parametrize("family_id", ["four_column_modular", "future_family"])
def test_unusable_parent_is_rejected_without_reusing_stale_content(tmp_path, family_id, fields):
    manager, handle, path = setup_parent(tmp_path, payload(family_id, fields))
    source = path.read_bytes()
    state = stale_state()
    memory = deepcopy(state["verified_content_bank"])
    assert manager.lineage_parent_status(handle, "selected") == {
        "eligible": False, "reason": "lineage_storyboard_unavailable"}
    assert manager.load_lineage_snapshot(handle, "selected", state) is None
    assert state["story_board"] is None and state["optimized_story_board"] is None
    assert "improve_parent_snapshot" not in state
    assert state["verified_content_bank"] == memory
    assert path.read_bytes() == source


def test_unusable_best_parent_falls_back_only_to_same_lineage_valid_latest(tmp_path):
    manager, handle, latest = setup_parent(tmp_path,
        payload("four_column_modular", {"story_board": board("latest")}, "latest"))
    best = latest.with_name(f"best_state_{manager.config['rubric_version']}.json")
    best.write_text(json.dumps(payload("four_column_modular", {}, "bad_best")))
    source = {p: p.read_bytes() for p in (latest, best)}
    state = stale_state()
    loaded = manager.load_lineage_snapshot(handle, "selected", state)
    assert loaded["snapshot_kind"] == "latest" and loaded["candidate_id"] == "latest"
    assert _prepare_improve_parent(state, loaded)["effective_board"] == board("latest")
    assert manager.lineage_parent_status(handle, "selected") == {"eligible": True, "snapshot_kind": "latest"}
    assert all(p.read_bytes() == content for p, content in source.items())


def test_restored_boards_do_not_alias_selected_snapshot_or_each_other(tmp_path, monkeypatch):
    shared = board("selected")
    value = payload("four_column_modular", {})
    value["fields"].update(story_board=shared, optimized_story_board=shared)
    manager, handle, _ = setup_parent(tmp_path, value)
    monkeypatch.setattr(manager, "_select_lineage_parent", lambda *_: ("best", value))
    state = stale_state()
    assert manager.load_lineage_snapshot(handle, "selected", state)
    state["story_board"]["spatial_content_plan"]["sections"][0]["claim_ids"].append("edited")
    assert value["fields"]["story_board"] == board("selected")
    assert state["optimized_story_board"] == board("selected")


def test_improve_with_no_usable_parent_stops_before_design_or_critic(tmp_path):
    from src.templates.library import LoopStorage
    from src.workflow.optimization_loop import PosterOptimizationLoop
    from test_campaign_resume import _AlwaysAcceptCritic, _render_candidate, _state

    config = load_critic_config()
    config["layout_families"]["enabled"] = ["classic_three_column", "four_column_modular"]
    storage = LoopStorage(tmp_path / "store", config)
    first = PosterOptimizationLoop(config=config, storage=storage, random_seed=7,
        critic=_AlwaysAcceptCritic(), batch_mode="explore", batch_iterations=1,
        fresh_design_nodes=[_render_candidate], revision_design_nodes=[_render_candidate]
    ).run(_state(tmp_path / "first"), foundation_ready=True)
    campaign = storage.root / "campaigns" / first["loop_state"]["campaign_id"]
    # Derived Lineage files are replayed from committed snapshots at startup.
    # Inject the missing historical fields into both sources in this tmp store.
    paths = list(campaign.glob("iterations/*/attempts/*/state_snapshot.json"))
    paths += list(campaign.glob("lineages/*/*state*.json"))
    for path in paths:
        value = json.loads(path.read_text())
        if isinstance(value.get("fields"), dict):
            value["fields"].pop("story_board", None)
            value["fields"].pop("optimized_story_board", None)
            path.write_text(json.dumps(value))

    def no_model_work(_state):
        pytest.fail("An unavailable parent must not reach design or Critic")

    resumed = PosterOptimizationLoop(config=config, storage=storage, random_seed=7,
        resume_mode="latest", new_batch=True, batch_mode="improve", batch_iterations=1,
        critic=no_model_work, fresh_design_nodes=[no_model_work], revision_design_nodes=[no_model_work]
    ).run(_state(tmp_path / "second"), foundation_ready=True)
    assert resumed["loop_state"]["status"] == "UNAVAILABLE"
    assert resumed["loop_state"]["stop_reason"] == "lineage_unavailable"
    assert resumed["loop_state"]["batch"]["completed_iterations"] == 0
    assert len(list(campaign.glob("iterations/*/COMPLETED.json"))) == 1
