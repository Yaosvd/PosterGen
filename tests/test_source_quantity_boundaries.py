"""Sentence punctuation retains quantity values and units on both sides."""
from decimal import Decimal
from pathlib import Path
import json

import pytest

from src.workflow.source_verification import quantity_tokens, numeric_support, check_module_verdict, targets_for
from src.workflow.source_document import SourceOutputError, build_document
from test_source_editorial import source_state, verdict_for, no_remote_models


@pytest.mark.parametrize('text,value,unit',[
    ('70%.','70','percent'),('100.','100','number'),('70.5%.','70.5','percent'),
    ('0.75.','0.75','number'),('1e-2.','0.01','number'),('-17%.','-17','percent'),
    ('1,600.','1600','number'),('5%, 70%.','70','percent')])
def test_punctuation_does_not_drop_or_change_quantity_units(text,value,unit):
    tokens=quantity_tokens(text)
    assert (Decimal(value),unit) in tokens
    if unit=='percent':assert (Decimal(value),'number') not in tokens


@pytest.mark.parametrize('target,source,accepted',[
    ('Approximately 42% to 70% improvement at 5%.','approximately 42%\nto 70%. At a low rate (5%), improvement is reported.',True),
    ('100 parcels','The evaluation used 100.',True),
    ('A 70% improvement.','The sample contains 70 parcels.',False),
    ('A 70.5% improvement.','The sample contains 70.5 parcels.',False),
    ('70%','70%.',True),('70.5%','70%.',False),
    ('70%','0.70.',False),('17%.','-17%.',False),
    ('80%.','70%.',False),('3–18%.','3% to 17%.',False),
])
def test_sentence_boundary_preserves_local_typed_numeric_admission(target,source,accepted):
    assert numeric_support(target,[{'quote':source}]) is accepted


def test_model_positive_verdict_cannot_turn_a_count_into_sentence_final_percent(tmp_path):
    state=source_state(tmp_path,count=1)
    module=state['source_candidate']['modules'][0]
    module['entries'][0]['text']='A 16000% improvement.'
    unit=state['source_document']['units'][0]
    paragraph=unit['paragraphs'][2]
    refs=[{'source_id':unit['source_id'],'paragraph_ids':[paragraph['paragraph_id']],
           'quote':unit['text'][paragraph['start']:paragraph['end']]}]
    module['source_refs']=refs
    verdict=verdict_for(module,state)
    targets=targets_for(module)
    with pytest.raises(SourceOutputError,match='quantity'):
        check_module_verdict(module,verdict,state['source_document'],targets,{'core':{}})


def test_abbreviated_source_failure_names_exact_value_target_and_quoted_paragraph(tmp_path):
    state=source_state(tmp_path,count=1)
    state['raw_text']=state['raw_text'].replace('16000 properties','80k properties')
    state['source_document']=build_document(state)
    module=state['source_candidate']['modules'][0]
    module['entries'][0]['text']='The evaluation uses 80,000 properties.'
    unit=state['source_document']['units'][0]
    paragraph=unit['paragraphs'][2]
    refs=[{'source_id':unit['source_id'],'paragraph_ids':[paragraph['paragraph_id']],
           'quote':unit['text'][paragraph['start']:paragraph['end']]}]
    module['source_refs']=refs
    verdict=verdict_for(module,state)
    with pytest.raises(SourceOutputError,match='quantity') as error:
        check_module_verdict(module,verdict,state['source_document'],targets_for(module),{'core':{}})
    diagnostic=json.loads(str(error.value).split(': ',1)[1])
    assert diagnostic['target_id']==module['module_id']+':idea'
    assert diagnostic['missing_quantities']==[{'value':'80000','kind':'number'}]
    assert diagnostic['actual_quoted_support']==refs
    assert '80k properties' in diagnostic['actual_quoted_support'][0]['quote']
    # Feedback improves without silently granting a new numeric conversion.
    assert not numeric_support(module['entries'][0]['text'],refs)


@pytest.mark.parametrize('target,source,accepted',[
    ('level 1 chooses a region; level 2 chooses a parcel.','A level-1 policy selects a region; a level-2 policy selects a parcel.',True),
    ('Level 1 chooses a region.','A level-1 policy chooses a region.',True),
    ('A level 1 policy spends 1 query.','A level-1 policy chooses a region.',False),
    ('1 query.','The level 1 policy chooses a region.',False),
    ('A level 1% improvement.','A level-1 policy chooses a region.',False),
    ('A level 1.5 response.','A level-1 policy chooses a region.',False),
    ('A level -1 response.','A level-1 policy chooses a region.',False),
])
def test_hierarchy_identifiers_are_not_experimental_quantities(target,source,accepted):
    assert numeric_support(target,[{'quote':source}]) is accepted
