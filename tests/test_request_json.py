"""Model payloads preserve numeric semantics and fail before remote requests."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import numpy as np
import pytest

from utils.request_json import request_json
from utils.persistence import digest


def test_nested_numpy_scalars_keep_types_values_and_identity():
    value = {'measurements': {'passed': np.bool_(False), 'height': np.float64(12.5)},
             'rows': [np.int64(7), (np.float32(.25), np.bool_(True))]}
    expected = {'measurements': {'passed': False, 'height': 12.5}, 'rows': [7, [.25, True]]}
    result = request_json(value)
    assert result == json.dumps(expected, ensure_ascii=False)
    assert digest(value) == digest(json.loads(result))
    assert type(value['measurements']['passed']) is np.bool_


def test_regular_json_has_identical_wire_bytes():
    value = {'科学': ['w_i* ≥ w_j*', '\\alpha', False, None, -0.0, 1.5], 'tuple': (1, 2)}
    assert request_json(value) == json.dumps(value, ensure_ascii=False)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'),
                               np.float32('nan'), np.float64('inf')])
def test_nonfinite_numbers_report_the_exact_nested_path(bad):
    with pytest.raises(ValueError, match=r'\$/rows/0/height'):
        request_json({'rows': [{'height': bad}]})


@pytest.mark.parametrize('bad', [object(), Path('/tmp/value'), np.array([1]),
                               np.complex64(1+2j), np.datetime64('2026-11-12')])
def test_unknown_values_are_never_stringified(bad):
    with pytest.raises(TypeError, match=r'\$/measurements/a~1b~0c'):
        request_json({'measurements': {'a/b~c': bad}})


def test_nonstring_keys_are_rejected_before_colliding_with_string_keys():
    with pytest.raises(TypeError, match='Non-string request key'):
        request_json({1: 'numeric', '1': 'string'})


def test_real_request_boundary_serializes_once_and_replays_without_call(tmp_path, monkeypatch):
    from test_editorial_generation import state_for
    from src.workflow.editorial_requests import request, obj, STRING
    import utils.langgraph_utils as language
    state = state_for(tmp_path)
    calls = []
    class Agent:
        def __init__(self, *args): pass
        def reset(self): pass
        def step(self, prompt):
            calls.append(prompt)
            return SimpleNamespace(content='{"title":"ok"}', input_tokens=1, output_tokens=1)
    monkeypatch.setattr(language, 'LangGraphAgent', Agent)
    payload = {'measurements': {'passed': np.bool_(False), 'height': np.float64(1.25)}}
    args = (state, 'editorial_metadata', payload, obj({'title': STRING}))
    assert request(*args, directory='editorial/numeric') == {'title': 'ok'}
    assert '"passed": false' in calls[0]
    assert request(*args, directory='editorial/numeric') == {'title': 'ok'}
    assert len(calls) == 1
    bad = deepcopy(payload); bad['measurements']['height'] = object()
    with pytest.raises(TypeError, match=r'\$/measurements/height'):
        request(state, 'editorial_metadata', bad, obj({'title': STRING}), directory='editorial/bad')
    assert len(calls) == 1
    assert not (Path(state['sample_preparation_dir'])/'editorial/bad').exists()


def test_formula_measurements_and_report_flags_are_native_numbers(tmp_path):
    from utils.display_formula import measure_formula, expression_to_mathtext
    from src.layout.editorial_layout import measure
    from test_editorial_generation import state_for, install
    formula = expression_to_mathtext('x = a/b')
    dimensions = measure_formula(formula, 44, 10)
    assert all(type(v) is float and v > 0 for v in dimensions)
    state = install(state_for(tmp_path, text='The objective is x = a/b.'))
    result = measure(state, state['editorial_candidate'], state['editorial_zones'])
    assert type(result['report']['passed']) is bool
    json.dumps(result, allow_nan=False)


def test_request_converter_participates_in_paper_cache_identity():
    from src.workflow.paper_cache import extraction_identity
    settings = {'preparation_policy_version': 'sample_editorial_v1',
                'code_identity': {'utils/request_json.py': 'original'}}
    before = extraction_identity(settings)
    settings['code_identity']['utils/request_json.py'] = 'changed'
    assert extraction_identity(settings) != before
