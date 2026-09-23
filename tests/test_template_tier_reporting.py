"""Operator-facing tier information and strict configuration validation."""

import pytest
import yaml

from src.config.critic_config import load_critic_config
from src.workflow.loop_progress import format_event


def test_committed_event_shows_design_score_and_reference_seat_reason():
    line = format_event({
        "type": "committed", "iteration": 4, "archive": "/accepted/4",
        "template": {
            "registered": True, "template_id": "template-4",
            "design_score": 91.5, "level": 0,
            "retrieval_enabled": False, "retrieval_reason": "tier_capacity",
        },
    })
    assert "template saved template-4" in line
    assert "design 91.5 L0" in line
    assert "reference seat no (tier_capacity)" in line


@pytest.mark.parametrize("slots", [
    {"0": 10, "1": 10, "2": 10},
    {"0": 10, "1": 10, "2": 10, "3": 0},
    {"0": 10, "1": 10, "2": 10, "3": True},
])
def test_invalid_tier_seat_config_is_rejected(tmp_path, slots):
    config = load_critic_config()
    config["templates"]["retrieval_slots_by_level"] = slots
    config_path = tmp_path / "critic_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    with pytest.raises(ValueError, match="retrieval_slots_by_level"):
        load_critic_config(config_path, use_cache=False)


@pytest.mark.parametrize("attempts", [0, -1, True, 1.5])
def test_invalid_cross_paper_validation_attempts_are_rejected(tmp_path, attempts):
    config = load_critic_config()
    config["templates"]["max_cross_paper_validation_attempts"] = attempts
    config_path = tmp_path / "critic_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    with pytest.raises(ValueError, match="max_cross_paper_validation_attempts"):
        load_critic_config(config_path, use_cache=False)


def test_mixed_weights_reject_validate_mode(tmp_path):
    config = load_critic_config()
    config["portfolio"]["mode_weights"] = {
        "explore": 0.30, "improve": 0.40,
        "mutate": 0.12, "validate": 0.18,
    }
    config_path = tmp_path / "critic_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    with pytest.raises(ValueError, match="portfolio.mode_weights"):
        load_critic_config(config_path, use_cache=False)
