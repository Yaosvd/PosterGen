"""Critical paper evidence survives shared selection and actual artifact gates."""

from copy import deepcopy
import json
from types import SimpleNamespace

from PIL import Image
import pytest
from pptx import Presentation
from pptx.util import Inches

from src.config.critic_config import load_critic_config
from src.critic.base import CriticContext
from src.critic.quality import VisualAssetEvaluator
from src.layout.visual_requirements import (
    attach_required, board_audit, build_contract, required_ids, seal, validate_contract,
)
from src.layout.render_visuals import admission_audit, artifact_identity, audit_rendered_visuals
from src.layout.feasibility import _content_options, fit_family_layout, LayoutFeasibilityError
from src.layout.families import FAMILIES, LayoutFamily, LayoutFamilyRegistry
from src.layout.family_contract import FamilyContract
from src.workflow.campaign import CampaignManager
from src.agents.revision_contract import authorize_deletions
from test_layout_exploration import _MeasuredAgent, _board
from test_family_design_policy import state_for


def sample(tmp_path, count=2):
    board = _board()
    for section in board['spatial_content_plan']['sections']:
        section['visual_assets'] = []
    state = state_for(board)
    state['evidence_bank'] = {'items': [{'evidence_id': f'ev{i}'} for i in range(count)]}
    state['images'] = {}
    for i in range(count):
        path = tmp_path / f'figure_{i+1}.png'
        Image.new('RGB', (900, 450), ('red', 'blue', 'green')[i % 3]).save(path)
        state['images'][str(i+1)] = {'path': str(path), 'caption': f'Paper evidence {i+1}', 'aspect': 2}
    review = {'items': [{'visual_id': f'figure_{i+1}', 'disposition': 'required',
                         'reason': 'main_result' if i else 'core_method',
                         'evidence_ids': [f'ev{i}'], 'source_section_ids': [f's{i}']}
                        for i in range(count)]}
    state['visual_requirements'] = build_contract(state, review)
    board, unresolved = attach_required(board, state, state['visual_requirements'])
    assert not unresolved
    state['story_board'] = board
    state['critic_config'] = load_critic_config()
    return state, board


def test_requirements_account_for_all_assets_and_do_not_use_quota(tmp_path):
    state, board = sample(tmp_path)
    assert required_ids(state) == {'figure_1', 'figure_2'}
    assert not validate_contract(state['visual_requirements'], state)
    unreviewed = build_contract(state)
    assert unreviewed['status'] == 'unresolved'
    state['images'] = {}
    state['visual_requirements'] = build_contract(state)
    state['story_board'] = {'spatial_content_plan': {'sections': []}}
    result = VisualAssetEvaluator().evaluate(CriticContext(state, load_critic_config()))
    assert result.passed and result.scores == {}
    assert result.metadata['submetrics']['visual_asset_presentation'] is None
    from src.critic.engine import PosterCritic
    from src.critic.base import EvaluationResult
    config = load_critic_config()
    other = [EvaluationResult(name, 'test', False, True, scores={'aesthetics': 96})
             for name in config['dimension_sources']['aesthetics'] if name != 'visual_assets']
    critic = PosterCritic(config=config, evaluators=[])
    reviewed = critic._build_report(state, [result, *other])
    missing = critic._build_report(state, other)
    assert reviewed['dimension_scores']['aesthetics'] == 96
    assert missing['dimension_scores']['aesthetics'] < 96


def test_key_and_planner_are_required_floors(tmp_path):
    state, _ = sample(tmp_path)
    items = state['visual_requirements']['items']
    state['narrative_plan']['visual_requirements'] = {'items': [items[0]]}
    state['classified_visuals'] = {'key_visual': 'figure_2'}
    optional = {'items': [{**i, 'disposition': 'optional', 'reason': 'supporting'} for i in items]}
    contract = build_contract(state, optional)
    assert set(contract['required_visual_ids']) == {'figure_1', 'figure_2'}
    assert not validate_contract(contract, state)
    contract['items'][0].update(disposition='optional', reason='supporting')
    contract['required_visual_ids'] = ['figure_2']
    assert 'PLANNER_REQUIRED_VISUAL_DOWNGRADED' in {i['code'] for i in validate_contract(seal(contract), state)}


