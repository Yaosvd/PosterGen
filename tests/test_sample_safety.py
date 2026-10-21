from copy import deepcopy
from src.agents.font_agent import FontAgent
from src.layout.content_guards import board_identity
from src.layout.sample_safety import compiled_contract_audit, deletion_guard


def state_for(text):
    board={'spatial_content_plan':{'sections':[{'section_id':'s1','importance_level':2,
           'claim_ids':['c1'],'text_content':[text],'visual_assets':[]}]}}
    return {'story_board':board,'optimized_story_board':deepcopy(board),
            'verified_claims':{'claims':[{'claim_id':'c1','text':text,'verified':True}]},
            'sample_content_contract':{'desired_board':board_identity(board)}}


def test_compiled_content_audit_detects_lost_scientific_text():
    state=state_for('One verified finding.')
    report=compiled_contract_audit(state,[{'type':'section_container','section_id':'s1','importance_level':2}])
    assert not report['passed']
    assert any(i['code']=='compiled_scientific_text_mismatch' for i in report['violations'])


def test_compiled_content_audit_accepts_renderer_literal_escapes():
    state=state_for(r'Value a*b with \alpha and **literal stars**.')
    text=state['story_board']['spatial_content_plan']['sections'][0]['text_content'][0]
    content=FontAgent._escape_formatting_literals(text).replace('Value','**Value**')
    layout=[{'type':'section_container','section_id':'s1','importance_level':2},
            {'type':'text','section_id':'s1','content':content}]
    assert compiled_contract_audit(state,layout)['passed']


def test_deletion_guard_rejects_global_holes_despite_better_local_fill():
    baseline={'zone_utilization':{'z':.95},'exact_bottom_gaps':{'z':.2},
              'composition_whitespace':{'unallocated_body_fraction':.05,'largest_empty_rectangle_fraction':.03}}
    state={'sample_content_contract':{'removed_visual_occurrences':[['s1','figure_1']]},
           'sample_fit_baseline':{'fit_report':baseline}}
    worse=deepcopy(baseline);worse['zone_utilization']['z']=.99
    worse['composition_whitespace']['largest_empty_rectangle_fraction']=.20
    assert not deletion_guard(state,worse)['passed']
    assert deletion_guard(state,baseline)['passed']
