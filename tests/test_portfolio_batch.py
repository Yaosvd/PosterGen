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
    assert portfolio["mode_counts"]["explore"] >= 28
    assert portfolio["mode_counts"]["improve"] >= 35
    assert portfolio["mode_counts"]["mutate"] >= 10
    assert portfolio["mode_counts"]["validate"] >= 15
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