@pytest.mark.parametrize('mutation', ['foreign', 'missing', 'corrupt', 'caption', 'unknown_key'])
def test_changed_or_unreadable_source_fails_closed(tmp_path, mutation):
    state, board = sample(tmp_path)
    path = tmp_path / 'figure_1.png'
    if mutation == 'foreign':
        state['verified_claims']['claims'][0]['text'] = 'Other source'
    elif mutation == 'missing':
        path.unlink()
    elif mutation == 'corrupt':
        path.write_bytes(b'not an image')
    elif mutation == 'caption':
        state['images']['1']['caption'] = 'Different evidence'
    else:
        state['classified_visuals'] = {'key_visual': 'figure_99'}
    assert validate_contract(state['visual_requirements'], state)
    assert not board_audit(state, board)['passed']


def test_local_owner_only_and_foreign_board_cannot_override(tmp_path):
    state, board = sample(tmp_path)
    other = deepcopy(board)
    for section in other['spatial_content_plan']['sections']:
        section['visual_assets'] = []
    state['visual_requirements']['items'][0]['source_section_ids'] = []
    state['visual_requirements'] = seal(state['visual_requirements'])
    _, unresolved = attach_required(other, state, state['visual_requirements'])
    assert unresolved[0]['visual_id'] == 'figure_1'
    other['visual_requirements'] = build_contract(state)
    assert 'VISUAL_REQUIREMENT_BRANCH_MISMATCH' in {i['code'] for i in board_audit(state, other)['issues']}


def test_required_subsets_keep_multiple_visuals_and_can_drop_optional(tmp_path):
    state, board = sample(tmp_path, 3)
    contract = deepcopy(state['visual_requirements'])
    contract['items'][2].update(disposition='optional', reason='supporting')
    contract['required_visual_ids'] = ['figure_1', 'figure_2']
    state['visual_requirements'] = seal(contract)
    section = deepcopy(board['spatial_content_plan']['sections'][0])
    section['visual_assets'] = [{'visual_id': f'figure_{i}'} for i in range(1, 4)]
    options = _content_options(_MeasuredAgent(), section, zone_width=12, zone_height=20, state=state)
    sets = [{a['visual_id'] for a in o['section']['visual_assets']} for o in options]
    assert {'figure_1', 'figure_2'} in sets
    assert all({'figure_1', 'figure_2'} <= ids for ids in sets)


class VisualMeasuredAgent(_MeasuredAgent):
    def _create_section_elements(self, section, x, y, width, state, available_height):
        result = super()._create_section_elements(section, x, y, width, state, available_height)
        for i, asset in enumerate(section.get('visual_assets') or []):
            result.append({'type': 'visual', 'id': asset['visual_id'], 'visual_id': asset['visual_id'],
                           'x': x, 'y': y+i*2, 'width': 4, 'height': 2})
        return result


@pytest.mark.parametrize('family', FAMILIES, ids=lambda f: f.family_id)
def test_all_families_keep_required_visuals(tmp_path, family):
    state, board = sample(tmp_path)
    config = load_critic_config()
    config['composition_refinement']['enabled'] = False
    fitted, _, report = fit_family_layout(VisualMeasuredAgent(), board, state, family.family_id, config=config)
    assert report['status'] == 'feasible'
    assert board_audit(state, fitted)['passed']


def test_future_registration_uses_same_requirement_contract(tmp_path, monkeypatch):
    family = LayoutFamily('future_visual_tracks', 'Future', 'Test', FAMILIES[2].zones, ('general',),
                          contract=FamilyContract(reading='columns', allow_module_grouping=True))
    original = LayoutFamilyRegistry.__init__
    monkeypatch.setattr(LayoutFamilyRegistry, '__init__', lambda self, families=None:
                        original(self, (*FAMILIES, family) if families is None else families))
    state, board = sample(tmp_path)
    fitted, _, _ = fit_family_layout(VisualMeasuredAgent(), board, state, family.family_id)
    assert board_audit(state, fitted)['passed']


