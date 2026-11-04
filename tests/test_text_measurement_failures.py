"""Fixed-font fitting failures, renderer soft wraps and bounded diagnostics."""
from copy import deepcopy
from pathlib import Path
import json
import math
import shutil
import subprocess

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import MSO_AUTO_SIZE

from src.layout import text_height_measurement as measurement
from src.layout.text_height_measurement import TextMeasurementError
from src.layout.measurement_context import measurement_scope, measurement_origin
from src.layout.text_fit_adapter import clusters
from test_editorial_generation import state_for, install
from src.layout import editorial_layout as layout


@pytest.mark.parametrize('text', ['scale-equivariance', 'Averylongunbrokenwordwhichcannotfit', 'αβγδεζηθικλμνξοπρστυφχψω'])
@pytest.mark.parametrize('settings', [None, {'enabled': False}, {'reuse_wrapping': False}])
def test_long_words_wrap_consistently_without_changing_source(text, settings):
    options = {'margins': {'left': .1, 'right': .1, 'top': .05, 'bottom': .05}}
    baseline = measurement.measure_text_height(text, 1.2, **options)
    with measurement_scope(settings) as context:
        result = measurement.measure_text_height(text, 1.2, **options)
        assert result == baseline and result['text_content'] == text
        assert result['optimal_height'] > 1
        assert context.failures == 0
        assert measurement.measure_text_height(text, 1.2, **options) == result


def test_soft_breaks_preserve_combining_and_joined_glyph_sequences():
    assert clusters('a\u0301b') == ['a\u0301', 'b']
    assert clusters('👩\u200d🔬x') == ['👩\u200d🔬', 'x']


@pytest.mark.parametrize('width', [.3, .01, 0, -1, math.nan])
def test_impossible_width_is_not_fabricated_height_or_cached_success(width):
    with measurement_scope() as context, measurement_origin(candidate_id='c', module_id='m', geometry_fingerprint='g'):
        for _ in range(2):
            with pytest.raises(TextMeasurementError) as caught:
                measurement.measure_text_height('Wide scientific word', width)
            assert caught.value.code in {'TEXT_INVALID_GEOMETRY', 'TEXT_WIDTH_INFEASIBLE'}
            assert caught.value.details['module_id'] == 'm'
        assert context.stats['exact']['hits'] == 0
        report = context.report('error')
        json.dumps(report, allow_nan=False)
        assert report['measurement_failures'] == 2
        assert report['measurement_failure_records'][0]['text_digest']
        assert 'Wide scientific word' not in json.dumps(report)


def test_unknown_backend_failure_is_reported_once_and_cleans_temporary_shape(monkeypatch):
    prs = Presentation(); monkeypatch.setattr(measurement, 'Presentation', lambda: prs)
    calls = []
    def broken(*args):
        calls.append(1)
        raise ValueError('backend failure')
    monkeypatch.setattr(measurement, 'fit_text', broken)
    state = {}
    with pytest.raises(TextMeasurementError, match='TEXT_MEASUREMENT_UNAVAILABLE'):
        with measurement_scope(report_state=state):
            measurement.measure_text_height('Retained text', 12)
    assert len(calls) == 1  # Never fifteen fake "not enough height" probes.
    assert len(prs.slides[0].shapes) == 0
    report = state['layout_performance_report']
    assert report['status'] == 'error' and report['measurement_failures'] == 1
    assert report['measurement_failure_records'][0]['traceback']


def test_unverified_height_bound_is_never_returned_as_success(monkeypatch):
    calls = []
    def never_fits(*args):
        calls.append(1)
        return {'height_probe_fits': False}
    monkeypatch.setattr(measurement, 'fit_text', never_fits)
    with pytest.raises(TextMeasurementError) as caught:
        measurement.measure_text_height('Text', 12)
    assert caught.value.code == 'TEXT_HEIGHT_LIMIT'
    assert len(calls) == 2


