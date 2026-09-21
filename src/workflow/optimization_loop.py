"""User-controlled, persistent Critic optimization loop.

Scientific extraction and verification run once. Every subsequent iteration
changes only a grounded design plan and its rendered artifacts.
"""

import random
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.agents.claim_verifier import claim_verifier_node
from src.agents.content_optimizer import content_optimizer_node
from src.agents.claim_writer import claim_writer_node
from src.agents.color_agent import color_agent_node
from src.agents.evidence_builder import evidence_builder_node
from src.agents.font_agent import font_agent_node
from src.agents.grounded_curator import grounded_curator_node
from src.agents.layout_with_balancer import layout_with_balancer_node
from src.agents.narrative_planner import narrative_planner_node
from src.agents.parser import parser_node
from src.agents.renderer import renderer_node
from src.agents.revision_planner import revision_planner_node
from src.agents.section_title_designer import section_title_designer_node
from src.config.critic_config import load_critic_config
from src.critic.engine import PosterCritic
from src.state.poster_state import PosterState
from src.workflow.campaign import CampaignManager
from src.workflow.portfolio import PortfolioScheduler
from src.templates.library import (
    LoopStorage,
    TemplateDistiller,
    TemplateLibrary,
    build_paper_profile,
)
from utils.src.logging_utils import log_agent_error, log_agent_info, log_agent_success, log_agent_warning