def test_unresolved_requirements_stop_before_geometry(tmp_path):
    state, board = sample(tmp_path)
    state['visual_requirements'] = build_contract(state)
    with pytest.raises(LayoutFeasibilityError) as caught:
        fit_family_layout(_MeasuredAgent(), board, state, FAMILIES[0].family_id)
    assert caught.value.report['failure_scope'] == 'shared_content'
    assert caught.value.report['trial_count'] == 0


def test_revision_cannot_delete_or_replace_critical_evidence(tmp_path):
    state, board = sample(tmp_path)
    operations = [{'operation': op, 'visual_id': 'figure_1', 'section_id': 's0'}
                  for op in ('remove_visual', 'replace_visual', 'move_visual')]
    approved, rejected = authorize_deletions(operations, state, board)
    assert [o['operation'] for o in approved] == ['move_visual']
    assert len(rejected) == 2


def presentation(state, board, tmp_path):
    pptx = tmp_path / 'poster.pptx'
    png = tmp_path / 'poster.png'
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(54), Inches(36)
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    layout, boxes = [], []
    for i, vid in enumerate(sorted(required_ids(state))):
        x, y, w, h = 1+i*6, 8, 4, 2
        picture = slide.shapes.add_picture(state['images'][str(i+1)]['path'], Inches(x), Inches(y), Inches(w), Inches(h))
        picture.name = 'PosterGenVisual:' + vid
        layout.append({'type': 'visual', 'visual_id': vid, 'x': x, 'y': y, 'width': w, 'height': h})
        boxes.append({'bbox': (x*72, y*72, (x+w)*72, (y+h)*72)})
    deck.save(pptx)
    Image.new('RGB', (540, 360), 'white').save(png)
    state.update(styled_layout=layout, current_candidate={'candidate_id': 'own', 'pptx_path': str(pptx), 'png_path': str(png)})
    state['render_diagnostics'] = {'artifact_identity': artifact_identity(state)}
    return SimpleNamespace(get_image_info=lambda: boxes), pptx, png


def test_actual_embedded_sources_and_pdf_positions_are_required(tmp_path):
    state, board = sample(tmp_path)
    page, _, _ = presentation(state, board, tmp_path)
    report = audit_rendered_visuals(state, page)
    assert report['passed'], report
    state['render_fit_report'] = {'visual_audit': report}
    assert admission_audit(state)['passed']
    result = VisualAssetEvaluator().evaluate(CriticContext(state, load_critic_config()))
    assert result.passed
    assert not audit_rendered_visuals(state)['passed']
    page.get_image_info = lambda: []
    assert not audit_rendered_visuals(state, page)['passed']


@pytest.mark.parametrize('mutation', ['crop', 'tiny', 'substitute', 'logo', 'duplicate', 'png_missing', 'stale'])
def test_bad_actual_artifacts_cannot_pass_high_score(tmp_path, mutation):
    state, board = sample(tmp_path)
    page, pptx, png = presentation(state, board, tmp_path)
    original = audit_rendered_visuals(state, page)
    state['render_fit_report'] = {'visual_audit': original}
    if mutation == 'png_missing':
        png.unlink()
    elif mutation == 'stale':
        state['current_candidate']['candidate_id'] = 'another attempt'
    else:
        deck = Presentation(pptx)
        first = deck.slides[0].shapes[0]
        if mutation == 'crop':
            first.crop_left = 0.1
        elif mutation == 'tiny':
            first.width = Inches(0.2)
        elif mutation == 'logo':
            first.name = 'Conference Logo'
        elif mutation == 'duplicate':
            shape = deck.slides[0].shapes.add_picture(state['images']['1']['path'], Inches(1), Inches(8), Inches(4), Inches(2))
            shape.name = first.name
        else:
            from pptx.oxml.ns import qn
            other = deck.slides[0].shapes[1]
            first._element.blipFill.blip.set(qn('r:embed'), other._element.blipFill.blip.get(qn('r:embed')))
        deck.save(pptx)
        state['render_diagnostics']['artifact_identity'] = artifact_identity(state)
        assert not audit_rendered_visuals(state, page)['passed']
    assert not admission_audit(state)['passed']
    result = VisualAssetEvaluator().evaluate(CriticContext(state, load_critic_config()))
    assert not result.passed and any(i['severity'] == 'critical' for i in result.issues)


