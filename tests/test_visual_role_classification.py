"""Paper-semantic visual roles and route-isolated grounded curation."""

import json
from types import SimpleNamespace

import src.agents.grounded_curator as curator_module
import src.agents.parser as parser_module
from src.agents.visual_classification import (
    ROLE_FIELDS,
    normalize_visual_classification,
)
from src.critic.base import CriticContext
from src.critic.quality import VisualAssetEvaluator
from src.workflow.campaign import CampaignManager, FOUNDATION_SCHEMA_VERSION


def _visuals():
    return [
        {"id": "figure_1", "caption": "Architecture of the method"},
        {"id": "figure_2", "caption": "Primary accuracy results"},
        {"id": "table_1", "caption": "Ablation comparison"},
    ]


def test_roles_are_exhaustive_unique_and_key_is_a_pointer():
    roles, audit = normalize_visual_classification({
        "key_visual": "figure_2",
        "method_workflow": ["figure_1", "figure_2", "bad_id"],
        "main_results": ["figure_2"],
    }, _visuals(), source="model_with_safe_repairs")
    members = [visual_id for role in ROLE_FIELDS for visual_id in roles[role]]
    assert sorted(members) == ["figure_1", "figure_2", "table_1"]
    assert len(members) == len(set(members))
    assert roles["key_visual"] == "figure_2"
    assert roles["comparative_results"] == ["table_1"]
    assert {item["code"] for item in audit["observations"]} >= {
        "duplicate_visual_id", "unknown_visual_id", "missing_role_filled"
    }
    assert "Architecture" not in json.dumps(audit)


def test_explicit_null_key_stays_null_and_fallback_does_not_guess_between_visuals():
    roles, _ = normalize_visual_classification({
        "key_visual": None,
        "method_workflow": ["figure_1"],
        "main_results": ["figure_2"],
        "comparative_results": ["table_1"],
    }, _visuals(), source="model_with_safe_repairs")
    assert roles["key_visual"] is None
    fallback, _ = normalize_visual_classification(
        None, _visuals(), source="caption_fallback"
    )
    assert fallback["key_visual"] is None
    assert fallback["main_results"] == ["figure_2"]
    assert fallback["comparative_results"] == ["table_1"]


def test_single_table_can_be_key_without_method_or_column_bias():
    classification, _ = normalize_visual_classification(
        None, [{"id": "table_1", "caption": "Main results"}], source="caption_fallback"
    )
    assert classification["key_visual"] == "table_1"
    assert classification["main_results"] == ["table_1"]


def test_parser_repairs_model_ids_and_records_caption_only_provenance(monkeypatch):
    class FakeAgent:
        def __init__(self, *_args):
            pass

        def reset(self):
            pass

        def step(self, prompt):
            assert "Do not" in prompt and "layout family" in prompt
            return SimpleNamespace(content=json.dumps({
                "key_visual": "table_1",
                "comparative_results": ["table_1", "figure_1", "made_up"],
                "method_workflow": ["figure_1"],
            }), input_tokens=2, output_tokens=3)

    monkeypatch.setattr(parser_module, "LangGraphAgent", FakeAgent)
    monkeypatch.setattr(parser_module, "apply_agent_policy", lambda cfg, _name: cfg)
    parser = parser_module.Parser.__new__(parser_module.Parser)
    parser.name = "parser"
    parser.visual_classification_prompt = parser_module.load_prompt(
        "config/prompts/classify_visuals.txt"
    )
    state = {}
    result, input_tokens, output_tokens = parser._classify_visual_assets(
        {"1": {"caption": "Architecture", "aspect": 1.0}},
        {"1": {"caption": "Ablation", "aspect": 1.0}},
        "unused source text", object(), state,
    )
    assert (input_tokens, output_tokens) == (2, 3)
    assert result["key_visual"] == "table_1"
    assert result["comparative_results"] == ["table_1"]
    assert result["method_workflow"] == ["figure_1"]
    assert state["visual_classification_report"]["input_modality"] == "captions_and_aspect_only"
    assert len(state["visual_classification_report"]["observations"]) == 2


def test_legacy_campaign_foundation_remains_readable_without_new_audit(tmp_path):
    foundation = tmp_path / "foundation"
    foundation.mkdir()
    (foundation / "scientific_state.json").write_text(json.dumps({
        "schema_version": FOUNDATION_SCHEMA_VERSION,
        "fields": {
            "verification_passed": True,
            "classified_visuals": {"key_visual": "figure_1"},
        },
    }), encoding="utf-8")
    manager = CampaignManager.__new__(CampaignManager)
    state = {}
    assert manager.load_foundation(SimpleNamespace(path=tmp_path), state)
    assert state["classified_visuals"]["key_visual"] == "figure_1"
    assert state.get("visual_classification_report") is None


