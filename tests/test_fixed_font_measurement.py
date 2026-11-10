"""Fixed-font height predicates must preserve the original full-search oracle."""
from copy import deepcopy

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

from src.layout import text_fit_adapter as adapter
from src.layout import text_height_measurement as measurement
from src.layout.measurement_context import measurement_scope
from src.layout.families import LayoutFamilyRegistry


def frame(text, width=8, height=4, size=44):
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    result = slide.shapes.add_textbox(0, 0, Inches(width), Inches(height)).text_frame
    result.text = text
    for paragraph in result.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(size)
    return result


def reduced(text_frame, size):
    return any(run.font.size and run.font.size.pt < size - .5
               for paragraph in text_frame.paragraphs for run in paragraph.runs)


@pytest.mark.parametrize('size', [2, 44, 64])
@pytest.mark.parametrize('height', [.001, .8, 8])
def test_predicate_agrees_with_full_fit_and_does_not_mutate_frame(size, height):
    text = 'A scientific result with necessary conditions and supporting evidence.'
    current = frame(text, height=height, size=size)
    original = frame(text, height=height, size=size)
    font = measurement.get_font_file_path('Arial')
    xml = current._txBody.xml
    with measurement_scope():
        fitting = adapter.fixed_size_fits(current, font, size)
        assert current._txBody.xml == xml
        if fitting is None:
            # Too little height for even size 1 must retain the old exception.
            with pytest.raises((TypeError, ValueError)):
                adapter.fit_text(original, font, size)
        else:
            adapter.fit_text(original, font, size)
            assert fitting is (not reduced(original, size))


def test_only_target_and_minimum_are_probed_instead_of_searching_smaller_sizes(monkeypatch):
    text_frame = frame('Scientific evidence. ' * 8, height=1)
    font = measurement.get_font_file_path('Arial')
    sizes = []
    original = adapter._CachedTextFitter._fits_inside_predicate.fget
    def recorded(fitter):
        predicate = original(fitter)
        def call(size):
            sizes.append(size)
            return predicate(size)
        return call
    monkeypatch.setattr(adapter._CachedTextFitter, '_fits_inside_predicate', property(recorded))
    with measurement_scope():
        assert adapter.fixed_size_fits(text_frame, font, 44) is False
        assert sizes == [44, 1]
        sizes.clear()
        adapter.fit_text(text_frame, font, 44)
        assert reduced(text_frame, 44)
        assert len(sizes) > 2 and any(s not in {44, 1} for s in sizes)


@pytest.mark.parametrize('settings', [{'enabled': False}, {'reuse_wrapping': False}])
def test_disabled_optimization_defers_to_original(settings):
    text_frame = frame('Supported text.')
    font = measurement.get_font_file_path('Arial')
    assert adapter.fixed_size_fits(text_frame, font, 44) is None
    with measurement_scope(settings):
        assert adapter.fixed_size_fits(text_frame, font, 44) is None


@pytest.mark.parametrize('size', [1, 44.0, 44.49, 44.5, 44.51])
def test_fractional_half_point_rule_and_small_sizes_use_original(monkeypatch, size):
    text = 'Fractional font thresholds must retain their original meaning.'
    font = measurement.get_font_file_path('Arial')
    with measurement_scope():
        assert adapter.fixed_size_fits(frame(text), font, size) is None
        actual = measurement.measure_text_height(text, 7, font_size=size)
    with monkeypatch.context() as old, measurement_scope():
        old.setattr(measurement, 'fixed_size_fits', lambda *args: None)
        assert measurement.measure_text_height(text, 7, font_size=size) == actual


@pytest.mark.parametrize('change', ['version', 'line_source', 'interface', 'missing_font', 'empty'])
def test_unverified_inputs_keep_existing_fallback(monkeypatch, tmp_path, change):
    text_frame = frame('Unverified inputs.')
    font = measurement.get_font_file_path('Arial')
    if change == 'version':
        monkeypatch.setattr(adapter, 'backend_versions', lambda: ('future', 'future'))
    elif change == 'line_source':
        monkeypatch.setattr(adapter, '_LineSource', None)
    elif change == 'interface':
        monkeypatch.setattr(adapter, 'TextFitter', object)
    elif change == 'missing_font':
        font = str(tmp_path / 'missing.ttf')
    else:
        text_frame.text = '   '
    with measurement_scope():
        assert adapter.fixed_size_fits(text_frame, font, 44) is None