def test_no_visual_i11_shape_is_blocked_instead_of_scoring_100(tmp_path):
    state, board = sample(tmp_path)
    for section in board['spatial_content_plan']['sections']:
        section['visual_assets'] = []
    result = VisualAssetEvaluator().evaluate(CriticContext(state, load_critic_config()))
    assert not result.passed and result.scores['aesthetics'] == 0
    state['generation_route'] = 'standalone_classic'
    assert VisualAssetEvaluator().evaluate(CriticContext(state, load_critic_config())).passed


def test_only_committed_campaign_requirements_are_recovered(tmp_path):
    state, _ = sample(tmp_path)
    handle = SimpleNamespace(path=tmp_path / 'campaign')
    manager = CampaignManager(tmp_path / 'store', load_critic_config())
    attempt = handle.path / 'iterations' / '000001' / 'attempts' / 'one'
    attempt.mkdir(parents=True)
    snapshot = attempt / 'state_snapshot.json'
    snapshot.write_text(json.dumps({'fields': {'visual_requirements': state['visual_requirements']}}))
    assert manager.committed_visual_requirements(handle) is None
    (attempt.parent.parent / 'COMPLETED.json').write_text(json.dumps({'attempt_id': 'one'}))
    assert manager.committed_visual_requirements(handle, state) == state['visual_requirements']
    data = json.loads(snapshot.read_text())
    data['fields']['visual_requirements']['required_visual_ids'] = []
    snapshot.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='corrupt'):
        manager.committed_visual_requirements(handle)
    assert 'visual_requirements' not in CampaignManager.LINEAGE_SNAPSHOT_FIELDS


@pytest.mark.parametrize('status', ['readable', 'unreadable', 'missing', 'uncertain', None])
def test_existing_vision_call_must_confirm_required_readability(tmp_path, monkeypatch, status):
    from src.critic.visual import VisualCriticEvaluator
    from src.state.poster_state import ModelConfig, TokenUsage
    state, board = sample(tmp_path)
    presentation(state, board, tmp_path)
    state.update(vision_model=ModelConfig('fake', 'fake'), tokens=TokenUsage())
    payload = {'scores': {name: 99 for name in VisualCriticEvaluator._DIMENSIONS}, 'issues': [],
               'critical_visual_assessments': [] if status is None else
               [{'visual_id': vid, 'status': status} for vid in sorted(required_ids(state))]}
    calls = []
    class FakeAgent:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, message):
            calls.append(message)
            return SimpleNamespace(content=json.dumps(payload), input_tokens=0, output_tokens=0)
    monkeypatch.setattr('src.critic.visual.LangGraphAgent', FakeAgent)
    result = VisualCriticEvaluator().evaluate(CriticContext(state, load_critic_config()))
    assert len(calls) == 1
    assert result.passed == (status == 'readable'), result


def test_unavailable_pdf_cannot_certify_required_visuals(tmp_path, monkeypatch):
    from src.layout.render_fit import audit_rendered_text
    state, board = sample(tmp_path)
    presentation(state, board, tmp_path)
    monkeypatch.setattr('src.layout.render_fit.shutil.which', lambda name: None)
    report = audit_rendered_text(state)
    assert not report['passed'] and report['status'] == 'failed'
    assert not report['visual_audit']['passed']


def test_locked_modes_do_not_restore_missing_visuals_silently(tmp_path):
    from src.agents.layout_preflight import layout_preflight_node
    state, board = sample(tmp_path)
    for mode in ('validate', 'improve'):
        trial = deepcopy(state)
        trial['iteration_context'] = {'portfolio_mode': mode}
        trial['improve_safe_fallback'] = mode == 'improve'
        trial['styled_layout'] = []
        trial['errors'] = []
        before = deepcopy(trial['story_board'])
        layout_preflight_node(trial, persist=False)
        assert trial['layout_preflight_failed']
        assert trial['story_board'] == before


