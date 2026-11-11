"""Explore-only, isolated poster samples for a future Rubrics iteration framework."""
from copy import deepcopy
from pathlib import Path
import random
import time
import traceback

from src.config.critic_config import load_critic_config
from src.critic.engine import PosterCritic
from src.layout.families import LayoutFamilyRegistry
from src.layout.family_selection import make_family_selection_policy
from src.layout.paper_profile import build_paper_profile, build_planning_profile
from src.layout.measurement_context import progress_observer
from src.workflow.exploration_store import ExplorationStore, DATASET, now
from src.workflow.poster_grouping import complete_score, poster_group
from src.workflow.content_contracts import GENERATOR_VERSION, PREPARATION_VERSION, science_fields, science_ready
from src.workflow.sample_preparation import SamplePreparation
from src.workflow.task_inputs import VERSION as TASK_ENTRY_VERSION, input_identity, enter_task
from src.workflow.generation_failure import GenerationFailure, capture_failure, require_rendered_candidate
from src.workflow.run_control import RunControl
from src.workflow.sample_progress import format_event
from utils.persistence import _atomic_json, digest, file_hash, read_json
from utils.src.logging_utils import log_agent_error, log_agent_warning


def default_nodes():
    from src.agents.parser import parser_node
    from src.workflow.editorial_pipeline import (editorial_curator_node, editorial_color_node,
        editorial_title_node, editorial_joint_node, editorial_compile_node)
    from src.agents.font_agent import font_agent_node
    from src.agents.layout_preflight import layout_preflight_node
    from src.agents.renderer import renderer_node
    from src.agents.render_fit_audit import render_fit_audit_node
    return ([parser_node],
            [editorial_curator_node, editorial_color_node, editorial_title_node, editorial_joint_node],
            [editorial_compile_node, font_agent_node, layout_preflight_node, renderer_node, render_fit_audit_node])



