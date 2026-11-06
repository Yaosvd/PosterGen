"""Measured same-zone height transfers, immutable prose and durable delivery."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from test_editorial_generation import state_for, draft_for, install
from src.layout.editorial_layout import measure, fit
from src.layout.editorial_space import module_height_candidates, coordinate_module_heights
from src.layout.editorial_composition import initial_fit, assert_composition
from src.layout.measurement_context import measurement_scope
from src.layout.families import LayoutFamilyRegistry
from src.workflow import editorial_pipeline as pipeline
from src.workflow.editorial_contract import assert_editorial_ready, EditorialInterrupted


INITIAL_MODULES = [{'module_id': 'm1',
  'title': 'Why Equivariance Fails',
  'zone_id': 'narrative_rail',
  'importance': 2,
  'space_weight': 1,
  'presentation_style': 'plain',
  'reader_question': "Why aren't existing scale-equivariant CNNs truly scale-equivariant?",
  'entries': [{'item_id': 'm1_prob',
               'text': 'When an object is photographed from different distances, its image size '
                       "changes; a scale-equivariant network's features should transform "
                       'predictably under such resizing, which underpins segmentation and '
                       'multi-resolution recognition.',
               'display_label': '',
               'parent_item_id': ''},
              {'item_id': 'm1_gap',
               'text': 'Recent equivariant CNNs (SESN, DISCO, DSS, SS-CNN, SI-ConvNet) share '
                       'weights across a set of scaled kernels, but they derive down-scaling in '
                       'the continuous domain and discretize afterwards, so no anti-aliasing '
                       'filter is applied.',
               'display_label': '',
               'parent_item_id': 'm1_prob'},
              {'item_id': 'm1_alias',
               'text': 'By the Nyquist theorem, downsampling a discrete signal without '
                       'anti-aliasing lets high-frequency content alias into lower frequencies '
                       '(the wagon-wheel effect), so these networks retain a non-negligible '
                       'equivariance error in practice.',
               'display_label': '',
               'parent_item_id': 'm1_gap'}],
  'visual_ids': ['figure_1'],
  'visual_rationale': 'Figure 1 contrasts a regular CNN whose features break under resizing with '
                      'our scale-equivariant model, making the failure mode concrete before the '
                      'fix is introduced.'},
 {'module_id': 'm2',
  'title': 'Ideal Downsampling',
  'zone_id': 'narrative_rail',
  'importance': 2,
  'space_weight': 1,
  'presentation_style': 'plain',
  'reader_question': 'What is the correct discrete-domain formulation of down-scaling?',
  'entries': [{'item_id': 'm2_def',
               'text': 'We define down-scaling directly in the discrete domain as ideal '
                       'downsampling: apply an ideal low-pass anti-aliasing filter h, whose DFT is '
                       '1 for |k| ≤ N/(2R) and 0 otherwise, then subsample: D_R(x) = Sub_R(h ⊛ x).',
               'display_label': '',
               'parent_item_id': ''},
              {'item_id': 'm2_spectrum',
               'text': 'In the Fourier domain this operation is simply a truncation of the '
                       'spectrum, F(D_R(x)) = F(x)[−N/2R : N/2R], which is exactly what makes '
                       'exact discrete analysis possible.',
               'display_label': '',
               'parent_item_id': 'm2_def'}],
  'visual_ids': ['figure_2'],
  'visual_rationale': 'Figure 2a depicts the ideal low-pass filter that zeros high frequencies — '
                      'the core of the anti-aliased down-scaling operator.'},
 {'module_id': 'm3',
  'title': 'Frequency-Causality Design Rule',
  'zone_id': 'evidence_field',
  'importance': 1,
  'space_weight': 3,
  'presentation_style': 'plain',
  'reader_question': 'What principle guarantees exact scale-equivariance, and how do the modules '
                     'realize it?',
  'entries': [{'item_id': 'm3_claim',
               'text': 'Claim 1: a network g is scale-equivariant under D_R if each output '
                       'frequency k is computed only from input frequencies in the band X[−k:k] — '
                       'lower-frequency outputs never depend on higher-frequency inputs. Since '
                       'ideal downsampling truncates the spectrum, such a network satisfies '
                       'g(D_R(x)) = D_R(g(x)) exactly, giving zero equivariance error.',
               'display_label': '',
               'parent_item_id': ''},
              {'item_id': 'm3_local',
               'text': "Spatially local Fourier layer: the kernel's DFT is parameterized through a "
                       'localized kernel K^l of receptive field l, so the layer computes Y[k] = '
                       'K[k] ⊙ X[k] per frequency — local in space yet exactly equivariant (Claim '
                       '2).',
               'display_label': '',
               'parent_item_id': 'm3_claim'},
              {'item_id': 'm3_nl',
               'text': 'Scale-equivariant non-linearity: for each frequency k, apply ReLU to the '
                       'inverse DFT of the low-frequency band up to |k| and read off the k-th '
                       'coefficient; coefficients between consecutive enforced resolutions share '
                       'one Fourier transform pair, keeping the cost at O(|A|N log N + KN) per '
                       'layer.',
               'display_label': '',
               'parent_item_id': 'm3_claim'},
              {'item_id': 'm3_pool',
               'text': 'Scale-equivariant pooling: pool the band-limited inverse DFT up to w|k| '
                       'and transform back, so pooling is exactly equivariant at every w-th '
                       'resolution (inputs whose size is not a multiple of w are truncated).',
               'display_label': '',
               'parent_item_id': 'm3_claim'}],
  'visual_ids': [],
  'visual_rationale': 'Figure 2b shows the band-diagonal structure of Claim 1 for a linear map — '
                      'gray regions are the zero couplings that enforce frequency-causality — so '
                      'the figure belongs with the design rule it illustrates.'},
 {'module_id': 'm4',
  'title': 'Scale-Consistent Classifier',
  'zone_id': 'evidence_field',
  'importance': 2,
  'space_weight': 2,
  'presentation_style': 'plain',
  'reader_question': 'How are equivariant features turned into predictions across scales?',
  'entries': [{'item_id': 'm4_why',
               'text': 'A truly scale-invariant classifier is undesirable: its accuracy is capped '
                       'by the lowest resolution — in the extreme it could depend on a single mean '
                       'pixel. The right target is scale-consistency: higher-resolution inputs '
                       'should perform better than their down-scaled versions.',
               'display_label': '',
               'parent_item_id': ''},
              {'item_id': 'm4_arch',
               'text': 'The classifier outputs a prediction per scale: features are band-limited '
                       'to [−|k|/2 : |k|/2], zero-padded in the Fourier domain to a fixed size so '
                       'one shared MLP applies at every scale, inverse-transformed, pooled, and '
                       'mapped to per-scale logits; at test time only the full-resolution output '
                       'is used.',
               'display_label': '',
               'parent_item_id': 'm4_why'},
              {'item_id': 'm4_loss',
               'text': 'Training adds a hinge consistency loss to per-scale cross-entropy, '
                       'penalizing the model whenever the loss on a higher-resolution input '
                       'exceeds that of its lower-resolution version, which pushes resolution '
                       'gains into accuracy gains.',
               'display_label': '',
               'parent_item_id': 'm4_arch'}],
  'visual_ids': [],
  'visual_rationale': 'Text-only module; the mechanism is fully described by the per-scale '
                      'pipeline and loss, and all figures/tables are owned by other modules.'}]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('Unexpected model'))
    with measurement_scope():
        yield


def mixed_state(tmp_path, *, initial=False):
    state = state_for(tmp_path, 'asymmetric_two_column')
    image = tmp_path/'figure.png'
    Image.new('RGB', (600, 200), '#335577').save(image)
    state['images'] = {str(i): {'path': str(image), 'aspect': 3, 'caption': 'Method figure'}
                       for i in (1, 2)}
    raw = draft_for(state)
    raw['modules'] = deepcopy(INITIAL_MODULES)
    install(state, raw)
    # A registered, already selected regional geometry; direction stays vertical.
    if not initial:
        state['editorial_zones'][0]['width'] = .39
        state['editorial_zones'][1].update(x=.42, width=.58)
    return state


def without_weights(candidate):
    result = deepcopy(candidate)
    result.pop('candidate_id')
    for module in result['modules']:
        module.pop('space_weight')
    return result


def test_exact_transfer_fixes_overflow_preserving_science_images_direction_and_state(tmp_path):
    state = mixed_state(tmp_path); original = deepcopy(state)
    before = measure(state, state['editorial_candidate'], state['editorial_zones'])
    assert before['report']['modules'][0]['overage_inches'] > 1
    result = coordinate_module_heights(state, state['editorial_candidate'], before)
    assert result['report']['height_allocation']['status'] == 'adopted'
    assert result['report']['total_overflow_inches'] == 0
    assert all(.9 <= m['utilization'] <= 1 for m in result['report']['modules'][:2])
    assert result['report']['composition_whitespace']['empty_body_fraction'] <= before['report']['composition_whitespace']['empty_body_fraction']
    assert without_weights(result['candidate']) == without_weights(state['editorial_candidate'])
    assert result['spec'] == before['spec']
    assert state == original
    for layout in (before['layout'], result['layout']):
        assert {e['body_layout'] for e in layout if e['type'] == 'visual'} == {'image_above_text'}
    # Image growth matters: the upper image grows after receiving height.
    top = lambda r: next(e for e in r['layout'] if e['type']=='visual' and e['section_id']=='m1')
    assert top(result)['height'] > top(before)['height']
    assert top(result)['width']/top(result)['height'] == pytest.approx(3)
    assert len(result['report']['height_allocation']['trials']) <= 3


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_proposals_preserve_all_family_contracts_and_total_height(tmp_path, family):
    state = state_for(tmp_path, family); raw = draft_for(state)
    zone = next((z for z in LayoutFamilyRegistry().get(family).zones if z['capacity'] > 1), None)
    if zone:
        owner = next(m for m in raw['modules'] if m['zone_id'] == zone['zone_id'])
        peer = deepcopy(owner); peer['module_id'] = 'peer';raw['modules'].append(peer)
    install(state, raw); candidate = state['editorial_candidate']
    baseline = measure(state, candidate, state['editorial_zones'])
    if zone:
        rows = [r for r in baseline['report']['modules'] if r['zone_id'] == zone['zone_id']]
        for row, used in zip(rows, (12., 4.)):
            row.update(allocated_height=10., intrinsic_height=used, minimum_intrinsic_height=used,
                       utilization=used/10., overage_inches=max(0, used-10.))
    proposals = module_height_candidates(state, candidate, baseline)
    assert bool(proposals) == bool(zone)
    assert len(proposals) <= 3
    for proposed in proposals:
        assert without_weights(proposed) == without_weights(candidate)
        assert all(1 <= m['space_weight'] <= 3 for m in proposed['modules'])
        for z in baseline['spec']['zones']:
            old = [m for m in candidate['modules'] if m['zone_id'] == z['zone_id']]
            new = [m for m in proposed['modules'] if m['zone_id'] == z['zone_id']]
            if z['zone_id'] != zone['zone_id']:
                assert old == new
            else:
                total = sum(m['space_weight'] for m in new)
                heights = [20*m['space_weight']/total for m in new]
                assert sum(heights) == pytest.approx(20)
                assert heights[0] > 10 and heights[1] >= 4


@pytest.mark.parametrize('condition', ['underfill_only', 'all_overflow', 'ratio_limit'])
def test_no_proposals_when_no_safe_donor_or_legal_share(tmp_path, condition):
    state = mixed_state(tmp_path); c=state['editorial_candidate']
    baseline = measure(state, c, state['editorial_zones'])
    rows=baseline['report']['modules']
    if condition == 'underfill_only':
        for row in rows: row.update(overage_inches=0, utilization=.5)
    elif condition == 'all_overflow':
        for row in rows: row.update(overage_inches=2, utilization=1.2)
    else:
        c['modules'][0]['space_weight']=3
        rows[0].update(allocated_height=30, intrinsic_height=35, minimum_intrinsic_height=35,
                       utilization=35/30, overage_inches=5)
        rows[1].update(allocated_height=10, intrinsic_height=4, minimum_intrinsic_height=4,
                       utilization=.4, overage_inches=0)
    assert module_height_candidates(state,c,baseline) == []


@pytest.mark.parametrize('regression', ['module_overflow_regression', 'underfill_regression',
                                       'preflight_regression', 'whitespace_regression'])
def test_exact_rejection_retains_original_candidate(monkeypatch,tmp_path,regression):
    import src.layout.editorial_layout as layout
    state=mixed_state(tmp_path); c=state['editorial_candidate']
    baseline=measure(state,c,state['editorial_zones'])
    actual=measure
    def bad(*a,**kw):
        result=actual(*a,**kw); r=result['report']
        if regression=='module_overflow_regression':r['modules'][1]['overage_inches']=.2
        elif regression=='underfill_regression':r['total_underfill_inches']=100
        elif regression=='preflight_regression':r['preflight']['passed']=False
        else:r['composition_whitespace']['empty_body_fraction']=1
        return result
    monkeypatch.setattr(layout,'measure',bad)
    result=coordinate_module_heights(state,c,baseline)
    assert result['candidate']==c and result['layout']==baseline['layout']
    assert result['report']['height_allocation']['status']=='no_safe_gain'
    assert all(regression in t['rejection_reasons'] for t in result['report']['height_allocation']['trials'])


def test_first_receipt_replays_coordinated_candidate_without_search(tmp_path):
    state=mixed_state(tmp_path, initial=True); original=deepcopy(state)
    first=initial_fit(state)
    assert first['candidate'] != original['editorial_candidate']
    again=initial_fit(original,fitter=lambda *a:pytest.fail('Repeated initial fit'))
    assert again==first
    pipeline.install(original,again['candidate'])
    compiled=measure(original,original['editorial_candidate'],again['spec']['zones'])
    assert compiled['layout']==again['layout']
    assert_composition(original,layout=compiled['layout'],durable=True)


def response_model(monkeypatch, calls):
    import utils.langgraph_utils as language
    class Model:
        def __init__(self,*a):pass
        def reset(self):pass
        def step(self,message):
            data=json.loads(message.split('\nINPUT:\n',1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
            calls.append(data)
            value={'modules':[], 'remove_module_ids':[], 'module_order':[], 'narrative_flow':'', 'reason':'No further grounded edit.'}
            return SimpleNamespace(content=json.dumps(value),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(language,'LangGraphAgent',Model)


def test_interrupted_request_replays_same_adopted_weights_and_charge(monkeypatch,tmp_path):
    state=mixed_state(tmp_path, initial=True); start=deepcopy(state); calls=[]
    response_model(monkeypatch,calls)
    edit=pipeline.edit
    def interrupted(*a):
        edit(*a)
        raise EditorialInterrupted()
    monkeypatch.setattr(pipeline,'edit',interrupted)
    with pytest.raises(EditorialInterrupted):pipeline.editorial_joint_node(state)
    assert len(calls)==1
    selected=deepcopy(state['editorial_candidate'])
    assert selected != start['editorial_candidate']
    monkeypatch.setattr(pipeline,'edit',edit)
    monkeypatch.setattr(pipeline,'fit',lambda *a:pytest.fail('Recovery bought new search'))
    pipeline.editorial_joint_node(start);pipeline.editorial_compile_node(start)
    assert len(calls)==1 and start['editorial_candidate']==selected
    assert calls[0]['whole_poster']==selected
    assert [h['phase'] for h in start['editorial_history']]==['height_allocation','capacity']
    assert [h['phase'] for h in start['editorial_budget']['charges']]==['capacity']
    assert start['editorial_fit']['completion_reason']=='no_useful_edit'
    assert_editorial_ready(start,compiled=True)


def test_real_render_and_freeze_use_the_adopted_height_weights(monkeypatch,tmp_path):
    import shutil
    from src.agents.font_agent import FontAgent
    from src.agents.renderer import Renderer
    from src.agents.render_fit_audit import render_fit_audit_node
    if not shutil.which('libreoffice'):pytest.skip('LibreOffice not installed')
    state=mixed_state(tmp_path, initial=True); calls=[];response_model(monkeypatch,calls)
    monkeypatch.setattr(FontAgent,'_identify_keywords',lambda *a:{'section_keywords':{}})
    pipeline.editorial_joint_node(state);pipeline.editorial_compile_node(state)
    FontAgent()(state);Renderer()(state);render_fit_audit_node(state)
    assert not state['errors'],state['errors']
    assert len(calls)==1
    assert state['editorial_fit']['height_allocation']['status']=='adopted'
    assert state['render_fit_report']['passed'],state['render_fit_report']
    # Formula-rich right-side text may be unmatched; require both corrected
    # left bodies and every title, without declaring unmatched text valid.
    matched = {r['element_id'] for r in state['render_fit_report']['matched_text_boxes']}
    assert {'m1_text', 'm2_text', 'm1_title', 'm2_title', 'm3_title', 'm4_title'} <= matched
    assert Path(state['current_candidate']['png_path']).is_file()
    assert Path(state['current_candidate']['pptx_path']).is_file()
    assert_editorial_ready(state,compiled=True)
    state['editorial_candidate']['modules'][0]['space_weight']=1
    with pytest.raises(ValueError,match='snapshot'):assert_editorial_ready(state,compiled=True)


def test_model_edit_and_following_automatic_transfer_have_separate_measurements(monkeypatch,tmp_path):
    import utils.langgraph_utils as language
    state=mixed_state(tmp_path, initial=True);calls=[]
    class Model:
        def __init__(self,*a):pass
        def reset(self):pass
        def step(self,message):
            data=json.loads(message.split('\nINPUT:\n',1)[1].split('\nCOMPLETE OUTPUT JSON SCHEMA:',1)[0])
            calls.append(data)
            module=deepcopy(data['whole_poster']['modules'][0])
            module['space_weight']=1
            module['entries'][0]['text'] += ' Locally.'
            value={'modules':[module] if len(calls)==1 else [],'remove_module_ids':[],
                   'module_order':[],'narrative_flow':'','reason':'Offline content edit.'}
            return SimpleNamespace(content=json.dumps(value),input_tokens=1,output_tokens=1)
    monkeypatch.setattr(language,'LangGraphAgent',Model)
    pipeline.editorial_joint_node(state);pipeline.editorial_compile_node(state)
    history=state['editorial_history']
    assert [h['phase'] for h in history]==['height_allocation','capacity','height_allocation','capacity']
    assert len(calls)==2
    assert len(state['editorial_budget']['charges'])==2
    assert history[1]['to']==history[2]['from']
    assert history[1]['measurements_after']==history[2]['measurements_before']
    before=history[2]['measurements_before']['modules'][0]['overage_inches']
    after=history[2]['measurements_after']['modules'][0]['overage_inches']
    assert after < before
    assert history[1]['observed_edit']['changed_modules'][0]['rewritten_entry_ids']
    assert all(m['changed_fields']==['space_weight'] for m in history[2]['observed_edit']['changed_modules'])
    assert_editorial_ready(state,compiled=True)


def test_combined_search_has_a_fixed_total_of_at_most_eight_exact_measurements(monkeypatch,tmp_path):
    import src.layout.editorial_layout as layout
    state=mixed_state(tmp_path, initial=True);counts={'exact':0,'fast':0};actual=measure
    def counted(*a,**kw):
        counts['exact' if kw.get('exact',True) else 'fast']+=1
        return actual(*a,**kw)
    monkeypatch.setattr(layout,'measure',counted)
    result=fit(state,state['editorial_candidate'],state['editorial_zones'])
    assert counts['fast']<=12
    assert counts['exact']<=8  # baseline + four regional finalists + three height trials
    assert len(result['report']['height_allocation']['trials'])<=3
