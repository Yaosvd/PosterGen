"""Final compilation must preserve frozen output while reusing local measurements."""
from contextlib import nullcontext
from copy import deepcopy

import pytest

from src.layout.families import LayoutFamilyRegistry
from src.layout import measurement_context as contexts
from src.workflow import editorial_pipeline as pipeline
from test_editorial_generation import state_for, install


def frozen(monkeypatch, tmp_path, family):
    state = install(state_for(tmp_path, family))
    pipeline.charge(state, 'curator', 'offline_fixture')
    monkeypatch.setattr(pipeline, 'fit', pipeline.measure)
    monkeypatch.setattr(pipeline, 'edit', lambda *args: False)
    pipeline.editorial_joint_node(state)
    return state


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_final_compilation_matches_uncached_in_every_family(monkeypatch, tmp_path, family):
    state = frozen(monkeypatch, tmp_path, family)
    expected = deepcopy(state)
    measure = pipeline.measure
    baseline_results = []

    def uncached(*args):
        result = measure(*args)
        baseline_results.append(deepcopy(result))
        return result

    # Run the same production compiler with the previous no-scope behavior.
    with monkeypatch.context() as baseline:
        baseline.setattr(contexts, 'measurement_scope', lambda *args: nullcontext())
        baseline.setattr(pipeline, 'measure', uncached)
        pipeline.editorial_compile_node(expected)
    observed = []

    def checked(*args):
        context = contexts.current_context()
        assert context is not None and not context.cache
        result = measure(*args)
        observed.append((context, deepcopy(result)))
        return result

    monkeypatch.setattr(pipeline, 'measure', checked)
    actual = pipeline.editorial_compile_node(deepcopy(state))
    assert actual == expected
    assert len(observed) == 1
    context, result = observed[0]
    assert result == baseline_results[0]
    assert result['layout'] == expected['design_layout']
    assert sum(bucket['hits'] for bucket in context.stats.values()) > 0
    assert context.closed and not context.cache and contexts.current_context() is None


@pytest.mark.parametrize('settings', [{'enabled': False}, {'reuse_wrapping': False}])
def test_compilation_honors_existing_fallback_settings(monkeypatch, tmp_path, settings):
    state = frozen(monkeypatch, tmp_path, 'classic_three_column')
    state['critic_config']['layout_performance'].update(settings)
    expected = deepcopy(state)
    with monkeypatch.context() as baseline:
        baseline.setattr(contexts, 'measurement_scope', lambda *args: nullcontext())
        pipeline.editorial_compile_node(expected)
    assert pipeline.editorial_compile_node(deepcopy(state)) == expected
    assert contexts.current_context() is None


def test_failed_compile_releases_private_cache_and_preserves_parent(monkeypatch, tmp_path):
    state = frozen(monkeypatch, tmp_path, 'classic_three_column')
    seen = []

    def failed(*args):
        context = contexts.current_context()
        seen.append(context)
        context.memo('exact', ('failure-fixture',), lambda: {'height': 1})
        raise RuntimeError('offline measurement failure')

    monkeypatch.setattr(pipeline, 'measure', failed)
    with contexts.measurement_scope() as parent:
        with pytest.raises(RuntimeError, match='offline measurement failure'):
            pipeline.editorial_compile_node(state)
        assert contexts.current_context() is parent
        assert seen[0] is not parent and seen[0].closed and not seen[0].cache
    assert contexts.current_context() is None