class PosterExplorationRunner:
    def __init__(self, *, config=None, storage=None, control=None, critic=None,
                 random_seed=None, samples=None, run_id=None, status_callback=None,
                 progress_reporter=None, paper_nodes=None, preparation_nodes=None, design_nodes=None, paper_cache_run_id=None,
                 paper_cache_sample_id=None, input_states=None):
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
        paper, preparation, design = default_nodes()
        self.paper_nodes = list(paper_nodes if paper_nodes is not None else paper)
        self.preparation_nodes = list(preparation_nodes if preparation_nodes is not None else preparation)
        self.editorial_default = any(getattr(n, '__name__', '') == 'editorial_joint_node' for n in self.preparation_nodes)
        self.source_default = any(getattr(n, '__name__', '') == 'source_joint_preparation_node' for n in self.preparation_nodes)
        self.joint_default = self.editorial_default or self.source_default or any(getattr(n, '__name__', '') == 'joint_preparation_node' for n in self.preparation_nodes)
        if self.source_default and critic is None:
            raise ValueError('Retired source Critic: diagnostic source helpers require an explicitly supplied critic')
        if self.editorial_default:
            from src.workflow.editorial_critic import editorial_critic_config, make_critic
            self.config = editorial_critic_config(self.config)
            if critic is None:
                self.critic = make_critic(self.config)
        self.design_nodes = list(design_nodes if design_nodes is not None else design)
        self.status_callback, self.progress_reporter = status_callback, progress_reporter
        self.registry = LayoutFamilyRegistry()
        self.runtime = {}
        self._curation = None
        self.paper_cache_run_id = paper_cache_run_id
        self.paper_cache_sample_id = paper_cache_sample_id
        if paper_cache_sample_id and not paper_cache_run_id and not run_id:
            raise ValueError('paper_cache_sample_id requires paper_cache_run_id')
        self.input_states = list(input_states) if input_states is not None else None
        if self.input_states is not None:
            if not self.input_states or (samples is not None and samples != len(self.input_states)):
                raise ValueError('Task inputs must match the frozen sample count')
            if any('task_random_seed' in value and type(value['task_random_seed']) is not int
                   for value in self.input_states):
                raise ValueError('Task random_seed must be an integer')
            self.samples = len(self.input_states)

    def _progress(self, _runtime, kind, **details):
        event = {'type': kind, 'run_id': self.run_id,
                 'iteration': self.runtime.get('iteration'),
                 'planned_samples': self.runtime.get('planned_samples'), **details}
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
        return {'sample_module_planner': 'curator', 'sample_claim_verifier': 'claim_verifier',
                'grounded_curator': 'curator', 'section_title_designer': 'title_designer',
                'layout_with_balancer': 'layout_optimizer', 'compile_joint_layout': 'layout_optimizer',
                'joint_preparation': 'joint_preparation', 'plan_family_capacity': 'space_draft',
                'source_narrative': 'narrative_planner', 'source_curator': 'curator',
                'editorial_curator': 'curator', 'editorial_color': 'color_agent',
                'editorial_title': 'title_designer', 'editorial_joint': 'joint_preparation',
                'editorial_compile': 'layout_optimizer',
                'source_joint_preparation': 'joint_preparation', 'source_document': 'source_document',
                'install_source_candidate': 'source_install', 'compile_source_layout': 'layout_optimizer'}.get(name, name)

    def _record_timing(self, state, component, elapsed, iteration):
        metrics = state.get('timing_metrics')
        if metrics is not None and hasattr(metrics, 'record_component'):
            metrics.record_component(component, elapsed, iteration)
            del metrics.iteration_timings[:-500]

    def run(self, state, *, paper_ready=False):
        from src.config.poster_config import load_config
        from src.layout.attempt_inputs import measurement_environment
        state['generation_route'] = 'optimization_family'
        if self.editorial_default:
            from src.workflow.editorial_contract import VERSION
            state['editorial_version'] = VERSION
        if self.source_default:
            from src.workflow.source_document import VERSION
            state['source_editorial_version'] = VERSION
        state['critic_config'] = deepcopy(self.config)
        accounting = {key: state[key] for key in ('tokens', 'timing_metrics')}
        # Every task starts from its own PDF/Logo/parameter input state.
        originals = self.input_states if self.input_states is not None else [state]
        identities = [input_identity(value) for value in originals]
        identity = identities[0] if self.input_states is None else {'task_inputs': identities,
            'task_seeds': [value.get('task_random_seed') for value in originals]}
        settings = {'project_identity': 'rubrics_poster_v1', 'critic': self.config, 'sampling': self.sampling, 'poster': load_config(),
                    'measurement_environment': measurement_environment(load_config()),
                    'agent_policy_hash': file_hash('config/agent_policy.yaml'),
                    'generator_version': GENERATOR_VERSION, 'task_entry_policy': TASK_ENTRY_VERSION,
                    'preparation_policy_version': PREPARATION_VERSION}
        if self.source_default or self.editorial_default:
            from utils.source_pdf import extraction_environment
            settings['source_extraction_environment'] = dict(extraction_environment())
        project = Path(__file__).resolve().parents[2]
        code_files = []
        for folder in ('src/agents', 'src/layout', 'src/critic', 'src/state', 'src/config', 'src/workflow', 'utils'):
            code_files.extend(p for p in (project / folder).rglob('*.py') if 'old versions' not in p.parts)
        code_files.extend((project / 'config/prompts').glob('*.txt'))
        settings['code_identity'] = {str(p.relative_to(project)): file_hash(p) for p in sorted(code_files)}
        if self.run_id and self.paper_cache_run_id is None:
            previous_settings = read_json(self.storage.run_path(self.run_id)/'manifest.json')['settings']
            self.paper_cache_run_id = previous_settings.get('paper_cache_run_id')
            if self.paper_cache_sample_id is None:
                self.paper_cache_sample_id = previous_settings.get('paper_cache_sample_id')
        settings['paper_cache_run_id'] = self.paper_cache_run_id
        settings['paper_cache_sample_id'] = self.paper_cache_sample_id
        seed = self.random_seed if self.random_seed is not None else random.SystemRandom().randint(1, 2**31-1)
        self.run_id, manifest = self.storage.open_run(identity, settings, run_id=self.run_id,
            seed=self.random_seed if self.run_id else seed,
            samples=self.samples if self.run_id else (self.samples or self.sampling['default_samples']))
        self.random_seed, self.samples = manifest['seed'], manifest['samples']
        with self.storage.lease(self.run_id) as root:
            self.runtime = {'run_id': self.run_id, 'status': 'RUNNING', 'planned_samples': self.samples}
            self.storage.recover_published(self.run_id)
            self._summary()
            policy = make_family_selection_policy(self.config['layout_families'], self.registry.ids())
            def build_plan():
                return [{'sample_id': f'sample_{number:06d}', 'number': number,
                         'seed': (originals[number - 1].get('task_random_seed', self.random_seed + number)
                                  if self.input_states is not None else self.random_seed + number)}
                        for number in range(1, self.samples + 1)]
            tasks = self.storage.plan(self.run_id, build_plan)
            if tasks != build_plan():
                raise ValueError('Full poster task plan changed')
            completed = {r['sample_id']: r for r in self.storage.results(self.run_id)}
            counts = {}
            from src.workflow.editorial_pipeline import EditorialPreparation
            preparation_class = EditorialPreparation if self.editorial_default else SamplePreparation
            preparation = preparation_class(self.storage, self.run_id, self.preparation_nodes)
            for task in tasks:
                if task['sample_id'] in completed:
                    assignment = self.storage.saved_assignment(self.run_id, task, counts)
                    if assignment is None and completed[task['sample_id']]['status'] != 'preparation_failed':
                        raise ValueError('Finalized sample is missing its family assignment')
                    if assignment:
                        counts[assignment['family']] = counts.get(assignment['family'], 0) + 1
                    continue
                self.control.wait_while_paused(self.status_callback)
                if self.control.stop_requested:
                    return self._finish(state, 'PAUSED')
                self.runtime.update(sample_id=task['sample_id'], iteration=task['number'], layout_family=None)
                original = originals[task['number'] - 1] if self.input_states is not None else originals[0]
                task_identity = identities[task['number'] - 1] if self.input_states is not None else identities[0]
                state = self._fresh_state(original, {})
                state.update(accounting)
                if self.editorial_default:
                    from src.workflow.editorial_contract import VERSION
                    state['editorial_version'] = VERSION
                if self.source_default:
                    from src.workflow.source_document import VERSION
                    state['source_editorial_version'] = VERSION
                cache = {'run_id': self.paper_cache_run_id, 'sample_id': self.paper_cache_sample_id}
                state = enter_task(self.storage, self.run_id, task, state, task_identity,
                                   manifest['settings_digest'], cache)
                state['iteration_context'] = {'run_id': self.run_id, 'sample_id': task['sample_id'],
                    'iteration': task['number'], 'random_seed': task['seed']}
                state['_force_stop_requested'] = lambda: self.control.force_stop_requested
                self._progress(self.runtime, 'task_inputs', iteration=task['number'], inputs=task_identity)
                state, paper = self._prepare_paper(state, task, original, task_identity, settings, paper_ready)
                if paper is None:
                    return self._finish(state, 'PAUSED' if self.control.stop_requested else 'FAILED')
                if self.control.stop_requested:
                    return self._finish(state, 'PAUSED')
                paper_digest = self.storage.paper_identity(self.run_id, task['sample_id'])
                state = self._fresh_state(state, paper)
                state['paper_foundation_digest'] = paper_digest
                state['joint_preparation'] = self.joint_default
                state['_force_stop_requested'] = lambda: self.control.force_stop_requested
                selected = {}
                def freeze_family(current):
                    profile = build_planning_profile(current)
                    assignment = self.storage.family_assignment(self.run_id, task, profile, counts,
                        lambda: self.registry.choose_with_report(profile, counts,
                            random_seed=task['seed'], policy=policy))
                    current['sample_family'] = deepcopy(assignment)
                    current['iteration_context']['layout_family'] = assignment['family']
                    # Explore enables adaptive geometry variants, without cross-family retries.
                    current['iteration_context']['generation_purpose'] = 'explore'
                    selected.update(profile=profile, assignment=assignment)
                    self.runtime['layout_family'] = assignment['family']
                    self._progress(self.runtime, 'family_frozen', family=assignment['family'], iteration=task['number'])
                with progress_observer(lambda e: self._progress(self.runtime, 'layout_detail', **{k:v for k,v in e.items() if k != 'type'})):
                    state = preparation.run(state, task, self._run_nodes, self.control, after_planner=freeze_family)
                if self.control.force_stop_requested:
                    return self._finish(state, 'PAUSED')
                if selected:
                    assignment = selected['assignment']
                    counts[assignment['family']] = counts.get(assignment['family'], 0) + 1
                if state.get('errors') or not science_ready(state):
                    self._preparation_failed(state, task)
                    self._summary()
                    if state.get('fatal_generation_error'):
                        return self._finish(state, 'FAILED')
                    continue
                profile = selected['profile']
                foundation = {**deepcopy(paper), **science_fields(state),
                              'paper_foundation_digest': paper_digest,
                              'sample_science_digest': state['sample_science_digest']}
                design_task = {**task, 'family': assignment['family'], 'counts': assignment['counts']}
                state, fatal = self._sample(state, foundation, design_task, profile, policy)
                self._summary()
                if fatal or self.control.stop_requested:
                    return self._finish(state, 'PAUSED' if self.control.stop_requested else 'FAILED')
            return self._finish(state, 'COMPLETED')

    def _prepare_paper(self, state, task, original, identity, settings, paper_ready):
        sample_id = task['sample_id']
        root = self.storage.paper_path(self.run_id, sample_id)
        state['output_dir'] = str(root)
        paper = self.storage.paper_foundation(self.run_id, sample_id)
        if paper is not None:
            self._progress(self.runtime, 'paper_checkpoint_reused', iteration=task['number'])
            return state, paper
        sample = root.parent
        if any((sample / name).exists() for name in ('preparation', 'attempts', 'family_assignment.json')):
            raise ValueError('Task paper foundation missing from existing sample history')
        if self.paper_cache_run_id:
            from src.workflow.paper_cache import copy_paper_cache
            try:
                state.update(copy_paper_cache(self.storage, self.paper_cache_run_id, self.run_id,
                    identity, settings, source_sample_id=self.paper_cache_sample_id, target_sample_id=sample_id))
            except (ValueError, OSError, KeyError, TypeError) as exc:
                _atomic_json(root / 'failure.json', {
                    'stage': 'paper_cache', 'error_type': type(exc).__name__, 'error': str(exc)})
                self._progress_error(self.runtime, 'paper_cache', exc)
                return state, None
            self._progress(self.runtime, 'paper_cache_reused', source_run_id=self.paper_cache_run_id,
                           source_sample_id=self.paper_cache_sample_id, iteration=task['number'])
        elif paper_ready:
            from src.workflow.content_contracts import paper_fields
            state.update(paper_fields(original))
        else:
            state = self._run_nodes(state, self.paper_nodes, stage='paper_foundation')
        if state.get('_joint_interrupted'):
            return state, None
        if state.get('errors') or (not (state.get('structured_sections') or {}).get('paper_sections') if self.editorial_default else
                not state.get('source_document') if self.source_default else
                not (state.get('evidence_bank') or {}).get('items')):
            _atomic_json(root / 'failure.json', {
                'errors': state.get('errors') or ['No original paper foundation available'],
                'failure': state.get('attempt_failure_report')})
            return state, None
        self.storage.save_paper_foundation(self.run_id, state, sample_id)
        return state, self.storage.paper_foundation(self.run_id, sample_id)

    def _fresh_state(self, original, fields):
        from src.state.poster_state import create_state
        state = create_state(original['pdf_path'], width=original['poster_width'], height=original['poster_height'],
            logo_path=original.get('logo_path', ''), aff_logo_path=original.get('aff_logo_path'),
            poster_name=original['poster_name'], url=original.get('url', ''))
        if original.get('task_input_digest'):
            state['task_input_digest'] = original['task_input_digest']
        for key in ('text_model', 'vision_model', 'tokens', 'timing_metrics'):
            state[key] = original[key]
        state.update(deepcopy(fields))
        state['generation_route'], state['critic_config'] = 'optimization_family', deepcopy(self.config)
        return state

    def _preparation_failed(self, state, task):
        result = {'run_id': self.run_id, 'sample_id': task['sample_id'], 'status': 'preparation_failed',
            'poster_id': None, 'candidate_id': None, 'attempt_id': None,
            'layout_family': (state.get('sample_family') or {}).get('family'),
            'seed': task['seed'], 'score': None, 'scoring_profile': self.config['rubric_version'],
            'generation_rubrics': None, 'grouping': 'unclassified', 'dataset': DATASET,
            'preparation_policy_version': PREPARATION_VERSION, 'generation_policy_version': GENERATOR_VERSION,
            'paper_foundation_digest': state['paper_foundation_digest'], 'retry_count': 0,
            'task_entry_policy': TASK_ENTRY_VERSION, 'task_input_digest': state.get('task_input_digest'),
            'failure': state.get('sample_failure') or state.get('attempt_failure_report') or {'errors': state.get('errors')}}
        self.storage.finalize(self.run_id, task['sample_id'], result)
        self._progress(self.runtime, 'sample_saved', result=result)

    def _sample(self, original, foundation, task, profile, policy):
        from src.layout.design_content import DESIGN_POLICY_VERSION
        from src.layout.editorial import EDITORIAL_POLICY_VERSION
        from src.layout.presentation_policy import PRESENTATION_POLICY_VERSION
        from src.layout.repair_budget import budget_usage
        sample_id = task['sample_id']
        from src.workflow.sample_curation import SampleCuration
        self._curation = SampleCuration(self.storage, self.run_id, sample_id)
        state = self._fresh_state(original, foundation)
        attempt = self.storage.begin_attempt(self.run_id, sample_id)
        family, selection = task['family'], (foundation.get('sample_family') or {}).get('selection', {})
        retry = 0
        visual_used = 0
        revision = 0
        state['sample_edit_budget_dir'] = str(self.storage.sample_path(self.run_id, sample_id))
        # One family for this task, including after interruption. No family fishing.
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
            'curation_revision': revision,
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
        from src.workflow.editorial_contract import permits_layout_defects
        advisory=permits_layout_defects(state)
        if state.get('attempt_failure_report') or (state.get('errors') and (advisory or not state.get('layout_preflight_failed'))):
            self._finalize(state, task, 'generation_failed', retry)
            return state, bool(state.get('fatal_generation_error'))
        if state.get('layout_preflight_failed') and not advisory:
            self._finalize(state, task, 'fit_failed', 0)
            return state, False
        try:
            require_rendered_candidate(state, candidate_id, Path(state['output_dir']))
        except GenerationFailure as exc:
            capture_failure(state, exc, agent='renderer', phase='render_readiness')
            self._finalize(state, task, 'generation_failed', retry)
            return state, True
        self._progress(self.runtime, 'stage_start', stage='critic', iteration=task['number'])
        started = time.perf_counter()
        try:
            state = self.critic(state)
        except Exception as exc:
            capture_failure(state, exc, agent='critic', phase='evaluation')
            state['critic_report'] = {'evaluation_status': 'failed', 'overall_score': None,
                                     'error_type': type(exc).__name__, 'reason': str(exc)}
        finally:
            self._record_timing(state, 'critic', time.perf_counter() - started, task['number'])
        if self.control.force_stop_requested:
            self.storage.save_attempt(state, 'abandoned', 'force_stop')
            return state, False
        report = state.get('critic_report') or {}
        complete = complete_score(report)
        self._progress(self.runtime, 'stage_done', stage='critic', iteration=task['number'],
                       elapsed=time.perf_counter() - started,
                       outcome='completed' if complete else 'evaluation_failed',
                       detail=f"score {report.get('overall_score')}" if complete else
                       (report.get('reason') or report.get('rejection_summary') or '无完整评分，详见评价诊断'))
        self._finalize(state, task, 'scored' if complete else 'evaluation_failed', retry)
        return state, False

    def _finalize(self, state, task, status, retry):
        self._progress(self.runtime, 'stage_start', stage='publish', iteration=task['number'])
        from src.workflow.content_contracts import module_provenance
        state['module_provenance'] = module_provenance(
            state.get('optimized_story_board') or state.get('story_board') or {}, state)
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
                  'grouping': 'unclassified', 'dataset': DATASET, 'retry_count': retry,
                  'preparation_policy_version': PREPARATION_VERSION, 'generation_policy_version': GENERATOR_VERSION,
                  'paper_foundation_digest': state.get('paper_foundation_digest'),
                  'sample_science_digest': state.get('sample_science_digest'),
                  'task_entry_policy': TASK_ENTRY_VERSION, 'task_input_digest': state.get('task_input_digest')}
        if rendered:
            result['grouping'] = poster_group(result, report)
            result.update(self.storage.poster_paper(result), poster_collection=self.storage.poster_collection)
        self.storage.save_attempt(state, status)
        sample_path = self.storage.sample_path(self.run_id, task['sample_id'])
        if rendered:
            from src.workflow.exploration_store import DIAGNOSTIC_FIELDS
            fields = (*DIAGNOSTIC_FIELDS, 'current_candidate', 'poster_width', 'poster_height',
                      'critic_report', 'poster_name')
            if self.editorial_default:
                from src.workflow.editorial_contract import PAPER_KEYS
                fields = (*fields, *PAPER_KEYS, 'pdf_path', 'logo_path', 'aff_logo_path',
                          'sample_edit_budget_dir', 'generation_route', 'draft_layout_mode')
            payload = {'state': {key: deepcopy(state.get(key)) for key in fields},
                       'artifact_hashes': {kind: file_hash(candidate[f'{kind}_path'])
                                           for kind in ('pptx', 'png')}}
            _atomic_json(sample_path / 'final_output_snapshot.json', {'payload': payload, 'digest': digest(payload)})
        _atomic_json(sample_path / 'pending_result.json', result)
        poster_directory = self.storage.publish_poster(state, result) if rendered else None
        self.storage.finalize(self.run_id, task['sample_id'], result)
        self._progress(self.runtime, 'sample_saved', result=result,
                       poster_directory=str(poster_directory.resolve()) if poster_directory is not None else None)

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
        total = len(nodes)
        for index, node in enumerate(nodes, 1):
            name = self._timing_component(node)
            self._progress(loop_state, "stage_start", stage=name,
                           stage_index=index, stage_total=total,
                           iteration=iteration or None)
            started = time.perf_counter()
            try:
                if self._curation is not None and name == 'curator' and stage in {'design', 'curation_repair'}:
                    state = self._curation.run(state, node)
                    if (state.get('curation_report') or {}).get('status') == 'reused':
                        self._progress(loop_state, 'curation_reused', revision=state['curation_report']['revision'])
                elif self._curation is not None and name == 'color_agent' and stage == 'design':
                    state = self._curation.run_color(state, node)
                else:
                    state = node(state)
            except Exception as exc:
                from src.workflow.joint_preparation import JointContentFailure
                from src.workflow.source_document import SourceOutputError, SourceInterrupted
                from src.workflow.editorial_contract import EditorialOutputError, EditorialInterrupted
                if isinstance(exc, (SourceInterrupted, EditorialInterrupted)) and self.control.force_stop_requested:
                    state['_joint_interrupted'] = True
                    return state
                state['fatal_generation_error'] = not isinstance(exc, (JointContentFailure, SourceOutputError, EditorialOutputError))
                if isinstance(exc, (SourceOutputError, EditorialOutputError)):
                    state['sample_failure'] = {'kind': 'source_output_invalid', 'reason': str(exc)}
                from utils.model_requests import SampleRequestFailure
                if (self.source_default or self.editorial_default) and isinstance(exc, SampleRequestFailure):
                    from src.workflow.sample_errors import record_sample_error
                    state['fatal_generation_error'] = False
                    record_sample_error(state, exc, 'source_model_request_failed')
                if stage != "paper_foundation":
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
                from src.workflow.editorial_contract import permits_layout_defects
                blocking_preflight=state.get('layout_preflight_failed') and not permits_layout_defects(state)
                if not state.get('sample_failure') and not blocking_preflight:
                    state['fatal_generation_error'] = True
                if stage != "paper_foundation" and not blocking_preflight:
                    from src.workflow.generation_failure import GenerationFailure, capture_failure
                    capture_failure(state, GenerationFailure(str(state["errors"][-1])),
                                    agent=name, phase=name)
                log_agent_warning("loop_controller", f"{stage} reported errors; candidate generation stopped")
                self._progress(loop_state, "error", stage=name,
                               error_type="AgentError", message=str(state["errors"][-1]),
                               iteration=iteration or None)
                break
            detail, outcome = None, 'completed'
            if name == 'joint_preparation' and state.get('editorial_fit'):
                fit = state['editorial_fit']
                outcome = fit.get('status', 'unavailable')
                detail = {'target_met': '容量目标已达到', 'no_useful_edit': '容量编辑无实际改动',
                          'repair_limit_reached': '容量编辑轮次已用尽'}.get(fit.get('completion_reason'), fit.get('completion_reason'))
            elif name == 'layout_preflight' and state.get('layout_preflight_failed'):
                outcome, detail = 'layout_defects', '按既有策略保留缺陷并继续导出'
            elif name == 'render_fit_audit':
                outcome = (state.get('render_fit_report') or {}).get('status', 'unavailable')
                detail = f"RenderFit={outcome}"
            self._progress(loop_state, "stage_done", stage=name, detail=detail, outcome=outcome,
                           elapsed=time.perf_counter() - started, iteration=iteration or None)
            if stage == "paper_foundation" and self.control.stop_requested:
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
        if (pending_completion and stage == 'design' and needs_rollback
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
