"""Independent template quality, tier seats, and L1 transfer boundaries."""

import json

from src.config.critic_config import load_critic_config
from src.templates.library import TemplateLibrary
from src.templates.scoring import TEMPLATE_RUBRIC_VERSION, score_template


def _template(template_id, *, level=0, score=80, poster_score=90, vector=0.0, visual_range=None):
    return {
        "template_id": template_id,
        "family": "classic_three_column",
        "status": "paper_specific" if level == 0 else "validated",
        "template_level": level,
        "fingerprint": template_id,
        "source_paper_id": "source",
        "source_profile": "balanced:medium",
        "overall_score": poster_score,
        "template_design_score": score,
        "template_evaluation": {
            "rubric_version": TEMPLATE_RUBRIC_VERSION,
            "score": score,
            "status": "scored",
            "coverage": 1.0,
            "components": {},
        },
        "signature_vector": [vector],
        "applicability": {"preferred_visual_count": visual_range or [0, 10]},
        "normalized_blueprint": [],
        "layout_principles": ["Clear hierarchy"],
        "zone_topology": {
            "family_id": "classic_three_column",
            "primary_anchor_zone": "main",
            "zones": [{
                "zone_id": "main", "role": "main", "capacity": 8,
                "x": 0, "y": 0, "width": 1, "height": 1,
            }],
        },
        "usage": {"times_retrieved": 0},
    }


def _retrieve(library, paper_id, profile_key="balanced:medium", strategy="adapt"):
    return library.retrieve(
        strategy=strategy,
        campaign_id=f"campaign-{paper_id}",
        paper_id=paper_id,
        paper_profile={"profile_key": profile_key, "visual_count": 2},
        iteration=1,
        recent_template_ids=[],
        random_seed=1,
    )


def test_design_rubric_excludes_poster_and_scientific_content_scores():
    template = {
        "zone_topology": {
            "primary_anchor_zone": "hero",
            "zones": [
                {"zone_id": "hero", "x": 0, "y": 0, "width": 0.5, "height": 1},
                {"zone_id": "detail", "x": 0.5, "y": 0, "width": 0.5, "height": 1},
            ],
        },
    }
    metrics = {
        "layout_structure": 90, "whitespace_quality": 85,
        "primary_anchor": 95, "compositional_balance": 80,
        "element_alignment": 90, "layout_robustness": 75,
        "font_hierarchy": 88, "font_legibility": 92,
    }
    first = score_template(template, {
        "overall_score": 96, "dimension_scores": {"content_quality": 100},
        "submetric_scores": metrics,
    })
    second = score_template(template, {
        "overall_score": 78, "dimension_scores": {"content_quality": 70},
        "submetric_scores": metrics,
    })
    assert first == second
    assert first["status"] == "scored"
    assert first["coverage"] == 1.0
    assert first["score"] != 96


def test_family_has_ten_independent_seats_per_level(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    for level in range(4):
        for number in range(12):
            score = 80 + number if level == 2 else 60 + number
            library.register(_template(
                f"L{level}_{number}", level=level, score=score,
                vector=level * 10 + number * 0.3,
            ))
    before = {item["template_id"]: item for item in library._load()["templates"]}
    assert before["L2_8"]["template_design_score"] == 88
    assert before["L2_8"]["retrieval_enabled"]

    library.register(_template("L0_96", level=0, score=96, vector=100))
    records = library._load()["templates"]
    for level in range(4):
        assert sum(item["retrieval_enabled"] for item in records if item["template_level"] == level) == 10
    assert next(item for item in records if item["template_id"] == "L2_8")["retrieval_enabled"]
    assert next(item for item in records if item["template_id"] == "L0_96")["retrieval_enabled"]
    assert len(records) == 49  # capacity never deletes accepted templates


def test_seat_ranking_uses_design_score_not_source_poster_score(tmp_path):
    config = load_critic_config()
    config["templates"]["retrieval_slots_by_level"]["0"] = 1
    library = TemplateLibrary(tmp_path, config)
    library.register(_template("better_poster", score=60, poster_score=99, vector=0))
    library.register(_template("better_design", score=90, poster_score=78, vector=1))
    indexed = {item["template_id"]: item for item in library._load()["templates"]}
    assert not indexed["better_poster"]["retrieval_enabled"]
    assert indexed["better_design"]["retrieval_enabled"]


def test_l0_is_source_only_and_l1_cross_paper_reference_requires_strict_success(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    library.register(_template("candidate", visual_range=[0, 10]))
    assert _retrieve(library, "other") == []
    assert [item["template_id"] for item in _retrieve(library, "source")] == ["candidate"]

    library.record_usage(
        template_ids=["candidate"], campaign_id="validation-b", paper_id="paper-b",
        profile_key="balanced:medium", iteration=1, accepted=True, score=88,
        event_id="validation-b:1", validation_run=True, transfer_verified=True,
    )
    assert [item["template_id"] for item in _retrieve(library, "paper-c")] == ["candidate"]
    assert _retrieve(library, "paper-c", "visual_heavy:high") == []
    library.record_usage(
        template_ids=["candidate"], campaign_id="campaign-c", paper_id="paper-c",
        profile_key="balanced:medium", iteration=2, accepted=True, score=92,
        event_id="campaign-c:2", validation_run=False,
    )
    stored = library._load()["templates"][0]
    assert stored["template_level"] == 1
    assert stored["validation"]["cross_paper_success_profiles"] == ["balanced:medium"]
    assert set(stored["validation"]["successful_papers"]) == {"source", "paper-b"}


def test_strict_validation_bypasses_ordinary_seats(tmp_path):
    config = load_critic_config()
    config["templates"]["retrieval_slots_by_level"]["0"] = 1
    library = TemplateLibrary(tmp_path, config)
    library.register(_template("selected", score=95, vector=0, visual_range=[0, 1]))
    library.register(_template("not_selected", score=70, vector=1, visual_range=[2, 3]))
    indexed = {item["template_id"]: item for item in library._load()["templates"]}
    assert not indexed["not_selected"]["retrieval_enabled"]
    assert [item["template_id"] for item in _retrieve(library, "other", strategy="validate")] == ["not_selected"]


def test_v5_migration_backfills_from_archived_report_without_deleting_bundle(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    legacy = _template("legacy", score=80)
    legacy.pop("template_evaluation")
    legacy.pop("template_design_score")
    legacy["source_candidate_id"] = "candidate_1"
    bundle = tmp_path / "accepted_posters" / "candidate_1"
    bundle.mkdir(parents=True)
    (bundle / "critic_report.json").write_text(json.dumps({
        "overall_score": 99,
        "submetric_scores": {"layout_structure": 80, "primary_anchor": 90},
    }))
    library.index_path.parent.mkdir(parents=True)
    library.index_path.write_text(json.dumps({"schema_version": 5, "templates": [legacy]}))
    loaded = library._load()["templates"][0]
    assert loaded["template_design_score"] is not None
    assert loaded["template_design_score"] != 99
    assert loaded["template_evaluation"]["status"] == "partial"
    library.record_usage(
        template_ids=["legacy"], campaign_id="c", paper_id="source",
        profile_key="balanced:medium", iteration=1, accepted=False, score=50,
        event_id="c:1",
    )
    assert json.loads(library.index_path.read_text())["schema_version"] == 10
    assert (bundle / "critic_report.json").is_file()
