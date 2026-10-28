"""Returned structured-output truncation uses only the existing format allowance."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import json

import httpx
import pytest
from openai import LengthFinishReasonError
from openai.types.chat import ChatCompletion

from test_source_editorial import source_state, verdict_for, no_remote_models
from src.workflow.source_document import SourceOutputError, SourceProtocolError, paragraph_hints
from src.workflow.source_requests import SourceRequests, read
from src.workflow.source_verification import VERDICT_SCHEMA
from utils.model_requests import SampleRequestFailure
from utils.persistence import read_json


def length_error(content=None, *, usage=True):
    completion=ChatCompletion(id='chatcmpl-offline-length',object='chat.completion',created=1,model='offline',
        choices=[{'index':0,'finish_reason':'length','message':{'role':'assistant','content':content,
            'reasoning_content':'UNVERIFIED_REASONING_MUST_NOT_ENTER_REPAIR_PROMPT'}}],
        usage={'prompt_tokens':30,'completion_tokens':12000,'total_tokens':12030} if usage else None)
    return LengthFinishReasonError(completion=completion)


class Agent:
    def __init__(self,*responses):self.responses=iter(responses);self.calls=[]
    def reset(self):pass
    def step(self,message):
        self.calls.append(message)
        response=next(self.responses)
        if isinstance(response,BaseException):
            raise SampleRequestFailure('Actual model wrapper failure') from response
        return SimpleNamespace(content=json.dumps(response),input_tokens=9,output_tokens=4)


def case(tmp_path, *, content=None, capture=True):
    state=source_state(tmp_path,count=1)
    value=paragraph_hints(verdict_for(state['source_candidate']['modules'][0],state),state['source_document'])
    journal=SourceRequests(state,'source/length','verify',VERDICT_SCHEMA,capture_length=capture)
    return state,value,journal


def test_real_completed_sdk_receipt_uses_one_shared_repair_and_exact_replay(tmp_path):
    state,value,journal=case(tmp_path)
    agent=Agent(length_error(),value)
    accepted=journal.call(agent)
    assert accepted['status']=='supported' and len(agent.calls)==2
    assert 'UNVERIFIED_REASONING' not in agent.calls[1]
    response=read(journal.root/'response_00.json',journal.identity)
    receipt=read(journal.root/'provider_completion_00.json',journal.identity)
    assert response['content']=='' and response['provider_finish_reason']=='length'
    assert response['output_tokens']==12000 and receipt['completion']['usage']['completion_tokens']==12000
    assert read_json(Path(state['sample_preparation_dir'])/'source_format_correction.json')['payload']['limit']==1
    usage=asdict(state['tokens'])
    assert journal.call(agent)==accepted and len(agent.calls)==2
    assert asdict(state['tokens'])==usage


@pytest.mark.parametrize('mode',['missing','corrupt','missing_response'])
def test_receipt_or_charged_response_loss_never_buys_resubmission(tmp_path,mode):
    state,value,journal=case(tmp_path)
    agent=Agent(length_error(),value)
    journal.call(agent)
    path=journal.root/('response_00.json' if mode=='missing_response' else 'provider_completion_00.json')
    if mode=='corrupt':path.write_text('{"payload":{}}')
    else:path.unlink()
    with pytest.raises((ValueError,FileNotFoundError)):
        journal.call(agent)
    assert len(agent.calls)==2


@pytest.mark.parametrize('failure',[httpx.ReadTimeout('No response'),length_error(usage=False)])
def test_missing_or_incomplete_provider_receipt_cannot_enter_format_recovery(tmp_path,failure):
    state,value,journal=case(tmp_path)
    agent=Agent(failure,value)
    with pytest.raises(SampleRequestFailure):journal.call(agent)
    assert len(agent.calls)==1 and not (journal.root/'response_00.json').exists()
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()
    with pytest.raises(ValueError,match='charged but missing response'):journal.call(agent)
    assert len(agent.calls)==1


def test_other_request_stages_do_not_opt_into_receipt_recovery(tmp_path):
    state,value,journal=case(tmp_path,capture=False)
    agent=Agent(length_error(),value)
    with pytest.raises(SampleRequestFailure):journal.call(agent)
    assert len(agent.calls)==1 and not (journal.root/'response_00.json').exists()


def test_scientific_negative_in_returned_length_response_cannot_buy_repair(tmp_path):
    state,value,journal=case(tmp_path)
    negative=deepcopy(value);negative['status']='unsupported'
    agent=Agent(length_error(json.dumps(negative)),value)
    with pytest.raises(SourceOutputError,match='Explicit scientific rejection'):journal.call(agent)
    assert len(agent.calls)==1 and not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()
    assert (journal.root/'provider_completion_00.json').is_file()


def test_second_length_response_exhausts_same_one_shared_format_budget(tmp_path):
    state,value,journal=case(tmp_path)
    agent=Agent(length_error(),length_error(),value)
    with pytest.raises(SourceProtocolError,match='no remaining format recovery'):journal.call(agent)
    assert len(agent.calls)==2 and (journal.root/'provider_completion_01.json').is_file()
    with pytest.raises(SourceProtocolError):journal.call(agent)
    assert len(agent.calls)==2


def test_length_receipt_does_not_get_a_new_allowance_after_another_stage_spent_it(tmp_path):
    state,value,journal=case(tmp_path)
    previous=SourceRequests(state,'source/previous_format','previous',VERDICT_SCHEMA)
    assert previous.call(Agent({},value))['status']=='supported'
    agent=Agent(length_error(),value)
    with pytest.raises(SourceProtocolError,match='allowance is exhausted'):journal.call(agent)
    assert len(agent.calls)==1 and (journal.root/'provider_completion_00.json').is_file()


@pytest.mark.parametrize('rewrite',[False,True])
def test_complete_json_with_length_finish_cannot_rewrite_its_valid_verdict(tmp_path,rewrite):
    state,value,journal=case(tmp_path)
    recovered=deepcopy(value)
    if rewrite:recovered['reason']='A different scientific explanation.'
    agent=Agent(length_error(json.dumps(value)),recovered)
    if rewrite:
        with pytest.raises(SourceProtocolError,match='no remaining format recovery'):journal.call(agent)
    else:
        assert journal.call(agent)['status']=='supported'
    assert len(agent.calls)==2
