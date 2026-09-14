"""Per-agent model policies for PosterGen."""

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict

import yaml

from src.state.poster_state import ModelConfig


_POLICY_CACHE: Dict[str, Dict[str, Any]] | None = None


def load_agent_policies() -> Dict[str, Dict[str, Any]]:
    global _POLICY_CACHE

    if _POLICY_CACHE is not None:
        return _POLICY_CACHE

    root = Path(__file__).resolve().parent.parent
    path = root / "config" / "agent_policy.yaml"

    if not path.exists():
        _POLICY_CACHE = {}
        return _POLICY_CACHE

    with path.open("r", encoding="utf-8") as f:
        _POLICY_CACHE = yaml.safe_load(f) or {}

    return _POLICY_CACHE


def apply_agent_policy(
    base_config: ModelConfig,
    agent_name: str,
) -> ModelConfig:
    policy = load_agent_policies().get(agent_name)

    if not policy:
        return base_config

    return replace(
        base_config,
        temperature=float(
            policy.get("temperature", base_config.temperature)
        ),
        max_tokens=int(
            policy.get("max_tokens", base_config.max_tokens)
        ),
        enable_thinking=policy.get(
            "thinking",
            base_config.enable_thinking,
        ),
        json_mode=bool(
            policy.get("json_mode", base_config.json_mode)
        ),
    )
