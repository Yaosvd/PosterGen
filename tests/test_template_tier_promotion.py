"""Strict transfer moves a template between isolated retrieval tiers."""

from src.config.critic_config import load_critic_config
from src.templates.library import TemplateLibrary
from src.templates.scoring import TEMPLATE_RUBRIC_VERSION


def _template(template_id, design_score, vector):
    return {
        "template_id": template_id,
        "family": "classic_three_column",
        "status": "paper_specific",
        "template_level": 0,
        "fingerprint": template_id,
        "source_paper_id": "source",
        "source_profile": "balanced:medium",
        "template_design_score": design_score,
        "template_evaluation": {
            "rubric_version": TEMPLATE_RUBRIC_VERSION,
            "score": design_score,
            "coverage": 1.0,
        },
        "signature_vector": [vector],
        "applicability": {"preferred_visual_count": [0, 10]},
        "usage": {"times_retrieved": 0},
    }


def test_promotion_vacates_l0_and_competes_only_with_l1(tmp_path):
    config = load_critic_config()
    config["templates"]["retrieval_slots_by_level"]["0"] = 1
    config["templates"]["retrieval_slots_by_level"]["1"] = 1
    library = TemplateLibrary(tmp_path, config)
    library.register(_template("first", 92, 0))
    library.register(_template("second", 88, 1))
    assert not next(item for item in library._load()["templates"] if item["template_id"] == "second")["retrieval_enabled"]

    library.record_usage(
        template_ids=["second"], campaign_id="validation", paper_id="paper-b",
        profile_key="balanced:medium", iteration=1, accepted=True,
        score=90, event_id="validation:1", validation_run=True,
        transfer_verified=True,
    )
    records = {item["template_id"]: item for item in library._load()["templates"]}
    assert records["first"]["retrieval_enabled"]
    assert records["second"]["retrieval_enabled"]
    assert records["second"]["template_level"] == 1
    assert records["second"]["status"] == "profile_validated"

    # Replaying the committed validation outcome must not add evidence twice.
    library.record_usage(
        template_ids=["second"], campaign_id="validation", paper_id="paper-b",
        profile_key="balanced:medium", iteration=1, accepted=True,
        score=90, event_id="validation:1", validation_run=True,
        transfer_verified=True,
    )
    assert library._load()["templates"][1]["validation"]["successful_events"] == 1
