import json

import pytest
import yaml

from src.config.critic_config import load_critic_config
from src.templates.library import TemplateLibrary


def _template(template_id, family, vector):
    return {
        "template_id": template_id,
        "status": "paper_specific",
        "family": family,
        "fingerprint": template_id,
        "source_paper_id": "paper",
        "overall_score": 90,
        "signature_vector": vector,
        "applicability": {"preferred_visual_count": [0, 10]},
        "layout_principles": ["keep a clear visual hierarchy"],
        "density_targets": {"ideal_section_utilization": [0.95, 1.0]},
        "normalized_blueprint": [{
            "role": "section_container",
            "column": "left",
            "x": 0.02,
            "y": 0.12,
            "width": 0.30,
            "height": 0.20,
        }],
        "usage": {
            "times_retrieved": 0,
            "last_used_iteration": None,
            "successful_papers": ["paper"],
            "successful_profiles": ["balanced:medium"],
        },
    }


def test_near_duplicate_is_stored_but_not_retrieved_even_if_family_differs(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template("first", "family-a", [0.1, 0.2]))["registered"]

    duplicate = _template("second", "family-b", [0.1, 0.2])
    result = library.register(duplicate)

    assert result["registered"] is True
    assert result["reason"] == "stored_near_duplicate"
    assert len(library._load()["templates"]) == 2
    assert result["template"]["retrieval_enabled"] is False
    assert len(json.loads(library.validation_queue_path.read_text())["pending"]) == 2


def test_planner_receives_relations_not_exact_template_coordinates(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template("template", "family-a", [0.1, 0.2]))["registered"]

    selected = library.retrieve(
        strategy="adapt",
        campaign_id="campaign-a",
        paper_id="paper",
        paper_profile={"visual_count": 2},
        iteration=1,
        recent_template_ids=[],
        random_seed=1,
    )

    assert len(selected) == 1
    context = selected[0]
    assert "normalized_blueprint" not in context
    assert context["relational_blueprint"] == [{
        "role": "section_container",
        "column": "left",
        "zone": None,
        "vertical_band": "top",
        "width_class": "wide",
        "height_class": "medium",
    }]
    assert context["diversity_requirement"]


def test_template_usage_event_is_idempotent(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template("template", "family-a", [0.1, 0.2]))["registered"]
    kwargs = {
        "template_ids": ["template"],
        "campaign_id": "campaign",
        "paper_id": "paper",
        "profile_key": "balanced:medium",
        "iteration": 7,
        "accepted": True,
        "score": 92,
        "event_id": "campaign:7",
    }

    library.record_usage(**kwargs)
    library.record_usage(**kwargs)

    index = json.loads(library.index_path.read_text(encoding="utf-8"))
    stored = index["templates"][0]
    assert stored["usage"]["times_retrieved"] == 1
    lines = library.outcomes_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def _retrieve_ids(library, campaign_id, iteration):
    return [
        item["template_id"]
        for item in library.retrieve(
            strategy="adapt",
            campaign_id=campaign_id,
            paper_id="paper",
            paper_profile={"visual_count": 2},
            iteration=iteration,
            recent_template_ids=[],
            random_seed=1,
        )
    ]


def test_campaign_scoped_cooldown_does_not_block_new_campaign(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(
        _template("template", "family-a", [0.1, 0.2])
    )["registered"]
    library.record_usage(
        template_ids=["template"],
        campaign_id="campaign-a",
        paper_id="paper",
        profile_key="balanced:medium",
        iteration=30,
        accepted=True,
        score=92,
        event_id="campaign-a:30",
    )

    assert _retrieve_ids(library, "campaign-a", 32) == []
    assert _retrieve_ids(library, "campaign-b", 4) == ["template"]
    assert _retrieve_ids(library, "campaign-a", 40) == ["template"]

    library.record_usage(
        template_ids=["template"],
        campaign_id="campaign-b",
        paper_id="paper",
        profile_key="balanced:medium",
        iteration=8,
        accepted=True,
        score=91,
        event_id="campaign-b:8",
    )
    index = json.loads(library.index_path.read_text(encoding="utf-8"))
    usage = index["templates"][0]["usage"]["last_used_by_campaign"]
    assert set(usage) == {"campaign-a", "campaign-b"}
    assert usage["campaign-a"]["iteration"] == 30
    assert _retrieve_ids(library, "campaign-a", 32) == []


def test_legacy_usage_is_lazily_migrated_without_blocking_new_campaign(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    legacy = _template("template", "family-a", [0.1, 0.2])
    legacy["usage"]["last_used_iteration"] = 30
    legacy["usage"]["last_used_paper_id"] = "paper"
    library.index_path.parent.mkdir(parents=True)
    library.index_path.write_text(json.dumps({
        "schema_version": 1,
        "templates": [legacy],
    }))

    assert _retrieve_ids(library, "campaign-new", 4) == ["template"]
    library.record_usage(
        template_ids=["template"],
        campaign_id="campaign-new",
        paper_id="paper",
        profile_key="balanced:medium",
        iteration=4,
        accepted=False,
        score=70,
        event_id="campaign-new:4",
    )

    index = json.loads(library.index_path.read_text(encoding="utf-8"))
    assert index["schema_version"] == 11
    stored = index["templates"][0]
    assert stored["schema_version"] == 11
    assert stored["usage"]["last_used_by_campaign"]["campaign-new"][
        "iteration"
    ] == 4


def test_campaign_cooldown_history_is_bounded(tmp_path):
    config = load_critic_config()
    config["templates"]["max_campaign_cooldown_records"] = 2
    library = TemplateLibrary(tmp_path, config)
    assert library.register(
        _template("template", "family-a", [0.1, 0.2])
    )["registered"]

    for iteration, campaign_id in enumerate(
        ("campaign-a", "campaign-b", "campaign-c"), start=1
    ):
        library.record_usage(
            template_ids=["template"],
            campaign_id=campaign_id,
            paper_id="paper",
            profile_key="balanced:medium",
            iteration=iteration,
            accepted=False,
            score=70,
            event_id=f"{campaign_id}:{iteration}",
        )

    index = json.loads(library.index_path.read_text(encoding="utf-8"))
    usage = index["templates"][0]["usage"]["last_used_by_campaign"]
    assert set(usage) == {"campaign-b", "campaign-c"}


def test_config_rejects_nonpositive_campaign_cooldown_history(tmp_path):
    config = load_critic_config()
    config["templates"]["max_campaign_cooldown_records"] = 0
    config_path = tmp_path / "critic_config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="max_campaign_cooldown_records",
    ):
        load_critic_config(config_path, use_cache=False)