StatusCallback = Callable[[Dict[str, Any]], None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LoopControl:
    """Thread-safe pause/resume/stop control owned by the user interface."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._force_stop = threading.Event()

    def request_stop(self, *, force: bool = False) -> None:
        self._stop.set()
        if force:
            self._force_stop.set()
        self._pause.clear()

    def pause(self) -> None:
        if not self._stop.is_set():
            self._pause.set()

    def resume(self) -> None:
        self._pause.clear()

    @property
    def stop_requested(self) -> bool:
        return self._stop.is_set()

    @property
    def force_stop_requested(self) -> bool:
        return self._force_stop.is_set()

    @property
    def paused(self) -> bool:
        return self._pause.is_set()

    def wait_while_paused(self, callback: Optional[StatusCallback] = None) -> None:
        while self.paused and not self.stop_requested:
            if callback:
                callback({"status": "paused", "message": "Optimization loop paused"})
            self._stop.wait(0.5)


class StrategySelector:
    """Select diverse generation modes while enforcing template-free search."""

    def __init__(self, config: Dict[str, Any], random_seed: int) -> None:
        self.config = config
        self.rng = random.Random(random_seed)
        self.counts: Dict[str, int] = {}

    def select(
        self,
        *,
        iteration: int,
        previous_accepted: Optional[bool],
        lineage_depth: int,
        session_iteration: Optional[int] = None,
    ) -> str:
        loop_config = self.config["loop"]
        max_depth = int(loop_config.get("max_lineage_depth", 3))
        total = sum(self.counts.values())
        required_ratio = float(loop_config.get("no_template_minimum_ratio", 0.4))
        warmup = int(loop_config.get("session_template_free_warmup", 0))
        current_session_iteration = (
            iteration if session_iteration is None else session_iteration
        )
        explore_count = self.counts.get("explore", 0)
        # Evaluate the post-selection ratio so the template-free floor is real.
        must_explore = total > 0 and explore_count / (total + 1) < required_ratio
        if total == 0 or current_session_iteration <= warmup or must_explore:
            strategy = "explore"
        elif previous_accepted is False and lineage_depth < max_depth:
            strategy = "revise"
        else:
            weights = loop_config.get("strategy_weights", {})
            names = list(weights)
            strategy = self.rng.choices(
                names,
                weights=[float(weights[name]) for name in names],
                k=1,
            )[0]
        self.counts[strategy] = self.counts.get(strategy, 0) + 1
        return strategy


class PosterOptimizationLoop:
    """Run candidate generation until the user-controlled stop flag is set."""

    SCIENTIFIC_FIELDS = (
        "raw_text",
        "page_records",
        "section_chunks",
        "images",
        "tables",
        "classified_visuals",
        "evidence_bank",
        "academic_entities",
        "narrative_plan",
        "poster_claims",
        "verified_claims",
        "verification_report",
        "verification_passed",
    )
    DESIGN_FIELDS = (
        "story_board",
        "optimized_story_board",
        "initial_layout_data",
        "column_analysis",
        "balancer_decisions",
        "design_layout",
        "final_column_analysis",
        "optimized_column_assignment",
        "color_scheme",
        "color_provenance",
        "style_overrides",
        "section_title_design",
        "keywords",
        "styled_layout",
        "revision_plan",
        "current_candidate",
        "layout_spec",
        "layout_family_analysis",
    )

    def __init__(
        self,
        *,
        control: Optional[LoopControl] = None,
        config: Optional[Dict[str, Any]] = None,
        storage: Optional[LoopStorage] = None,
        critic: Optional[PosterCritic] = None,
        random_seed: Optional[int] = None,
        status_callback: Optional[StatusCallback] = None,
        foundation_nodes: Optional[Iterable[Callable[[PosterState], PosterState]]] = None,
        fresh_design_nodes: Optional[Iterable[Callable[[PosterState], PosterState]]] = None,
        revision_design_nodes: Optional[Iterable[Callable[[PosterState], PosterState]]] = None,
        campaign_manager: Optional[CampaignManager] = None,
        resume_mode: Optional[str] = None,
        campaign_id: Optional[str] = None,
        batch_iterations: Optional[int] = None,
    ) -> None:
        self.config = config or load_critic_config()
        self.control = control or LoopControl()
        self.storage = storage or LoopStorage(config=self.config)
        self.library = TemplateLibrary(self.storage.root, self.config)
        self.distiller = TemplateDistiller()
        self.critic = critic or PosterCritic(self.config)
        self.random_seed = random_seed if random_seed is not None else random.SystemRandom().randint(1, 2**31 - 1)
        self.selector = StrategySelector(self.config, self.random_seed)
        self.portfolio_scheduler = PortfolioScheduler(
            self.config, self.random_seed
        )
        self.status_callback = status_callback
        self.campaign_manager = campaign_manager or CampaignManager(
            self.storage.root, self.config
        )
        self.resume_mode = resume_mode or str(
            self.config.get("resume", {}).get("default_mode", "latest")
        )
        self.requested_campaign_id = campaign_id
        self.batch_iterations = int(
            batch_iterations
            if batch_iterations is not None
            else self.config.get("batch", {}).get("default_iterations", 100)
        )
        if self.batch_iterations < 1:
            raise ValueError("batch_iterations must be positive")
        self._active_campaign = None
        self.foundation_nodes = list(foundation_nodes or (
            parser_node,
            evidence_builder_node,
            narrative_planner_node,
            claim_writer_node,
            claim_verifier_node,
        ))
        common_design = (
            color_agent_node,
            section_title_designer_node,
            layout_with_balancer_node,
            font_agent_node,
            renderer_node,
        )
        self.fresh_design_nodes = list(fresh_design_nodes or (grounded_curator_node, *common_design))
        self.revision_design_nodes = list(
            revision_design_nodes
            or (revision_planner_node, content_optimizer_node, *common_design)
        )

    def run(
        self,
        state: PosterState,
        *,
        foundation_ready: bool = False,
        max_iterations_for_test: Optional[int] = None,
    ) -> PosterState:
        from src.workflow.campaign_runner import run_optimization_campaign

        return run_optimization_campaign(
            self, state, foundation_ready=foundation_ready,
            max_iterations_for_test=max_iterations_for_test,
        )

    def _run_legacy(
        self,
        state: PosterState,
        *,
        foundation_ready: bool = False,
        max_iterations_for_test: Optional[int] = None,
    ) -> PosterState:
        """Run continuously; the iteration cap exists only for deterministic tests."""

        base_output_dir = Path(state["output_dir"])
        base_output_dir.mkdir(parents=True, exist_ok=True)
        session_id = self.storage.create_session(state["poster_name"])
        loop_state: Dict[str, Any] = {
            "schema_version": 1,
            "session_id": session_id,
            "status": "INITIALIZING",
            "started_at": _utc_now(),
            "updated_at": _utc_now(),
            "paper_id": state["poster_name"],
            "run_output_dir": str(base_output_dir),
            "iteration": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "template_count": 0,
            "best_candidate": None,
            "strategy_counts": {},
            "random_seed": self.random_seed,
            "stop_reason": None,
        }
        state["loop_state"] = loop_state
        state["loop_config"] = {"enabled": True, "session_id": session_id}
        self._checkpoint(loop_state)
        self._notify(loop_state, "Preparing scientific foundation")

        if not foundation_ready:
            state["output_dir"] = str(base_output_dir)
            state = self._run_nodes(state, self.foundation_nodes, stage="foundation")
        if self.control.stop_requested:
            loop_state.update({
                "status": "STOPPED",
                "updated_at": _utc_now(),
                "stopped_at": _utc_now(),
                "stop_reason": "user_force_stop" if self.control.force_stop_requested else "user_requested_before_iterations",
            })
            self._checkpoint(loop_state)
            self._notify(loop_state, "Optimization loop stopped during scientific foundation")
            state["output_dir"] = str(base_output_dir)
            return state
        if state.get("errors") or not state.get("verification_passed"):
            loop_state.update({
                "status": "FAILED_REQUIRES_USER",
                "updated_at": _utc_now(),
                "stop_reason": "scientific_foundation_failed",
                "errors": list(state.get("errors", [])),
            })
            self._checkpoint(loop_state)
            state["output_dir"] = str(base_output_dir)
            return state

        frozen = {name: deepcopy(state.get(name)) for name in self.SCIENTIFIC_FIELDS}
        paper_profile = build_paper_profile(state)
        recent_templates: List[str] = []
        previous_accepted: Optional[bool] = None
        lineage_depth = 0
        best_score = -1.0
        iteration = 0

        while not self.control.stop_requested:
            self.control.wait_while_paused(self.status_callback)
            if self.control.stop_requested:
                break
            iteration += 1
            strategy = self.selector.select(
                iteration=iteration,
                previous_accepted=previous_accepted,
                lineage_depth=lineage_depth,
            )
            if strategy != "revise":
                lineage_depth = 0
            template_context = self.library.retrieve(
                strategy=strategy,
                campaign_id=session_id,
                paper_id=state["poster_name"],
                paper_profile=paper_profile,
                iteration=iteration,
                recent_template_ids=recent_templates,
                random_seed=self.random_seed + iteration,
            )
            selected_template_ids = [
                item["template_id"] for item in template_context if item.get("template_id")
            ]
            recent_templates.extend(selected_template_ids)
            recent_templates = recent_templates[-int(self.config["loop"].get("recent_template_window", 10)):]

            candidate_id = f"{session_id}_{iteration:06d}"
            candidate_dir = base_output_dir / "iterations" / f"{iteration:06d}"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            state["output_dir"] = str(candidate_dir)
            state["iteration_context"] = {
                "session_id": session_id,
                "iteration": iteration,
                "candidate_id": candidate_id,
                "strategy": strategy,
                "parent_candidate_id": (state.get("critic_report") or {}).get("candidate_id") if strategy == "revise" else None,
                "lineage_depth": lineage_depth,
                "random_seed": self.random_seed + iteration,
                "anti_fixation": {
                    "template_free": strategy == "explore",
                    "copy_coordinates_forbidden": True,
                    "recent_template_ids": list(recent_templates),
                },
            }
            state["template_context"] = template_context
            state["current_candidate"] = {
                "candidate_id": candidate_id,
                "candidate_dir": str(candidate_dir),
                "pptx_path": str(candidate_dir / f"{state['poster_name']}.pptx"),
                "png_path": str(candidate_dir / f"{state['poster_name']}.png"),
                "status": "planned",
            }
            state["errors"] = []
            if strategy != "revise":
                for field in self.DESIGN_FIELDS:
                    if field != "current_candidate":
                        state[field] = None

            loop_state.update({"status": "RUNNING", "iteration": iteration, "strategy": strategy, "updated_at": _utc_now()})
            self._notify(loop_state, f"Iteration {iteration}: {strategy}")
            nodes = self.revision_design_nodes if strategy == "revise" else self.fresh_design_nodes
            state = self._run_nodes(state, nodes, stage=f"iteration_{iteration}")

            if self.control.force_stop_requested:
                self._cleanup_iteration_artifacts(state)
                loop_state["stop_reason"] = "user_force_stop"
                break
            guard_violation = False
            for field, value in frozen.items():
                if state.get(field) != value:
                    guard_violation = True
                    state[field] = deepcopy(value)
            state["scientific_guard_violation"] = guard_violation
            critic_started = time.perf_counter()
            state = self.critic(state)
            self._record_timing(
                state,
                "critic",
                time.perf_counter() - critic_started,
                iteration,
            )
            report = state["critic_report"]
            accepted = bool(report.get("archive_eligible"))
            previous_accepted = accepted
            lineage_depth = 0 if accepted else lineage_depth + 1
            self.storage.save_iteration_report(session_id, iteration, report)

            template_registration = None
            if accepted:
                archive = self.storage.archive_candidate(session_id, state, report)
                loop_state["accepted_count"] += 1
                score = float(report.get("overall_score", 0.0))
                if score > best_score:
                    best_score = score
                    self.storage.promote_best(state, archive, base_output_dir)
                    loop_state["best_candidate"] = {
                        "candidate_id": report.get("candidate_id"),
                        "score": score,
                        "archive_dir": archive.get("archive_dir"),
                    }
                template = self.distiller.distill(state, report, paper_profile)
                template_registration = self.library.register(template)
                if template_registration.get("registered"):
                    loop_state["template_count"] += 1
                self._cleanup_iteration_artifacts(state)
            else:
                loop_state["rejected_count"] += 1
                self.storage.record_rejection(session_id, state, report)

            self.library.record_usage(
                template_ids=selected_template_ids,
                campaign_id=session_id,
                paper_id=state["poster_name"],
                profile_key=paper_profile["profile_key"],
                iteration=iteration,
                accepted=accepted,
                score=float(report.get("overall_score", 0.0)),
            )
            loop_state.update({
                "last_candidate_id": report.get("candidate_id"),
                "last_decision": report.get("decision"),
                "last_score": report.get("overall_score"),
                "last_rejection_summary": report.get("rejection_summary"),
                "last_template_registration": (
                    template_registration.get("reason") if template_registration else None
                ),
                "strategy_counts": dict(self.selector.counts),
                "updated_at": _utc_now(),
            })
            self._checkpoint(loop_state)
            self._notify(loop_state, f"Iteration {iteration}: {report.get('decision')} ({report.get('overall_score')})")

            if max_iterations_for_test is not None and iteration >= max_iterations_for_test:
                loop_state["stop_reason"] = "test_iteration_limit"
                break

        loop_state.update({
            "status": "STOPPED",
            "updated_at": _utc_now(),
            "stopped_at": _utc_now(),
            "stop_reason": loop_state.get("stop_reason") or "user_requested",
        })
        self._checkpoint(loop_state)
        self._notify(loop_state, "Optimization loop stopped")
        state["loop_state"] = loop_state
        state["output_dir"] = str(base_output_dir)
        log_agent_success("loop_controller", f"loop {session_id} stopped after {iteration} iterations")
        return state

    def _run_nodes(
        self,
        state: PosterState,
        nodes: Iterable[Callable[[PosterState], PosterState]],
        *,
        stage: str,
    ) -> PosterState:
        for node in nodes:
            started = time.perf_counter()
            try:
                state = node(state)
            except Exception as exc:
                message = f"{getattr(node, '__name__', 'node')}: {exc}"
                state.setdefault("errors", []).append(message)
                log_agent_error("loop_controller", f"{stage} failed: {message}")
                break
            finally:
                component = self._timing_component(node)
                if component:
                    iteration = int((state.get("iteration_context") or {}).get("iteration", 0))
                    self._record_timing(state, component, time.perf_counter() - started, iteration)
            if state.get("errors"):
                log_agent_warning("loop_controller", f"{stage} reported errors; Critic will reject the candidate")
                break
            if stage == "foundation" and self.control.stop_requested:
                log_agent_warning("loop_controller", "foundation stopped between components by user request")
                break
            if self.control.force_stop_requested:
                log_agent_warning("loop_controller", f"{stage} interrupted between components by force-stop")
                break
        return state

    @staticmethod
    def _timing_component(node: Callable[[PosterState], PosterState]) -> str:
        component = getattr(node, "__name__", "").removesuffix("_node")
        aliases = {
            "grounded_curator": "curator",
            "section_title_designer": "title_designer",
            "layout_with_balancer": "layout_optimizer",
        }
        return aliases.get(component, component)

    def _record_timing(
        self,
        state: PosterState,
        component: str,
        elapsed: float,
        iteration: int,
    ) -> None:
        metrics = state.get("timing_metrics")
        if metrics is None:
            return
        if not hasattr(metrics, f"{component}_time"):
            return
        metrics.record_component(component, elapsed, iteration)
        limit = max(
            1,
            int(self.config["loop"].get("timing_history_limit", 500)),
        )
        if len(metrics.iteration_timings) > limit:
            del metrics.iteration_timings[:-limit]

    @staticmethod
    def _cleanup_iteration_artifacts(state: PosterState) -> None:
        candidate = state.get("current_candidate") or {}
        raw_dir = candidate.get("candidate_dir")
        if not raw_dir:
            return
        candidate_dir = Path(raw_dir).resolve()
        for kind in ("pptx", "png"):
            raw_path = candidate.get(f"{kind}_path")
            if not raw_path:
                continue
            path = Path(raw_path).resolve()
            try:
                path.relative_to(candidate_dir)
            except ValueError:
                continue
            if path.is_file():
                path.unlink()

    def _checkpoint(self, loop_state: Dict[str, Any]) -> None:
        self.storage.save_checkpoint(loop_state["session_id"], loop_state)
        if self._active_campaign is not None:
            self.campaign_manager.checkpoint(
                self._active_campaign,
                str(loop_state["session_id"]),
                loop_state,
            )

    def _notify(self, loop_state: Dict[str, Any], message: str) -> None:
        log_agent_info("loop_controller", message)
        if self.status_callback:
            self.status_callback({**loop_state, "message": message})
