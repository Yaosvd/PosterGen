"""Explore-only, isolated poster samples for a future Rubrics iteration framework."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import random
import time
import traceback

from src.config.critic_config import load_critic_config
from src.critic.engine import PosterCritic
from src.layout.families import LayoutFamilyRegistry
from src.layout.family_selection import make_family_selection_policy
from src.layout.paper_profile import build_paper_profile
from src.layout.measurement_context import progress_observer
from src.workflow.exploration_store import ExplorationStore, FOUNDATION_FIELDS, now
from src.workflow.generation_failure import GenerationFailure, capture_failure, require_rendered_candidate
from src.workflow.run_control import RunControl
from src.workflow.sample_progress import format_event
from utils.persistence import _atomic_json, digest, file_hash, read_json
from utils.src.logging_utils import log_agent_error, log_agent_warning


def default_nodes():
    from src.agents.parser import parser_node
    from src.agents.evidence_builder import evidence_builder_node
    from src.agents.narrative_planner import narrative_planner_node
    from src.agents.claim_writer import claim_writer_node
    from src.agents.claim_verifier import claim_verifier_node
    from src.agents.grounded_curator import grounded_curator_node
    from src.agents.color_agent import color_agent_node
    from src.agents.section_title_designer import section_title_designer_node
    from src.agents.layout_with_balancer import layout_with_balancer_node
    from src.agents.font_agent import font_agent_node
    from src.agents.layout_preflight import layout_preflight_node
    from src.agents.renderer import renderer_node
    from src.agents.render_fit_audit import render_fit_audit_node
    return ([parser_node, evidence_builder_node, narrative_planner_node, claim_writer_node, claim_verifier_node],
            [grounded_curator_node, color_agent_node, section_title_designer_node,
             layout_with_balancer_node, font_agent_node, layout_preflight_node, renderer_node, render_fit_audit_node])


class PosterExplorationRunner:
    def __init__(self, *, config=None, storage=None, control=None, critic=None,
                 random_seed=None, samples=None, run_id=None, status_callback=None,
                 progress_reporter=None, foundation_nodes=None, design_nodes=None):
        self.config = deepcopy(config if config is not None else load_critic_config())
        from src.config.exploration_config import load_exploration_config
        self.sampling = load_exploration_config()
        self.storage = storage or ExplorationStore(self.sampling['storage_root'])
        self.control = control or RunControl()
        self.critic = critic or PosterCritic(self.config)
        self.random_seed, self.samples, self.run_id = random_seed, samples, run_id
        if samples is not None and (type(samples) is not int or samples < 1):
            raise ValueError('samples must be a positive integer')
        if random_seed is not None and type(random_seed) is not int:
            raise ValueError('random_seed must be an integer')
        foundation, design = default_nodes()
        self.foundation_nodes = list(foundation_nodes if foundation_nodes is not None else foundation)
        self.design_nodes = list(design_nodes if design_nodes is not None else design)
        self.status_callback, self.progress_reporter = status_callback, progress_reporter
        self.registry = LayoutFamilyRegistry()
        self.runtime = {}

    def _progress(self, _runtime, kind, **details):
        event = {'type': kind, 'run_id': self.run_id, **details}
        if self.run_id:
            with (self.storage.run_path(self.run_id) / 'events.jsonl').open('a', encoding='utf-8') as stream:
                import json
                stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        if self.progress_reporter:
            self.progress_reporter.emit(event)
        if self.status_callback:
            self.status_callback({**self.runtime, 'progress_event': event, 'message': format_event(event)})

    def _progress_error(self, runtime, stage, exc, iteration=None):
        self._progress(runtime, 'error', stage=stage, error_type=type(exc).__name__, message=str(exc), iteration=iteration)
        if self.progress_reporter:
            self.progress_reporter.write_traceback(traceback.format_exc())

    @staticmethod
    def _timing_component(node):
        name = getattr(node, '__name__', '').removesuffix('_node')
        return {'grounded_curator': 'curator', 'section_title_designer': 'title_designer',
                'layout_with_balancer': 'layout_optimizer'}.get(name, name)

    def _record_timing(self, state, component, elapsed, iteration):
        metrics = state.get('timing_metrics')
        if metrics is not None and hasattr(metrics, f'{component}_time'):
            metrics.record_component(component, elapsed, iteration)
            del metrics.iteration_timings[:-500]

    def run(self, state, *, foundation_ready=False):
        from src.config.poster_config import load_config
        from src.layout.attempt_inputs import measurement_environment
        state['generation_route'] = 'optimization_family'
        state['critic_config'] = deepcopy(self.config)
        inputs = {key: file_hash(state[key]) if state.get(key) and Path(state[key]).is_file() else None
                  for key in ('pdf_path', 'logo_path', 'aff_logo_path')}
        if inputs['pdf_path'] is None and not foundation_ready:
            raise ValueError('A readable source PDF is required')
        identity = {'inputs': inputs, 'width': state['poster_width'], 'height': state['poster_height'],
                    'text_model': asdict(state['text_model']), 'vision_model': asdict(state['vision_model'])}
        settings = {'critic': self.config, 'sampling': self.sampling, 'poster': load_config(),
                    'measurement_environment': measurement_environment(load_config()),
                    'agent_policy_hash': file_hash('config/agent_policy.yaml'),
                    'generator_version': 'explore_samples_v1'}
        project = Path(__file__).resolve().parents[2]
        code_files = []
        for folder in ('src/agents', 'src/layout', 'src/critic', 'src/state', 'src/config', 'src/workflow', 'utils'):
            code_files.extend(p for p in (project / folder).rglob('*.py') if 'old versions' not in p.parts)
        code_files.extend((project / 'config/prompts').glob('*.txt'))
        settings['code_identity'] = {str(p.relative_to(project)): file_hash(p) for p in sorted(code_files)}
        seed = self.random_seed if self.random_seed is not None else random.SystemRandom().randint(1, 2**31-1)
        self.run_id, manifest = self.storage.open_run(identity, settings, run_id=self.run_id,
            seed=self.random_seed if self.run_id else seed,
            samples=self.samples if self.run_id else (self.samples or self.sampling['default_samples']))
        self.random_seed, self.samples = manifest['seed'], manifest['samples']
        with self.storage.lease(self.run_id) as root:
            self.runtime = {'run_id': self.run_id, 'status': 'RUNNING', 'planned_samples': self.samples}
            self.storage.recover_published(self.run_id)
            self._summary()
            state['output_dir'] = str(root / 'foundation')
            foundation = self.storage.foundation(self.run_id)
            if foundation is None:
                # Copy source inputs so temporary WebUI uploads need not survive a restart.
                input_dir = root / 'inputs'
                input_dir.mkdir(exist_ok=True)
                import shutil
                for key in inputs:
                    if inputs[key] is not None:
                        target = input_dir / (key + Path(state[key]).suffix)
                        shutil.copy2(state[key], target)
                        state[key] = str(target)
                if not foundation_ready:
                    state = self._run_nodes(state, self.foundation_nodes, stage='foundation')
                if self.control.stop_requested:
                    return self._finish(state, 'PAUSED')
                if state.get('errors') or not state.get('verification_passed'):
                    _atomic_json(root / 'foundation_failure.json', {'errors': state.get('errors') or ['Verification failed']})
                    return self._finish(state, 'FAILED')
                self.storage.save_foundation(self.run_id, state)
                foundation = self.storage.foundation(self.run_id)
            # Preserve safe input paths on resume; no old Campaign inputs are consulted.
            for key in inputs:
                matches = list((root / 'inputs').glob(key + '.*'))
                if matches:
                    state[key] = str(matches[0])
            profile = build_paper_profile({**state, **foundation})
            policy = make_family_selection_policy(self.config['layout_families'], self.registry.ids())
            def build_plan():
                counts, tasks = {}, []
                for number in range(1, self.samples + 1):
                    family, selection = self.registry.choose_with_report(profile, counts,
                        random_seed=self.random_seed + number, policy=policy)
                    tasks.append({'sample_id': f'sample_{number:06d}', 'number': number,
                                  'seed': self.random_seed + number, 'family': family,
                                  'selection': selection, 'counts': deepcopy(counts)})
                    counts[family] = counts.get(family, 0) + 1
                return tasks
            tasks = self.storage.plan(self.run_id, build_plan)
            completed = {r['sample_id'] for r in self.storage.results(self.run_id)}
            for task in tasks:
                if task['sample_id'] in completed:
                    continue
                self.control.wait_while_paused(self.status_callback)
                if self.control.stop_requested:
                    return self._finish(state, 'PAUSED')
                state, fatal = self._sample(state, foundation, task, profile, policy)
                self._summary()
                if fatal or self.control.stop_requested:
                    return self._finish(state, 'PAUSED' if self.control.stop_requested else 'FAILED')
            return self._finish(state, 'COMPLETED')

    def _sample(self, original, foundation, task, profile, policy):
        from src.layout.design_content import DESIGN_POLICY_VERSION
        from src.layout.editorial import EDITORIAL_POLICY_VERSION
        from src.layout.presentation_policy import PRESENTATION_POLICY_VERSION
        from src.layout.repair_budget import budget_usage
        sample_id = task['sample_id']
        attempts = self.storage.sample_path(self.run_id, sample_id) / 'attempts'
        excluded = set()
        visual_used = 0
        if attempts.exists():
            for path in sorted(attempts.iterdir()):
                if not path.is_dir():
                    continue
                status = read_json(path / 'status.json')
                if status.get('status') == 'fit_failed':
                    excluded.add(status['reason']['family'])
                audit = path / 'capacity_repair_report.json'
                if audit.exists():
                    visual_used += len(read_json(audit).get('visual_restoration') or [])
        maximum = min(len(policy['enabled_families']), self.config.get('explore_layout', {}).get('max_family_attempts_per_iteration', 12))
        state = original
        for retry in range(len(excluded), maximum):
            # A fresh state includes no design fields, repair variants, or previous score.
            from src.state.poster_state import create_state
            state = create_state(original['pdf_path'], width=original['poster_width'], height=original['poster_height'],
                                 logo_path=original.get('logo_path', ''), aff_logo_path=original.get('aff_logo_path'),
                                 poster_name=original['poster_name'], url=original.get('url', ''))
            state['text_model'], state['vision_model'] = original['text_model'], original['vision_model']
            state['tokens'], state['timing_metrics'] = original.get('tokens'), original.get('timing_metrics')
            state.update(deepcopy(foundation))
            state['generation_route'], state['critic_config'] = 'optimization_family', deepcopy(self.config)
            attempt = self.storage.begin_attempt(self.run_id, sample_id)
            family, selection = self.registry.choose_with_report(profile, task['counts'],
                random_seed=task['seed'], exclude=excluded, policy=policy)
            used = sum(budget_usage(attempt))
            candidate_id = f'{self.run_id}_{sample_id}_{attempt.name}'
            state['output_dir'] = str(attempt / 'work')
            Path(state['output_dir']).mkdir()
            state['iteration_context'] = {
                'run_id': self.run_id, 'sample_id': sample_id, 'iteration': task['number'],
                'attempt_id': attempt.name, 'attempt_number': int(attempt.name.split('_')[-1]),
                'attempt_diagnostics_dir': str(attempt), 'random_seed': task['seed'],
                'layout_family': family, 'generation_purpose': 'explore',
                'capacity_repair_remaining': max(0, self.config.get('capacity_repair', {}).get('max_rounds_per_iteration', 4)-used),
                'visual_restore_remaining': max(0, self.config.get('capacity_repair', {}).get('max_visual_restore_attempts_per_iteration', 4)-visual_used),
                'design_policy_version': DESIGN_POLICY_VERSION, 'editorial_policy_version': EDITORIAL_POLICY_VERSION,
                'presentation_policy_version': PRESENTATION_POLICY_VERSION,
            }
            state['current_candidate'] = {'candidate_id': candidate_id, 'candidate_dir': state['output_dir'], 'status': 'planned'}
            _atomic_json(attempt / 'family_selection_report.json', selection)
            self.runtime.update(sample_id=sample_id, iteration=task['number'], layout_family=family)
            self._progress(self.runtime, 'sample', family=family, iteration=task['number'], attempt=attempt.name)
            with progress_observer(lambda e: self._progress(self.runtime, 'layout_detail', **{k:v for k,v in e.items() if k != 'type'})):
                state = self._run_nodes(state, self.design_nodes, stage='design')
            if self.control.force_stop_requested:
                self.storage.save_attempt(state, 'abandoned', 'force_stop')
                return state, False
            if state.get('attempt_failure_report') or (state.get('errors') and not state.get('layout_preflight_failed')):
                self._finalize(state, task, 'generation_failed', retry)
                return state, True
            if state.get('layout_preflight_failed'):
                report = state.get('layout_feasibility_report') or {}
                shared = (report.get('failure_scope') == 'shared_content' and
                          report.get('reason_code') == 'PRESENTATION_STRUCTURE_UNRESOLVED' and
                          report.get('failure_stage') == 'structure' and report.get('trial_count') == 0)
                reason = 'shared_presentation_structure_unresolved' if shared else 'fit_failed'
                self.storage.save_attempt(state, reason, {'family': family})
                if shared or retry == maximum-1:
                    self._finalize(state, task, reason, retry)
                    return state, shared
                excluded.add(family)
                visual_used += len((state.get('capacity_repair_report') or {}).get('visual_restoration') or [])
                self._progress(self.runtime, 'layout_fit_retry', family=family, reason=report.get('reason_code'))
                if self.control.stop_requested:
                    return state, False
                continue
            try:
                require_rendered_candidate(state, candidate_id, Path(state['output_dir']))
            except GenerationFailure as exc:
                capture_failure(state, exc, agent='renderer', phase='render_readiness')
                self._finalize(state, task, 'generation_failed', retry)
                return state, True
            try:
                state = self.critic(state)
            except Exception as exc:
                capture_failure(state, exc, agent='critic', phase='evaluation')
                state['critic_report'] = {'evaluation_status': 'failed', 'overall_score': None,
                                         'error_type': type(exc).__name__, 'reason': str(exc)}
            if self.control.force_stop_requested:
                self.storage.save_attempt(state, 'abandoned', 'force_stop')
                return state, False
            report = state.get('critic_report') or {}
            complete = report.get('evaluation_status') == 'complete' and report.get('overall_score') is not None
            self._finalize(state, task, 'scored' if complete else 'evaluation_failed', retry)
            return state, False
        raise ValueError('The saved sample retry state exhausted its family pool without a final outcome')

    def _finalize(self, state, task, status, retry):
        context = state['iteration_context']
        report = state.get('critic_report') or {}
        candidate = state.get('current_candidate') or {}
        rendered = candidate.get('status') == 'rendered'
        if rendered:
            try:
                expected_id = f'{self.run_id}_{task["sample_id"]}_{context["attempt_id"]}'
                require_rendered_candidate(state, expected_id, Path(state['output_dir']))
            except GenerationFailure:
                rendered = False
        result = {'run_id': self.run_id, 'sample_id': task['sample_id'], 'status': status,
                  'poster_id': f'{self.run_id}_{task["sample_id"]}' if rendered else None,
                  'candidate_id': candidate.get('candidate_id'), 'attempt_id': context['attempt_id'],
                  'layout_family': context['layout_family'], 'seed': task['seed'],
                  'score': report.get('overall_score') if status == 'scored' else None,
                  'scoring_profile': self.config['rubric_version'], 'generation_rubrics': None,
                  'grouping': 'unclassified', 'dataset': 'rubrics_samples_v1', 'retry_count': retry}
        self.storage.save_attempt(state, status)
        sample_path = self.storage.sample_path(self.run_id, task['sample_id'])
        if rendered:
            from src.workflow.exploration_store import DIAGNOSTIC_FIELDS
            fields = (*DIAGNOSTIC_FIELDS, 'current_candidate', 'poster_width', 'poster_height',
                      'critic_report', 'poster_name')
            payload = {'state': {key: deepcopy(state.get(key)) for key in fields},
                       'artifact_hashes': {kind: file_hash(candidate[f'{kind}_path'])
                                           for kind in ('pptx', 'png')}}
            _atomic_json(sample_path / 'final_output_snapshot.json', {'payload': payload, 'digest': digest(payload)})
        _atomic_json(sample_path / 'pending_result.json', result)
        if rendered:
            self.storage.publish_poster(state, result)
        self.storage.finalize(self.run_id, task['sample_id'], result)
        self._progress(self.runtime, 'sample_saved', result=result)

    def _summary(self):
        results = self.storage.results(self.run_id)
        self.runtime.update(finalized_samples=len(results), rendered_samples=sum(bool(r['poster_id']) for r in results),
                            scored_samples=sum(r['status']=='scored' for r in results),
                            failed_samples=sum(r['status']!='scored' for r in results),
                            results=results, updated_at=now())
        self.storage.save_state(self.run_id, self.runtime)

    def _finish(self, state, status):
        self._summary()
        self.runtime['status'] = status
        self.storage.save_state(self.run_id, self.runtime)
        state['run_state'] = deepcopy(self.runtime)
        state['output_dir'] = str(self.storage.run_path(self.run_id))
        self._progress(self.runtime, 'finished', status=status)
        return state

    def _run_nodes(
        self,
        state,
        nodes,
        *,
        stage: str,
    ):
        nodes = list(nodes)
        loop_state = self.runtime
        iteration = int((state.get("iteration_context") or {}).get("iteration", 0))
        total = len(nodes) if stage == "foundation" else len(nodes) + 2
        for index, node in enumerate(nodes, 1):
            name = self._timing_component(node)
            self._progress(loop_state, "stage_start", stage=name,
                           stage_index=index, stage_total=total,
                           iteration=iteration or None)
            started = time.perf_counter()
            try:
                state = node(state)
            except Exception as exc:
                if stage != "foundation":
                    from src.workflow.generation_failure import capture_failure
                    capture_failure(state, exc, agent=name, phase=name)
                message = f"{getattr(node, '__name__', 'node')}: {exc}"
                state.setdefault("errors", []).append(message)
                log_agent_error("loop_controller", f"{stage} failed: {message}")
                self._progress_error(loop_state, name, exc, iteration or None)
                break
            finally:
                component = self._timing_component(node)
                if component:
                    self._record_timing(state, component, time.perf_counter() - started, iteration)
            if state.get("errors"):
                if stage != "foundation" and not state.get("layout_preflight_failed"):
                    from src.workflow.generation_failure import GenerationFailure, capture_failure
                    capture_failure(state, GenerationFailure(str(state["errors"][-1])),
                                    agent=name, phase=name)
                log_agent_warning("loop_controller", f"{stage} reported errors; candidate generation stopped")
                self._progress(loop_state, "error", stage=name,
                               error_type="AgentError", message=str(state["errors"][-1]),
                               iteration=iteration or None)
                break
            self._progress(loop_state, "stage_done", stage=name,
                           elapsed=time.perf_counter() - started, iteration=iteration or None)
            if stage == "foundation" and self.control.stop_requested:
                log_agent_warning("loop_controller", "foundation stopped between components by user request")
                break
            if self.control.force_stop_requested:
                log_agent_warning("loop_controller", f"{stage} interrupted between components by force-stop")
                break
        pending_completion = state.get('_quality_repair_baseline')
        render_status = (state.get('render_fit_report') or {}).get('status')
        needs_rollback = state.get('layout_preflight_failed') or render_status in {'failed', 'partial', 'unavailable'}
        if pending_completion and not state.get('errors'):
            from src.layout.module_repair import space_preserved
            needs_rollback |= not space_preserved(pending_completion['result'][2],
                                                 state.get('layout_feasibility_report') or {})
        if (pending_completion and stage != 'foundation' and needs_rollback
                and not state.get('attempt_failure_report')
                and not self.control.force_stop_requested
                and (not state.get('errors') or state.get('layout_preflight_failed'))):
            from src.layout.module_recovery import rollback_completion
            if rollback_completion(state) and not state.get('errors'):
                tail = next((i for i, n in enumerate(nodes)
                             if self._timing_component(n) == 'layout_preflight'), None)
                if tail is None:
                    raise ValueError('Completion rollback requires the final typography/render pipeline')
                self._progress(loop_state, 'content_completion_rollback', iteration=iteration,
                               reason='final_fit_failed_or_inconclusive')
                return self._run_nodes(state, nodes[tail:], stage=stage)
        # Runtime-only baseline must never enter snapshots or another attempt.
        state.pop('_quality_repair_baseline', None)
        return state
