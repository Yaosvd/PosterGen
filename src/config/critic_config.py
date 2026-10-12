"""Configuration loader for the poster Critic and optimization loop."""

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from src.layout.families import LayoutFamilyRegistry
from src.layout.family_selection import make_family_selection_policy
from src.layout.measurement_context import validate_settings


_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def load_critic_config(
    path: Optional[Path] = None,
    *,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Load and minimally validate the versioned Critic configuration."""

    global _CONFIG_CACHE

    if path is None and use_cache and _CONFIG_CACHE is not None:
        return deepcopy(_CONFIG_CACHE)

    config_path = path or (
        Path(__file__).resolve().parents[2]
        / "config"
        / "critic_config.yaml"
    )
    with config_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}

    required = {
        "critic_system_version",
        "rubric_version",
        "evaluators",
        "dimensions",
        "dimension_sources",
        "archive_policy",
        "loop",
        "batch",
        "portfolio",
        "improve_layout",
        "layout_families",
        "resume",
        "content_optimization",
        "templates",
        "storage",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(
            "critic configuration is missing keys: "
            + ", ".join(missing)
        )

    dimensions = config["dimensions"]
    dimension_sources = config["dimension_sources"]
    if set(dimension_sources) != set(dimensions):
        raise ValueError("dimension_sources must define every configured dimension exactly once")
    enabled_evaluators = {
        name for name, settings in config["evaluators"].items()
        if settings.get("enabled", True)
    }
    for dimension, sources in dimension_sources.items():
        if not sources or any(float(weight) <= 0 for weight in sources.values()):
            raise ValueError(f"dimension_sources.{dimension} must contain positive weights")
        unknown = set(sources) - enabled_evaluators
        if unknown:
            raise ValueError(
                f"dimension_sources.{dimension} references disabled or unknown evaluators: "
                + ", ".join(sorted(unknown))
            )
    template_minimums = config["templates"].get("dimension_minimums", {})
    if set(template_minimums) - set(dimensions):
        raise ValueError("templates.dimension_minimums contains unknown dimensions")

    strategy_weights = config["loop"].get("strategy_weights", {})
    if not strategy_weights or sum(strategy_weights.values()) <= 0:
        raise ValueError("loop.strategy_weights must contain positive weights")

    no_template_ratio = float(
        config["loop"].get("no_template_minimum_ratio", 0.0)
    )
    validate_settings(config.get("layout_performance"))
    explore = config.get("explore_layout", {})
    first_pass = int(explore.get("max_geometry_candidates_per_family", 4))
    adaptive = int(explore.get("max_adaptive_geometry_candidates", 12))
    if not 1 <= first_pass <= adaptive <= 12:
        raise ValueError(
            "explore_layout geometry search must satisfy "
            "1 <= max_geometry_candidates_per_family <= "
            "max_adaptive_geometry_candidates <= 12"
        )
    beam_width = int(explore.get("beam_width", 4))
    adaptive_beam_width = int(explore.get("adaptive_beam_width", 8))
    subset_limit = int(explore.get("max_extra_claim_subsets_per_section", 12))
    if not 2 <= beam_width <= adaptive_beam_width <= 16:
        raise ValueError("explore_layout beam widths must satisfy 2 <= beam_width <= adaptive_beam_width <= 16")
    if not 1 <= subset_limit <= 32:
        raise ValueError("explore_layout.max_extra_claim_subsets_per_section must be between 1 and 32")
    if not 0 <= int(explore.get("max_near_miss_rechecks", 2)) <= 8:
        raise ValueError("explore_layout.max_near_miss_rechecks must be between 0 and 8")
    if float(explore.get("near_miss_max_overflow_inches", 2.0)) <= 0:
        raise ValueError("explore_layout.near_miss_max_overflow_inches must be positive")
    repair = config.get("capacity_repair") or {}
    if repair:
        family_rounds = int(repair.get("max_rounds_per_family", 2))
        iteration_rounds = int(repair.get("max_rounds_per_iteration", 4))
        actions_per_round = int(repair.get("max_actions_per_round", 2))
        if not 1 <= family_rounds <= iteration_rounds <= 16:
            raise ValueError("capacity_repair rounds must satisfy 1 <= family <= iteration <= 16")
        if not 1 <= actions_per_round <= 2:
            raise ValueError("capacity_repair.max_actions_per_round must be 1 or 2")
        if float(repair.get("max_repairable_overflow_inches", 2.0)) <= 0:
            raise ValueError("capacity_repair.max_repairable_overflow_inches must be positive")
        if not 0.70 <= float(repair.get("active_utilization_threshold", 0.90)) <= 0.95:
            raise ValueError("capacity_repair.active_utilization_threshold must be between 0.70 and 0.95")
        if float(repair.get("large_bottom_gap_body_lines", 2.0)) <= 0:
            raise ValueError("capacity_repair.large_bottom_gap_body_lines must be positive")
        if not 0 <= int(repair.get("max_visual_restore_attempts", 2)) <= 4:
            raise ValueError("capacity_repair.max_visual_restore_attempts must be between 0 and 4")
        if not 1 <= int(repair.get("max_visual_restore_attempts_per_iteration", 4)) <= 16:
            raise ValueError("capacity_repair.max_visual_restore_attempts_per_iteration must be between 1 and 16")
        if not 0 <= float(repair.get("max_whitespace_regression_fraction", 0.01)) <= 0.05:
            raise ValueError("capacity_repair.max_whitespace_regression_fraction must be between 0 and 0.05")
        if not 0 <= float(repair.get("max_gap_regression_inches", 0.35)) <= 1.0:
            raise ValueError("capacity_repair.max_gap_regression_inches must be between 0 and 1")
    explore_weight = float(strategy_weights.get("explore", 0.0))
    if explore_weight < no_template_ratio:
        raise ValueError(
            "explore strategy weight must satisfy no_template_minimum_ratio"
        )

    section_fit = config["evaluators"].get("section_fit", {})
    ideal_minimum = float(section_fit.get("ideal_minimum", 0.95))
    ideal_maximum = float(section_fit.get("ideal_maximum", 1.0))
    planning_target = float(section_fit.get("planning_target", 0.975))
    if not 0 < ideal_minimum <= planning_target <= ideal_maximum <= 1.0:
        raise ValueError(
            "section_fit requires 0 < ideal_minimum <= planning_target "
            "<= ideal_maximum <= 1"
        )

    resume_mode = str(config["resume"].get("default_mode", "latest"))
    if resume_mode not in {"latest", "required", "new"}:
        raise ValueError("resume.default_mode must be latest, required, or new")

    slots = config["templates"].get("retrieval_slots_by_level")
    if not isinstance(slots, dict) or set(slots) != {"0", "1", "2", "3"}:
        raise ValueError("templates.retrieval_slots_by_level must define levels 0, 1, 2, 3")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in slots.values()):
        raise ValueError("templates.retrieval_slots_by_level values must be positive integers")

    max_campaign_records = int(
        config["templates"].get("max_campaign_cooldown_records", 128)
    )
    if max_campaign_records < 1:
        raise ValueError(
            "templates.max_campaign_cooldown_records must be positive"
        )

    max_validation_attempts = config["templates"].get(
        "max_cross_paper_validation_attempts", 3
    )
    if (
        not isinstance(max_validation_attempts, int)
        or isinstance(max_validation_attempts, bool)
        or max_validation_attempts < 1
    ):
        raise ValueError(
            "templates.max_cross_paper_validation_attempts must be a "
            "positive integer"
        )

    if config["batch"].get("default_mode", "mixed") not in {
        "mixed", "explore", "improve", "validate"
    }:
        raise ValueError("batch.default_mode must be a supported scheduling mode")
    if int(config["batch"].get("default_iterations", 100)) < 1:
        raise ValueError("batch.default_iterations must be positive")

    portfolio_weights = config["portfolio"].get("mode_weights", {})
    required_modes = {"explore", "improve"}
    if set(portfolio_weights) != required_modes:
        raise ValueError(
            "portfolio.mode_weights must define explore and improve"
        )
    if any(float(value) < 0 for value in portfolio_weights.values()):
        raise ValueError("portfolio.mode_weights cannot be negative")
    if abs(sum(float(value) for value in portfolio_weights.values()) - 1.0) > 1e-6:
        raise ValueError("portfolio.mode_weights must sum to 1")

    improve_layout = config["improve_layout"]
    for key in ("local_geometry_candidates", "max_preflight_recovery_attempts"):
        value = improve_layout.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"improve_layout.{key} must be a positive integer")

    enabled_families = config["layout_families"].get("enabled", [])
    if not 10 <= len(set(enabled_families)) <= 15:
        raise ValueError("layout_families.enabled must contain 10 to 15 families")
    if "classic_three_column" not in enabled_families:
        raise ValueError("classic_three_column must remain enabled")
    make_family_selection_policy(config["layout_families"], LayoutFamilyRegistry().ids())

    if path is None and use_cache:
        _CONFIG_CACHE = deepcopy(config)
    return deepcopy(config)
