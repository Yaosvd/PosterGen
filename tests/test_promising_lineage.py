from src.config.critic_config import load_critic_config
from src.workflow.campaign import CampaignManager
from src.workflow.portfolio import (
    PortfolioScheduler,
    assess_promising_candidate,
    new_portfolio_state,
)


def _report(config, candidate_id, score, *, accepted=False, unsafe=False):
    evaluator = "render_artifacts" if unsafe else "geometry"
    return {
        "candidate_id": candidate_id,
        "iteration": int(candidate_id.removeprefix("c")),
        "overall_score": score,
        "presentation_quality_score": score,
        "decision": "archive" if accepted else "discard",
        "archive_eligible": accepted,
        "rubric_version": config["rubric_version"],
        "critic_system_version": config["critic_system_version"],
        "poster_evaluation": {"evaluated": True},
        "hard_gate_passed": accepted,
        "dimension_scores": {"scientific_integrity": 100.0},
        "evaluations": [{
            "evaluator": evaluator,
            "hard_gate": True,
            "passed": accepted,
        }],
        "issues": ([] if accepted else [{
            "issue_id": f"ISSUE-{candidate_id}",
            "scope": "artifact" if unsafe else "layout",
            "severity": "major",
        }]),
    }


def _seed_task(scheduler, portfolio):
    return scheduler.select(
        portfolio,
        iteration=1,
        session_iteration=1,
        paper_profile={"kind": "balanced", "design_flags": []},
        validation_available=False,
        batch_mode="explore",
    )


def _improve_task(seed_task, candidate_id):
    return {
        "mode": "improve",
        "strategy": "revise",
        "lineage_id": seed_task["lineage_id"],
        "parent_lineage_id": seed_task["lineage_id"],
        "parent_candidate_id": candidate_id,
        "family_id": seed_task["family_id"],
    }


def test_rejected_local_improvement_advances_only_promising_track():
    config = load_critic_config()
    scheduler = PortfolioScheduler(config, random_seed=13)
    portfolio = new_portfolio_state()
    seed = _seed_task(scheduler, portfolio)

    first = _report(config, "c1", 70)
    first["promising_evaluation"] = assess_promising_candidate(
        first, preflight_passed=True
    )
    portfolio = scheduler.commit(portfolio, seed, first, accepted=False)

    improve = _improve_task(seed, "c1")
    second = _report(config, "c2", 75)
    second["promising_evaluation"] = assess_promising_candidate(
        second, preflight_passed=True
    )
    portfolio = scheduler.commit(
        portfolio,
        improve,
        second,
        accepted=False,
        revision_context={"parent_score": 70},
    )
    lineage = portfolio["lineages"][seed["lineage_id"]]
    assert lineage["best_promising_candidate_id"] == "c2"
    assert lineage["best_promising_score"] == 75
    assert lineage["best_accepted_candidate_id"] is None
    assert lineage["latest_feedback"]["local_improvement"] is True
    assert lineage["latest_feedback"]["became_best_promising"] is True
    assert lineage["stagnation_count"] == 0

    third = _report(config, "c3", 73)
    third["promising_evaluation"] = assess_promising_candidate(
        third, preflight_passed=True
    )
    improve["parent_candidate_id"] = "c2"
    portfolio = scheduler.commit(
        portfolio,
        improve,
        third,
        accepted=False,
        revision_context={"parent_score": 75},
    )
    lineage = portfolio["lineages"][seed["lineage_id"]]
    assert lineage["latest_candidate_id"] == "c3"
    assert lineage["best_promising_candidate_id"] == "c2"
    assert lineage["latest_feedback"]["candidate_id"] == "c3"
    assert lineage["latest_feedback"]["local_improvement"] is False
    assert lineage["latest_feedback"]["became_best_promising"] is False
    assert lineage["stagnation_count"] == 1


def test_nonrepairable_high_score_cannot_become_promising():
    config = load_critic_config()
    report = _report(config, "c9", 99, unsafe=True)
    assessment = assess_promising_candidate(report, preflight_passed=True)
    assert assessment["eligible"] is False
    assert any(
        reason.startswith("nonrepairable_hard_gate:render_artifacts")
        for reason in assessment["reasons"]
    )


