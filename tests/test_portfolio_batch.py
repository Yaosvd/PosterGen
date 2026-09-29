from src.config.critic_config import load_critic_config
from src.workflow.campaign import CampaignManager
from src.workflow.portfolio import PortfolioScheduler, new_portfolio_state


def test_portfolio_preserves_multiple_lineages_and_rolling_ratios():
    config = load_critic_config()
    scheduler = PortfolioScheduler(config, random_seed=17)
    portfolio = new_portfolio_state()
    profile = {
        "kind": "balanced",
        "design_flags": ["comparison", "process", "timeline"],
    }

    for iteration in range(1, 101):
        task = scheduler.select(
            portfolio,
            iteration=iteration,
            session_iteration=iteration,
            paper_profile=profile,
            validation_available=True,
        )
        report = {
            "candidate_id": f"c{iteration}",
            "overall_score": 70 + iteration % 20,
            "decision": "archive" if iteration % 3 == 0 else "discard",
            "issues": [],
        }
        portfolio = scheduler.commit(
            portfolio,
            task,
            report,
            accepted=iteration % 3 == 0,
        )

    assert sum(portfolio["mode_counts"].values()) == 100
    assert portfolio["mode_counts"]["explore"] >= 43
    assert portfolio["mode_counts"]["improve"] >= 53
    assert "mutate" not in portfolio["mode_counts"]
    assert portfolio["mode_counts"]["validate"] == 0
    assert len(portfolio["lineages"]) > 4
    assert len(portfolio["family_counts"]) >= 10


def test_batch_resumes_remaining_committed_budget(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    state = {
        "poster_name": "paper",
        "raw_text": "identity",
        "poster_width": 54,
        "poster_height": 36,
    }
    handle = manager.open_campaign(state, resume_mode="new")
    batch = manager.open_batch(handle, target_iterations=100)
    batch["completed_iterations"] = 63
    manager.save_batch(handle, batch)

    resumed = manager.open_batch(handle, target_iterations=100)
    assert resumed["batch_id"] == batch["batch_id"]
    assert resumed["completed_iterations"] == 63
    assert resumed["target_iterations"] - resumed["completed_iterations"] == 37

    resumed["completed_iterations"] = 100
    resumed["status"] = "COMPLETED"
    manager.save_batch(handle, resumed, complete=True)
    next_batch = manager.open_batch(handle, target_iterations=100)
    assert next_batch["batch_number"] == 2
    assert next_batch["completed_iterations"] == 0


def test_frozen_mixed_weights_override_live_scheduler_config():
    config = load_critic_config()
    scheduler = PortfolioScheduler(config, random_seed=5)
    portfolio = new_portfolio_state()
    profile = {"kind": "balanced", "design_flags": []}
    seed = scheduler.select(
        portfolio, iteration=1, session_iteration=1,
        paper_profile=profile, validation_available=False,
        batch_mode="explore",
    )
    portfolio = scheduler.commit(
        portfolio, seed,
        {"candidate_id": "seed", "overall_score": 80, "issues": []},
        accepted=True, batch_mode="explore",
    )
    task = scheduler.select(
        portfolio, iteration=2, session_iteration=4,
        paper_profile=profile, validation_available=True,
        mixed_mode_weights={"explore": 1.0, "improve": 0.0},
    )
    assert task["mode"] == "explore"


def test_incomplete_legacy_mixed_batch_migrates_without_validate_weight(tmp_path):
    config = load_critic_config()
    manager = CampaignManager(tmp_path / "store", config)
    state = {
        "poster_name": "paper", "raw_text": "identity",
        "poster_width": 54, "poster_height": 36,
    }
    handle = manager.open_campaign(state, resume_mode="new")
    batch = manager.open_batch(handle, target_iterations=100, mode="mixed")
    batch["schema_version"] = 2
    batch["schedule_policy"] = {
        "version": 1, "mode": "mixed", "target_lineage_id": None,
        "mode_weights": {
            "explore": 0.30, "improve": 0.40,
            "mutate": 0.12, "validate": 0.18,
        },
    }
    manager.save_batch(handle, batch)

    resumed = manager.open_batch(handle, target_iterations=100)
    assert resumed["schema_version"] == 6
    assert resumed["schedule_policy"]["version"] == 3
    assert resumed["schedule_policy"]["mode_weights"] == {
        "explore": 0.45, "improve": 0.55,
    }
    assert resumed["schedule_policy_migration"]["reason"] == "remove_unused_mutate_mode"


def test_legacy_mutate_history_fails_closed_instead_of_rewriting_history():
    config = load_critic_config()
    scheduler = PortfolioScheduler(config, random_seed=1)
    legacy = new_portfolio_state()
    legacy["mode_counts"]["mutate"] = 1
    legacy["mixed_mode_counts"]["mutate"] = 1
    try:
        scheduler.normalize(legacy)
    except ValueError as exc:
        assert "executed mutate history" in str(exc).lower()
    else:
        raise AssertionError("Mutate history must fail closed")
