"""Shared contracts for independent Critic evaluators."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol

from src.state.poster_state import PosterState


@dataclass
class CriticContext:
    state: PosterState
    config: Dict[str, Any]


@dataclass
class EvaluationResult:
    evaluator: str
    version: str
    hard_gate: bool
    passed: bool
    scores: Dict[str, float] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    positive_patterns: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluator": self.evaluator,
            "version": self.version,
            "hard_gate": self.hard_gate,
            "passed": self.passed,
            "scores": self.scores,
            "issues": self.issues,
            "positive_patterns": self.positive_patterns,
            "metadata": self.metadata,
        }


class CriticEvaluator(Protocol):
    name: str

    def evaluate(self, context: CriticContext) -> EvaluationResult:
        ...


def issue(
    issue_id: str,
    *,
    severity: str,
    scope: str,
    observation: str,
    required_outcome: str,
    location: Dict[str, Any] | None = None,
    evidence: Dict[str, Any] | None = None,
    allowed_operations: List[str] | None = None,
    forbidden_operations: List[str] | None = None,
) -> Dict[str, Any]:
    """Build the stable issue contract consumed by RevisionPlanner."""

    return {
        "issue_id": issue_id,
        "severity": severity,
        "scope": scope,
        "location": location or {},
        "observation": observation,
        "evidence": evidence or {},
        "required_outcome": required_outcome,
        "allowed_operations": allowed_operations or [],
        "forbidden_operations": forbidden_operations or [],
    }