def test_resume_uses_best_promising_but_keeps_latest_feedback(tmp_path):
    config = load_critic_config()
    scheduler = PortfolioScheduler(config, random_seed=13)
    manager = CampaignManager(tmp_path / "store", config)
    handle = manager.open_campaign({
        "poster_name": "paper",
        "raw_text": "identity",
        "poster_width": 54,
        "poster_height": 36,
    }, resume_mode="new")
    portfolio = new_portfolio_state()
    seed = _seed_task(scheduler, portfolio)

    first = _report(config, "c1", 75)
    first["promising_evaluation"] = assess_promising_candidate(
        first, preflight_passed=True
    )
    portfolio = scheduler.commit(portfolio, seed, first, accepted=False)
    first_state = {
        "critic_report": first,
        "story_board": {"snapshot_candidate": "c1"},
    }

    second = _report(config, "c2", 73)
    second["promising_evaluation"] = assess_promising_candidate(
        second, preflight_passed=True
    )
    portfolio = scheduler.commit(
        portfolio,
        _improve_task(seed, "c1"),
        second,
        accepted=False,
        revision_context={"parent_score": 75},
    )
    lineage = portfolio["lineages"][seed["lineage_id"]]
    # Replay receives final Lineage metadata while rebuilding historical
    # snapshots in commit order. It must still recover c1 as the best base.
    manager.save_lineage_snapshot(
        handle, seed["lineage_id"], first_state, lineage, accepted=False
    )
    manager.save_lineage_snapshot(
        handle,
        seed["lineage_id"],
        {"critic_report": second,
         "story_board": {"snapshot_candidate": "c2"}},
        lineage,
        accepted=False,
    )

    restored = {}
    loaded = manager.load_lineage_snapshot(
        handle, seed["lineage_id"], restored
    )
    assert loaded["snapshot_kind"] == "best_promising"
    assert loaded["candidate_id"] == "c1"
    assert restored["story_board"]["snapshot_candidate"] == "c1"
    assert loaded["feedback_candidate_id"] == "c2"
    assert restored["lineage_feedback"]["candidate_id"] == "c2"


def test_accepted_snapshot_remains_base_after_higher_rejection(tmp_path):
    config = load_critic_config()
    scheduler = PortfolioScheduler(config, random_seed=13)
    manager = CampaignManager(tmp_path / "store", config)
    handle = manager.open_campaign({
        "poster_name": "paper",
        "raw_text": "identity",
        "poster_width": 54,
        "poster_height": 36,
    }, resume_mode="new")
    portfolio = new_portfolio_state()
    seed = _seed_task(scheduler, portfolio)

    accepted = _report(config, "c1", 80, accepted=True)
    portfolio = scheduler.commit(portfolio, seed, accepted, accepted=True)
    lineage = portfolio["lineages"][seed["lineage_id"]]
    manager.save_lineage_snapshot(
        handle,
        seed["lineage_id"],
        {"critic_report": accepted,
         "story_board": {"snapshot_candidate": "c1"}},
        lineage,
        accepted=True,
    )

    rejected = _report(config, "c2", 90)
    rejected["promising_evaluation"] = assess_promising_candidate(
        rejected, preflight_passed=True
    )
    portfolio = scheduler.commit(
        portfolio,
        _improve_task(seed, "c1"),
        rejected,
        accepted=False,
        revision_context={"parent_score": 80},
    )
    lineage = portfolio["lineages"][seed["lineage_id"]]
    assert lineage["status"] == "accepted_poster"
    assert lineage["best_promising_candidate_id"] == "c2"
    manager.save_lineage_snapshot(
        handle,
        seed["lineage_id"],
        {"critic_report": rejected,
         "story_board": {"snapshot_candidate": "c2"}},
        lineage,
        accepted=False,
    )

    restored = {}
    loaded = manager.load_lineage_snapshot(
        handle, seed["lineage_id"], restored
    )
    assert loaded["snapshot_kind"] == "best"
    assert loaded["candidate_id"] == "c1"
    assert restored["story_board"]["snapshot_candidate"] == "c1"
    assert restored["lineage_feedback"]["candidate_id"] == "c2"