@pytest.mark.parametrize('stop', [False, True])
def test_shared_visual_failure_never_retries_another_family_or_calls_critic(tmp_path, stop):
    from test_auxiliary_function_boundary import make_loop
    from test_campaign_resume import _state
    calls = []
    def node(state):
        calls.append(state['iteration_context']['layout_family'])
        if stop:
            loop.control.request_stop()
        state.update(layout_preflight_failed=True, errors=['critical visual review unresolved'],
            layout_feasibility_report={'status': 'infeasible', 'failure_scope': 'shared_content',
                'reason_code': 'VISUAL_REQUIREMENTS_UNRESOLVED', 'failure_stage': 'visual_requirements', 'trial_count': 0})
        return state
    def critic(state):
        pytest.fail('Unresolved paper visuals cannot reach Critic')
    loop = make_loop(tmp_path, node, critic, batch_mode='explore')
    result = loop.run(_state(tmp_path / 'run'), foundation_ready=True)['loop_state']
    assert len(calls) == 1
    assert result['status'] == ('PAUSED' if stop else 'FAILED_REQUIRES_USER')
    if not stop:
        assert result['stop_reason'] == 'shared_visual_requirements_unresolved'
    assert result['batch']['completed_iterations'] == 0
    assert result['accepted_count'] == result['rejected_count'] == result['template_count'] == 0
    root = loop.storage.root / 'campaigns' / result['campaign_id']
    assert not list(root.glob('iterations/*/COMPLETED.json'))
    assert not list(root.glob('iterations/*/attempts/*/model_repair_budget.json'))
    assert not (loop.storage.root / 'design_memory/rejection_memory.jsonl').exists()


def test_later_opaque_rectangle_cannot_hide_required_visual(tmp_path):
    state, board = sample(tmp_path)
    page, _, _ = presentation(state, board, tmp_path)
    boxes = page.get_image_info()
    page.get_bboxlog = lambda: [('fill-image', b['bbox']) for b in boxes]
    page.get_drawings = lambda: [{'seqno': 3, 'fill': (1, 1, 1), 'fill_opacity': 1,
                                 'items': [('re', boxes[0]['bbox'], 1)]}]
    report = audit_rendered_visuals(state, page)
    assert 'REQUIRED_VISUAL_COVERED' in {i['code'] for i in report['issues']}


def test_required_raster_size_uses_source_aspect_and_existing_dpi_floor(tmp_path):
    from src.agents.layout_agent import LayoutAgent
    state, _ = sample(tmp_path)
    # Width 30 would render only 30 DPI. Cap to 12.5 inches at 72 DPI.
    w, h, _ = LayoutAgent()._calculate_visual_height('figure_1', 30, state, 100)
    assert w == pytest.approx(12.5)
    assert h == pytest.approx(6.25)
    from src.agents.renderer import Renderer
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    renderer = Renderer()
    renderer._add_visual_with_aspect_ratio(slide, 'figure_1', Inches(1), Inches(1), Inches(4), Inches(2), state)
    assert slide.shapes[0].name == 'PosterGenVisual:figure_1'
    state['generation_route'] = 'standalone_classic'
    renderer._add_visual_with_aspect_ratio(slide, 'figure_1', Inches(1), Inches(4), Inches(4), Inches(2), state)
    assert not slide.shapes[1].name.startswith('PosterGenVisual:')


def test_critical_duplicate_can_remove_extra_but_never_last_copy(tmp_path):
    state, board = sample(tmp_path)
    board['spatial_content_plan']['sections'][1]['visual_assets'].append({'visual_id': 'figure_1'})
    state['critic_report'] = {'rubric_version': 'test', 'issues': [{
        'issue_id': 'VISUAL-ASSET-DUPLICATED', 'location': {'section_id': 's0', 'visual_id': 'figure_1'},
        'allowed_operations': ['remove_visual'], 'evidence': {'visual_ids': ['figure_1']}}]}
    operations = [{'operation': 'remove_visual', 'section_id': sid, 'visual_id': 'figure_1',
                   'critic_issue_ids': ['VISUAL-ASSET-DUPLICATED'], 'reason': 'duplicate'} for sid in ('s0', 's1')]
    approved, rejected = authorize_deletions(operations, state, board)
    assert len(approved) == len(rejected) == 1
