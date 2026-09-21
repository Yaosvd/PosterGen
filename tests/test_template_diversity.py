import json

from src.config.critic_config import load_critic_config
from src.templates.library import TemplateLibrary
from src.workflow.optimization_loop import StrategySelector


def _config():
    config = load_critic_config()
    config["evaluators"]["visual"]["enabled"] = False
    return config


def _template(template_id, family, vector, paper_id="paper", status="paper_specific"):
    return {
        "template_id": template_id,
        "status": status,
        "family": family,
        "fingerprint": template_id,
        "source_paper_id": paper_id,
        "overall_score": 85,
        "signature_vector": vector,
        "applicability": {"preferred_visual_count": [0, 10]},
        "layout_principles": [family],
        "normalized_blueprint": [],
        "usage": {
            "times_retrieved": 0,
            "last_used_iteration": None,
            "successful_papers": [paper_id],
            "successful_profiles": ["balanced:medium"],
        },
    }


def test_explore_never_retrieves_template_and_hybrid_uses_distinct_families(tmp_path):
    library = TemplateLibrary(tmp_path, _config())
    assert library.register(_template("t1", "family_a", [0, 0]))["registered"]
    assert library.register(_template("t2", "family_b", [1, 1]))["registered"]
    profile = {"visual_count": 2}
    assert library.retrieve(
        strategy="explore",
        campaign_id="campaign-a",
        paper_id="paper",
        paper_profile=profile,
        iteration=1,
        recent_template_ids=[],
        random_seed=1,
    ) == []
    selected = library.retrieve(
        strategy="hybridize",
        campaign_id="campaign-a",
        paper_id="paper",
        paper_profile=profile,
        iteration=2,
        recent_template_ids=[],
        random_seed=1,
    )
    assert {item["family"] for item in selected} == {"family_a", "family_b"}
    assert library.retrieve(
        strategy="revise",
        campaign_id="campaign-a",
        paper_id="paper",
        paper_profile=profile,
        iteration=3,
        recent_template_ids=[],
        random_seed=2,
    ) == []


def test_registry_rejects_duplicate_template_fingerprint(tmp_path):
    library = TemplateLibrary(tmp_path, _config())
    assert library.register(_template("same", "family_a", [0, 0]))["registered"]
    duplicate = _template("same", "family_a", [0, 0])
    result = library.register(duplicate)
    assert result["registered"] is False
    assert result["reason"] == "duplicate_fingerprint"


def test_candidate_template_can_validate_across_papers_without_cross_session_cooldown(tmp_path):
    library = TemplateLibrary(tmp_path, _config())
    candidate = _template(
        "candidate",
        "family_a",
        [0, 0],
        paper_id="paper_a",
        status="candidate",
    )
    assert library.register(candidate)["registered"]

    selected = library.retrieve(
        strategy="adapt",
        campaign_id="campaign-b",
        paper_id="paper_b",
        paper_profile={"visual_count": 2},
        iteration=1,
        recent_template_ids=[],
        random_seed=1,
    )
    assert [item["template_id"] for item in selected] == ["candidate"]

    library.record_usage(
        template_ids=["candidate"],
        campaign_id="campaign-b",
        paper_id="paper_b",
        profile_key="visual_heavy:medium",
        iteration=1,
        accepted=True,
        score=86,
    )
    library.record_usage(
        template_ids=["candidate"],
        campaign_id="campaign-c",
        paper_id="paper_c",
        profile_key="balanced:medium",
        iteration=1,
        accepted=True,
        score=88,
    )
    index = json.loads(library.index_path.read_text(encoding="utf-8"))
    stored = next(item for item in index["templates"] if item["template_id"] == "candidate")
    assert stored["status"] == "validated"
    assert stored["usage"]["successful_papers"] == ["paper_a", "paper_b", "paper_c"]


def test_strategy_selector_enforces_template_free_floor_and_repair_depth():
    selector = StrategySelector(_config(), random_seed=7)
    strategies = [
        selector.select(
            iteration=index,
            previous_accepted=True,
            lineage_depth=0,
        )
        for index in range(1, 501)
    ]
    assert strategies[:3] == ["explore", "explore", "explore"]
    for prefix_length in range(1, len(strategies) + 1):
        prefix = strategies[:prefix_length]
        assert prefix.count("explore") / prefix_length >= 0.40

    repair_selector = StrategySelector(_config(), random_seed=7)
    repair_selector.counts = {"explore": 2, "adapt": 2}
    assert repair_selector.select(
        iteration=5,
        previous_accepted=False,
        lineage_depth=1,
    ) == "revise"
    assert repair_selector.select(
        iteration=6,
        previous_accepted=False,
        lineage_depth=3,
    ) != "revise"