def test_minimum_probe_error_does_not_add_an_error_to_successful_full_search(monkeypatch):
    text_frame = frame('Scientific evidence. ' * 8, height=1)
    font = measurement.get_font_file_path('Arial')
    original = adapter._CachedTextFitter._fits_inside_predicate.fget
    def minimum_error(fitter):
        predicate = original(fitter)
        def call(size):
            if size == 1:
                raise ValueError('minimum-only backend error')
            return predicate(size)
        return call
    monkeypatch.setattr(adapter._CachedTextFitter, '_fits_inside_predicate', property(minimum_error))
    with measurement_scope():
        assert adapter.fixed_size_fits(text_frame, font, 44) is None
        adapter.fit_text(text_frame, font, 44)
        assert reduced(text_frame, 44)


@pytest.mark.parametrize('text,width,config_change', [
    ('Unbreakablewordwhichcannotfit', .3, False),
    ('Dense text must not turn an unknown fit into a successful cached height.', 8, True),
])
def test_impossible_fit_preserves_failure_counts_and_noncacheability(monkeypatch, text, width, config_change):
    if config_change:
        config = measurement.load_config()
        config['text_measurement'].update(min_height=.001, max_height=.03)
        monkeypatch.setattr(measurement, 'load_config', lambda: deepcopy(config))
    rows = []
    for optimized in (False, True):
        with monkeypatch.context() as mode, measurement_scope() as context:
            if not optimized:
                mode.setattr(measurement, 'fixed_size_fits', lambda *args: None)
            first = measurement.measure_text_height(text, width)
            second = measurement.measure_text_height(text, width)
            rows.append((first, second, context.failures))
            assert context.failures > 0
            assert context.stats['exact']['hits'] == 0
    assert rows[0] == rows[1]


@pytest.mark.parametrize('family', LayoutFamilyRegistry().ids())
def test_actual_image_frames_full_search_and_capacity_payload_are_identical(monkeypatch, tmp_path, family):
    from test_editorial_generation import state_for, draft_for, plan_for, prose_for, install
    from test_editorial_authoring import geometry_for
    from src.workflow.editorial_authoring import written_candidate, persist_geometry
    from src.workflow.editorial_pipeline import capacity_payload
    from src.layout.editorial_layout import fit
    from src.layout.authoring_geometry import assert_initial_frames
    from src.layout.editorial_layout import measure
    from src.layout.editorial_composition import initial_fit
    import utils.langgraph_utils as language

    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No real model'))

    state = state_for(tmp_path, family)
    raw = draft_for(state)
    state['images'] = {str(i): {'aspect': 3.24 if i % 2 == 0 else .8}
                       for i in range(len(raw['modules']))}
    for i, module in enumerate(raw['modules']):
        module['visual_ids'] = [f'figure_{i}']
        module['entries'][0]['text'] *= 3
    results = []
    for optimized in (False, True):
        working = deepcopy(state)
        with monkeypatch.context() as mode, measurement_scope():
            if not optimized:
                mode.setattr(measurement, 'fixed_size_fits', lambda *args: None)
            install(working, raw)
            geometry, zones = geometry_for(working, raw)
            persist_geometry(working, plan_for(raw), geometry)
            candidate = written_candidate(prose_for(raw), plan_for(raw), working, zones)
            working['editorial_candidate'] = candidate
            working['editorial_zones'] = zones
            baseline = measure(working, candidate, zones)
            assert_initial_frames(geometry, baseline)
            # Establish the real frozen-direction receipt, without replaying
            # the bounded search being compared below.
            initial_fit(working, fitter=measure)
            result = fit(working, candidate, zones)
            results.append((geometry, baseline, result, capacity_payload(working, result)))
    assert results[0] == results[1]


def test_actual_height_transfer_trials_choose_identical_weights(monkeypatch, tmp_path):
    from test_editorial_height_allocation import mixed_state
    from src.layout.editorial_layout import measure
    from src.layout.editorial_space import coordinate_module_heights
    import utils.langgraph_utils as language

    monkeypatch.setattr(language, 'create_model', lambda *a, **k: pytest.fail('No real model'))
    state = mixed_state(tmp_path)
    original = deepcopy(state)
    results = []
    for optimized in (False, True):
        with monkeypatch.context() as mode, measurement_scope():
            if not optimized:
                mode.setattr(measurement, 'fixed_size_fits', lambda *args: None)
            baseline = measure(state, state['editorial_candidate'], state['editorial_zones'])
            result = coordinate_module_heights(state, state['editorial_candidate'], baseline)
            allocation = result['report']['height_allocation']
            assert allocation['status'] == 'adopted'
            assert 0 < len(allocation['trials']) <= allocation['exact_trial_limit']
            results.append((baseline, result))
    assert results[0] == results[1]
    assert state == original