def test_long_text_above_previous_twenty_inch_cap_has_verified_bound():
    text = 'a ' * 80
    result = measurement.measure_text_height(text, 1.2)
    assert result['optimal_height'] > 20 and result['text_content'] == text
    with measurement_scope():
        assert measurement.measure_text_height(text, 1.2) == result


def test_failure_report_is_bounded_and_repeated_diagnostics_are_counted():
    with measurement_scope() as context:
        for i in range(150):
            context.record_failure('UNAVAILABLE', {'text_digest': str(i)})
        context.record_failure('UNAVAILABLE', {'text_digest': '0'})
        report = context.report('error')
        assert len(report['measurement_failure_records']) == 128
        assert report['measurement_failure_records_truncated']
        assert report['measurement_failure_records'][0]['occurrences'] == 2


def test_failed_exact_geometry_trial_is_not_selected_or_certified(monkeypatch, tmp_path):
    state = install(state_for(tmp_path)); candidate = state['editorial_candidate']
    zones = state['editorial_zones']; good = layout.measure(state, candidate, zones)
    alternative = deepcopy(zones); alternative[0]['width'] *= .99
    monkeypatch.setattr(layout, 'boundary_candidates', lambda *a: [alternative])
    def probe(st, c, z, *, exact=True):
        if z == alternative and exact:
            raise TextMeasurementError('TEXT_WIDTH_INFEASIBLE', {'module_id': 'module_0'})
        return deepcopy(good)
    monkeypatch.setattr(layout, 'measure', probe)
    result = layout.fit(state, candidate, zones)
    assert result['spec'] == good['spec']
    assert result['report']['geometry_trials'][-1]['measurement_status'] == 'unavailable'
    assert result['report']['geometry_trials'][-1]['measurement_failure']['code'] == 'TEXT_WIDTH_INFEASIBLE'


@pytest.mark.parametrize('text,width,font,size,bold', [
    ('scale-equivariance', 1.2, 'Arial', 44, False),
    ('Discrete Anti-Aliasing', 6.60303911111111, 'Helvetica Neue', 64, True)])
def test_actual_pptx_png_soft_wrap_preserves_font_text_and_measured_bounds(tmp_path, text, width, font, size, bold):
    import pymupdf
    if not shutil.which('libreoffice'):
        pytest.skip('LibreOffice unavailable')
    margins = {'left': .1, 'right': .1, 'top': .05, 'bottom': .05}
    result = measurement.measure_text_height(text, width, font, size, margins=margins, bold=bold)
    prs = Presentation(); prs.slide_width=Inches(8); prs.slide_height=Inches(14)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    frame = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(width), Inches(result['optimal_height'])).text_frame
    frame.word_wrap=True; frame.auto_size=MSO_AUTO_SIZE.NONE
    for key, value in margins.items():setattr(frame, 'margin_'+key, Inches(value))
    run=frame.paragraphs[0].add_run();run.text=text;run.font.name=font;run.font.size=Pt(size);run.font.bold=bold
    pptx=tmp_path/'softwrap.pptx';prs.save(pptx)
    reopened=Presentation(pptx).slides[0].shapes[0].text_frame
    assert reopened.text == text and reopened.paragraphs[0].runs[0].font.size.pt == size
    subprocess.run(['libreoffice','-env:UserInstallation='+(tmp_path/'lo').as_uri(),'--headless',
                    '--convert-to','pdf','--outdir',str(tmp_path),str(pptx)],check=True,capture_output=True,timeout=60)
    doc=pymupdf.open(tmp_path/'softwrap.pdf')
    lines=[line for block in doc[0].get_text('dict')['blocks'] if 'lines' in block for line in block['lines']]
    assert len(lines)>1
    assert ''.join(span['text'] for line in lines for span in line['spans']) == text
    assert max(line['bbox'][3] for line in lines) <= (1+result['optimal_height'])*72
    assert all(span['size'] == pytest.approx(size,abs=.1) for line in lines for span in line['spans'])
    doc[0].get_pixmap().save(tmp_path/'softwrap.png')
    assert (tmp_path/'softwrap.png').stat().st_size > 0