def _curator_state(tmp_path, route):
    return {
        "generation_route": route,
        "text_model": object(),
        "tokens": SimpleNamespace(add_text=lambda *_args: None),
        "output_dir": str(tmp_path), "errors": [],
        "verified_claims": {"claims": [{
            "claim_id": "c1", "section_id": "results", "text": "Verified result."
        }]},
        "narrative_plan": {"sections": [{
            "section_id": "results", "title_intent": "Results",
            "narrative_role": "results", "evidence_ids": ["e1"],
        }]},
        "images": {"2": {"caption": "Primary result", "aspect": 1.4}},
        "tables": {},
        "classified_visuals": {
            "key_visual": "figure_2", "main_results": ["figure_2"],
        },
    }


def test_loop_curator_ignores_model_column_and_seeds_relevant_key(tmp_path, monkeypatch):
    seen = []

    class FakeAgent:
        def __init__(self, *_args):
            pass

        def reset(self):
            pass

        def step(self, prompt):
            seen.append(prompt)
            return SimpleNamespace(content=json.dumps({
                "spatial_content_plan": {"sections": [{
                    "section_id": "results", "section_title": "Results",
                    "column_assignment": "right", "claim_ids": ["c1"],
                    "visual_assets": [],
                }]}
            }), input_tokens=1, output_tokens=1)

    monkeypatch.setattr(curator_module, "LangGraphAgent", FakeAgent)
    monkeypatch.setattr(curator_module, "apply_agent_policy", lambda cfg, _name: cfg)
    state = curator_module.GroundedCurator()(
        _curator_state(tmp_path, "optimization_family")
    )
    section = state["story_board"]["spatial_content_plan"]["sections"][0]
    assert state["errors"] == []
    assert section["column_assignment"] == "left"  # ignored legacy placeholder
    assert section["text_content"] == ["Verified result."]
    assert section["visual_assets"] == [{"visual_id": "figure_2"}]
    assert state["visual_curation_report"]["key_seed_status"] == "seeded_as_optional_candidate"
    assert "Do not supply column_assignment" in seen[0]


def test_standalone_curator_keeps_classic_column_behavior(tmp_path, monkeypatch):
    class FakeAgent:
        def __init__(self, *_args):
            pass

        def reset(self):
            pass

        def step(self, prompt):
            assert "Use all three columns" in prompt
            return SimpleNamespace(content=json.dumps({
                "spatial_content_plan": {"sections": [{
                    "section_id": "results", "section_title": "Results",
                    "column_assignment": "right", "claim_ids": ["c1"],
                    "visual_assets": [],
                }]}
            }), input_tokens=1, output_tokens=1)

    monkeypatch.setattr(curator_module, "LangGraphAgent", FakeAgent)
    monkeypatch.setattr(curator_module, "apply_agent_policy", lambda cfg, _name: cfg)
    state = curator_module.GroundedCurator()(
        _curator_state(tmp_path, "standalone_classic")
    )
    section = state["story_board"]["spatial_content_plan"]["sections"][0]
    assert section["column_assignment"] == "right"
    assert section["visual_assets"] == []


def test_loop_curator_fallback_can_seed_one_relevant_visual(tmp_path, monkeypatch):
    class FailingAgent:
        def __init__(self, *_args):
            pass

        def reset(self):
            pass

        def step(self, _prompt):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(curator_module, "LangGraphAgent", FailingAgent)
    monkeypatch.setattr(curator_module, "apply_agent_policy", lambda cfg, _name: cfg)
    state = curator_module.GroundedCurator()(
        _curator_state(tmp_path, "optimization_family")
    )
    section = state["story_board"]["spatial_content_plan"]["sections"][0]
    assert section["visual_assets"] == [{"visual_id": "figure_2"}]
    assert state["visual_curation_report"]["key_seed_status"] == "seeded_as_optional_candidate"


def test_critic_audits_assets_omitted_before_solver_without_new_hard_gate():
    state = {
        "images": {"1": {}, "2": {}}, "tables": {},
        "classified_visuals": {"key_visual": "figure_2"},
        "visual_classification_report": {"policy_version": "semantic_visual_roles_v2"},
        "story_board": {"spatial_content_plan": {"sections": [{
            "section_id": "s1", "visual_assets": [{"visual_id": "figure_1"}],
        }]}},
        "optimized_story_board": {"spatial_content_plan": {"sections": [{
            "section_id": "s1", "visual_assets": [],
        }]}},
    }
    result = VisualAssetEvaluator().evaluate(CriticContext(
        state, {"evaluators": {"visual_assets": {"hard_gate": True}}}
    ))
    selection = result.metadata["source_visual_selection"]
    assert selection["uncurated_visual_ids"] == ["figure_2"]
    assert selection["key_visual_uncurated"] is True
    assert result.passed is True
