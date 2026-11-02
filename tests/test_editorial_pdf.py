"""Adaptive native/raster selection, visible evidence and honest early failures."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pymupdf
import pytest

from test_source_pdf import native_fixture
from utils.editorial_pdf import (transcribe_visible, validate_visible, extract_visible_text,
    bind_visible_captions, quality_summary, VERSION)
from utils.source_pdf import transcribe_regions, SourceExtractionError
from utils.pdf_ocr import RasterOCR, MAX_PIXELS, EmptyRasterRegion
from utils.persistence import digest, file_hash


@pytest.fixture(autouse=True)
def no_live_model(monkeypatch):
    import utils.langgraph_utils as language
    monkeypatch.setattr(language,'create_model',lambda *a,**k:pytest.fail('Unexpected authoring model'))


def raster(text, confidence=.97, box=None):
    def callback(page, requested):
        return {'engine':'offline_raster_fixture','image_hash':'fixture_pixels',
                'lines':[{'text':text,'bbox':box or list(requested),'confidence':confidence}]}
    return callback


def document_for(pages):
    result=[]
    for layout in pages:
        children={r['region_id']:SimpleNamespace(
            block_type=SimpleNamespace(name=r['kind']),structure=[],
            polygon=SimpleNamespace(bbox=r['bbox']),heading_level=r.get('heading_level'),
            raw_text=lambda doc,t=r.get('marker_text',''):t) for r in layout['regions']}
        result.append(SimpleNamespace(page_id=layout['page_index'],
            polygon=SimpleNamespace(bbox=layout['bbox']),structure=list(children),
            get_block=lambda key,c=children:c[key]))
    return SimpleNamespace(pages=result)


@pytest.mark.parametrize('native,marker',[
    ('The frst result is udpated.','The first result is updated.'),
    ('The result improves after affixation.','The result improves afer afxation.'),
    ('The model uses a shared encoder.','The model uses a separate encoder.'),
    ('Clitics are inflectional.','Clitics are infectional.'),
])
def test_readable_native_is_preserved_with_diagnostics_not_dictionary_changes(tmp_path,native,marker):
    pdf,pages=native_fixture(tmp_path,[(30,50,native)])
    pages[0]['regions'][0]['marker_text']=marker
    raw,report=transcribe_visible(pdf,pages,marker,ocr=lambda *a:pytest.fail('Native prose needs no OCR'))
    assert raw==native and not report['issues'] and report['warnings']
    assert report['blocks'][0]['method']=='native_pdf'
    validate_visible(report,raw,file_hash(pdf))
    assert quality_summary(report)['scientific_truth_verified'] is False


def test_clipped_form_extra_text_never_enters_emitted_source(tmp_path):
    pdf=tmp_path/'clipped.pdf'
    with pymupdf.open() as source,pymupdf.open() as target:
        s=source.new_page(width=500,height=300)
        s.insert_text((30,50),'Hidden paragraph with 99%.')
        s.insert_text((30,120),'Visible result: 3%.')
        t=target.new_page(width=500,height=300)
        t.show_pdf_page(pymupdf.Rect(20,20,480,180),source,0,clip=pymupdf.Rect(0,95,500,145))
        target.save(pdf)
    with pymupdf.open(pdf) as doc:
        blocks=doc[0].get_text('blocks');assert 'Hidden' not in doc[0].get_text()
        pages=[{'page_index':0,'bbox':list(doc[0].rect),'regions':[
            {'region_id':'clipped','kind':'Text','bbox':list(b[:4]),
             'marker_text':'Hidden paragraph with 99%.\n'+b[4]} for b in blocks]}]
    raw,report=transcribe_visible(pdf,pages,'PDFium with clipped contents',
                               ocr=lambda *a:pytest.fail('Clear clipped native text needs no OCR'))
    assert 'Visible result: 3%.' in raw and 'Hidden' not in raw
    assert not report['issues'] and any(w['kind']=='native_preferred_converter_extra' for w in report['warnings'])


@pytest.mark.parametrize('printed,converted,visible,method',[
    ('Gain 3%.','Gain 70%.','Gain 3%.','native_pdf'),
    ('Gain 3%.','Gain 70%.','Gain 70%.','raster_ocr'),
    ('Gain 3%.','Gain 30%.','Gain 3%.','native_pdf'),
    ('Gain 3%.','Gain -3%.','Gain 3%.','native_pdf'),
])
def test_numerical_replacements_need_actual_raster_reconciliation(tmp_path,printed,converted,visible,method):
    pdf,pages=native_fixture(tmp_path,[(30,50,printed)])
    pages[0]['regions'][0]['marker_text']=converted
    calls=[]
    def recognize(page,box):calls.append(box);return raster(visible)(page,box)
    raw,report=transcribe_visible(pdf,pages,converted,ocr=recognize)
    assert raw==visible and not report['issues'] and len(calls)==1
    assert report['blocks'][0]['method']==method
    assert report['blocks'][0]['ocr_receipt']['image_hash']
    validate_visible(report,raw,file_hash(pdf))


@pytest.mark.parametrize('visible', ['Gain 25%.','Gain -70%.','Gain 370%.'])
def test_unresolved_numerical_conflicts_remain_blocking(tmp_path,visible):
    pdf,pages=native_fixture(tmp_path,[(30,50,'Gain 3%.')])
    pages[0]['regions'][0]['marker_text']='Gain 70%.'
    raw,report=transcribe_visible(pdf,pages,'Gain 70%.',ocr=raster(visible))
    assert report['status']=='rejected' and report['issues']
    with pytest.raises(SourceExtractionError):validate_visible(report,raw,file_hash(pdf))


def test_table_cell_boundaries_are_not_treated_as_changed_numbers(tmp_path):
    pdf,pages=native_fixture(tmp_path,[(30,50,'3.00 17.00')])
    pages[0]['regions'][0].update(kind='Table',marker_text='3.0017.00',
        marker_cells=[{'text':'3.00'},{'text':'17.00'}])
    raw,report=transcribe_visible(pdf,pages,'table',ocr=lambda *a:pytest.fail('Cells already agree'))
    assert not report['issues'] and '3.00 17.00' in raw


@pytest.mark.parametrize('printed,converted',[
    ('Gain 3.00%.','Gain 3%.'),('Number 1,000.','Number 1000.'),('Value 0.001.','Value 1e-3.'),
    ('Value .05.','Value 0.05.'),('Value 0.000.','Value 0.')])
def test_equivalent_numeric_formatting_retains_original_precision_without_ocr(tmp_path,printed,converted):
    pdf,pages=native_fixture(tmp_path,[(30,50,printed)])
    pages[0]['regions'][0]['marker_text']=converted
    raw,report=transcribe_visible(pdf,pages,converted,ocr=lambda *a:pytest.fail('Equivalent numeric values'))
    assert raw==printed and not report['issues']


def test_long_numeric_identifiers_do_not_compare_equal_through_decimal_rounding(tmp_path):
    printed='Value 123456789012345678901234567891.'
    converted='Value 123456789012345678901234567890.'
    pdf,pages=native_fixture(tmp_path,[(30,50,printed)])
    pages[0]['regions'][0]['marker_text']=converted
    calls=[]
    def recognize(page,box):calls.append(box);return raster(printed)(page,box)
    raw,report=transcribe_visible(pdf,pages,converted,ocr=recognize)
    assert not report['issues'] and raw==printed and len(calls)==1


def test_leading_decimal_point_is_not_lost_in_numerical_conflict_detection(tmp_path):
    pdf,pages=native_fixture(tmp_path,[(30,50,'Value .05.')])
    pages[0]['regions'][0]['marker_text']='Value 5.'
    calls=[]
    def recognize(page,box):calls.append(box);return raster('Value .05.')(page,box)
    raw,report=transcribe_visible(pdf,pages,'converted',ocr=recognize)
    assert not report['issues'] and raw=='Value .05.' and len(calls)==1


def test_printable_garbled_native_does_not_win_merely_because_numbers_match(tmp_path):
    pdf,pages=native_fixture(tmp_path,[(30,50,'xyzz xqrr zwwq 17%.')])
    pages[0]['regions'][0]['marker_text']='Measured gain is 17%.'
    raw,report=transcribe_visible(pdf,pages,'converted',ocr=raster('Measured gain is 17%.'))
    assert not report['issues'] and raw=='Measured gain is 17%.'
    assert report['blocks'][0]['method']=='raster_ocr'


@pytest.mark.parametrize('kind',['Table','Equation'])
def test_structural_decoder_order_is_not_treated_as_prose_garbling(tmp_path,kind):
    pdf,pages=native_fixture(tmp_path,[(30,50,'Method A 3.00 Method B 17.00')])
    pages[0]['regions'][0].update(kind=kind,marker_text='3.00 17.00 Method B Method A')
    raw,report=transcribe_visible(pdf,pages,'structural',ocr=lambda *a:pytest.fail('Known traversal difference'))
    assert not report['issues'] and raw=='Method A 3.00 Method B 17.00'


@pytest.mark.parametrize('angle',[90,180,270])
@pytest.mark.parametrize('scale',[1,2])
def test_rotated_marker_regions_map_back_to_native_pdf_coordinates(tmp_path,angle,scale):
    original,pages=native_fixture(tmp_path)
    pdf=tmp_path/'rotated.pdf'
    with pymupdf.open(original) as doc:
        p=doc[0];p.set_rotation(angle)
        for r in pages[0]['regions']:
            r['bbox']=[v*scale for v in (pymupdf.Rect(r['bbox'])*p.rotation_matrix)]
        pages[0]['bbox']=[v*scale for v in p.rect]
        doc.save(pdf)
    raw,report=transcribe_visible(pdf,pages,'rotated',ocr=lambda *a:pytest.fail('Readable rotated native'))
    assert not report['issues'] and 'first finding' in raw
    assert report['pages'][0]['rotation']==angle
    assert report['blocks'][0]['pdf_bbox'][0]==pytest.approx(30,abs=1)


def scanned_fixture(tmp_path,region_count=1):
    pdf=tmp_path/'scan.pdf'
    with pymupdf.open() as doc,pymupdf.open() as source:
        p=doc.new_page(width=300,height=400)
        s=source.new_page(width=300,height=400);s.insert_text((30,50),'Measured gain is 17%.')
        p.insert_image(p.rect,pixmap=s.get_pixmap());doc.save(pdf)
    pages=[{'page_index':0,'bbox':[0,0,300,400],'regions':[
        {'region_id':str(i),'kind':'Text','bbox':[0,i*10,300,(i+1)*10],
         'marker_text':'Converted scanned text.'} for i in range(region_count)]}]
    return pdf,pages


@pytest.mark.parametrize('regions',[1,30])
def test_scanned_page_has_one_raster_pass_and_honest_ocr_provenance(tmp_path,regions):
    pdf,pages=scanned_fixture(tmp_path,regions)
    calls=[]
    def recognize(page,box):calls.append(box);return raster('Measured gain is 17%.')(page,box)
    raw,report=transcribe_visible(pdf,pages,'OCR text',ocr=recognize)
    assert raw=='Measured gain is 17%.' and not report['issues']
    assert calls==[[0,0,300,400]]
    assert report['blocks'][0]['method']=='raster_ocr' and not report['blocks'][0]['glyphs']
    assert report['pages'][0]['native_nonspace_glyphs']==0
    validate_visible(report,raw,file_hash(pdf))
    _,legacy=transcribe_regions(pdf,pages,'OCR text')
    assert legacy['status']=='rejected'  # Explicit old source still requires native glyphs.


def test_scanned_columns_follow_marker_regions_rather_than_interleaved_detection(tmp_path):
    pdf,pages=scanned_fixture(tmp_path)
    pages[0]['regions']=[{'region_id':'left','kind':'Text','bbox':[0,0,140,400],'marker_text':'left'},
                         {'region_id':'right','kind':'Text','bbox':[160,0,300,400],'marker_text':'right'}]
    def recognize(page,box):
        return {'engine':'offline_raster_fixture','image_hash':'fixture', 'lines':[
            {'text':text,'confidence':.99,'bbox':bbox} for text,bbox in [
                ('Left first.',[20,20,100,40]),('Right first.',[180,20,280,40]),
                ('Left second.',[20,60,100,80]),('Right second.',[180,60,280,80])]]}
    raw,report=transcribe_visible(pdf,pages,'scan',ocr=recognize)
    assert not report['issues']
    assert raw.index('Left second')<raw.index('Right first')
    assert [b['region_id'] for b in report['blocks']]==['left','right']
    assert all(b['reading_order']=='marker_regions_then_ocr_lines' for b in report['blocks'])


@pytest.mark.parametrize('confidence',[0,.84,float('nan'),float('inf')])
def test_low_or_invalid_ocr_confidence_does_not_certify_scanned_body(tmp_path,confidence):
    pdf,pages=scanned_fixture(tmp_path)
    raw,report=transcribe_visible(pdf,pages,'scan',ocr=raster('Gain 17%.',confidence))
    assert report['issues'] and report['status']=='rejected'
    with pytest.raises(SourceExtractionError):validate_visible(report,raw,file_hash(pdf))


def test_blank_page_is_nonblocking_but_a_textless_paper_is_not_usable(tmp_path):
    original,pages=native_fixture(tmp_path)
    pdf=tmp_path/'with_blank.pdf'
    with pymupdf.open(original) as doc:
        p=doc.new_page();pages.append({'page_index':1,'bbox':list(p.rect),'regions':[]});doc.save(pdf)
    raw,report=transcribe_visible(pdf,pages,'paper',ocr=lambda *a:pytest.fail('Blank page needs no OCR'))
    assert not report['issues'] and any(w['kind']=='no_text_regions' for w in report['warnings'])
    validate_visible(report,raw,file_hash(pdf))
    with pymupdf.open() as doc:
        p=doc.new_page();doc.save(tmp_path/'blank.pdf')
    _,empty=transcribe_visible(tmp_path/'blank.pdf',[{'page_index':0,'bbox':list(pages[1]['bbox']),'regions':[]}],'')
    assert empty['issues'][0]['kind']=='no_usable_body_text'


@pytest.mark.parametrize('kind',['PageHeader','Text'])
def test_unreadable_decoration_can_be_omitted_while_unreadable_body_stops(tmp_path,kind):
    pdf,pages=native_fixture(tmp_path)
    pages[0]['regions'].append({'region_id':'missing','kind':kind,'bbox':[20,200,250,230],
                               'marker_text':'Scanned unreadable addition.'})
    raw,report=transcribe_visible(pdf,pages,'mixed',ocr=raster('unreadable',.2))
    assert bool(report['issues'])==(kind=='Text')
    if kind=='PageHeader':validate_visible(report,raw,file_hash(pdf))


@pytest.mark.parametrize('damage',['missing','overlap'])
def test_native_layout_gaps_and_ambiguity_use_whole_visible_page_without_duplicating(tmp_path,damage):
    pdf,pages=native_fixture(tmp_path)
    if damage=='missing':pages[0]['regions']=[]
    else:pages[0]['regions'].append({**pages[0]['regions'][0],'region_id':'duplicate'})
    raw,report=transcribe_visible(pdf,pages,'layout',ocr=raster('The visible finding is 17%.'))
    assert not report['issues'] and raw.count('finding')==1
    assert report['pages'][0]['method']=='visible_ocr_page'
    assert report['blocks'][0]['method']=='raster_ocr'


@pytest.mark.parametrize('damage',['text','pdf','digest','method','confidence','page'])
def test_adaptive_record_detects_corruption_including_ocr_origin(tmp_path,damage):
    pdf,pages=scanned_fixture(tmp_path)
    raw,report=transcribe_visible(pdf,pages,'scan',ocr=raster('Gain 17%.'))
    pdfhash=file_hash(pdf)
    if damage=='text':raw+=' changed'
    elif damage=='pdf':pdfhash='another paper'
    elif damage=='digest':report['blocks'][0]['text']='changed'
    else:
        if damage=='method':report['blocks'][0]['method']='scientifically_verified'
        elif damage=='page':report['pages'][0]['page']=2
        else:report['blocks'][0]['ocr_lines'][0]['confidence']=.1
        report.pop('digest');report['digest']=digest(report)
    with pytest.raises(SourceExtractionError):validate_visible(report,raw,pdfhash)


def test_failed_extraction_saves_actual_report_and_converter_input(tmp_path):
    pdf,pages=scanned_fixture(tmp_path); document=document_for(pages)
    with pytest.raises(SourceExtractionError,match='visible PDF'):
        extract_visible_text(pdf,document,'Original converter text',tmp_path,ocr=raster('bad',.1))
    assert (tmp_path/'marker_raw.md').read_text()=='Original converter text'
    assert json.loads((tmp_path/'source_extraction.json').read_text())['status']=='rejected'


@pytest.mark.parametrize('ambiguous',[False,True])
def test_caption_binding_reports_ambiguity_without_claiming_native_verification(tmp_path,ambiguous):
    block={'kind':'Caption','page':1,'region_id':'caption','pdf_bbox':[1,2,3,4],
           'marker_text':'Figure 1: The frst finding.','text':'Figure 1: The first finding.','method':'native_pdf'}
    report={'blocks':[block,deepcopy(block)] if ambiguous else [block]}
    figures={'1':{'page':0,'caption':block['marker_text']}}
    bind_visible_captions(figures,{},report,tmp_path)
    assert figures['1']['caption_source']['status']==('marker_caption_unresolved' if ambiguous else 'native_pdf_caption')
    assert figures['1']['caption']==(block['marker_text'] if ambiguous else block['text'])


@pytest.mark.parametrize('angle',[0,90,270])
def test_real_raster_adapter_uses_rendered_pixels_and_returns_pdf_coordinates(tmp_path,angle):
    pdf,_=native_fixture(tmp_path)
    with pymupdf.open(pdf) as doc:
        page=doc[0];page.set_rotation(angle);calls=[]
        def recognize(**kwargs):
            calls.append(kwargs)
            image=kwargs['images'][0]
            assert image.width*image.height<=MAX_PIXELS
            assert 'input_text' not in kwargs  # Hidden PDFium text is never fed to OCR.
            return [SimpleNamespace(text_lines=[SimpleNamespace(text='Visible text',confidence=.98,
                bbox=[0,0,image.width,image.height])])]
        converter=SimpleNamespace(artifact_dict={'recognition_model':recognize,'detection_model':object()})
        box=[20,20,250,90]
        value=RasterOCR(converter)(page,box)
        assert value['lines'][0]['bbox']==pytest.approx(box,abs=.01)
        assert value['engine']=='surya_raster' and len(value['image_hash'])==64 and len(calls)==1


def test_uniform_raster_is_not_sent_to_recognition_or_accepted_as_hallucinated_text(tmp_path):
    converter=SimpleNamespace(artifact_dict={'recognition_model':lambda **k:pytest.fail('Blank raster OCR'),
                                             'detection_model':object()})
    with pymupdf.open() as doc:
        page=doc.new_page()
        with pytest.raises(EmptyRasterRegion):RasterOCR(converter)(page,list(page.rect))


def test_uncertain_numeric_word_overrides_high_sentence_confidence(tmp_path):
    pdf,_=native_fixture(tmp_path)
    def recognize(**kwargs):
        image=kwargs['images'][0]
        return [SimpleNamespace(text_lines=[SimpleNamespace(text='Gain 17%',confidence=.99,
            words=[SimpleNamespace(text='17%',confidence=.4)],bbox=[0,0,image.width,image.height])])]
    converter=SimpleNamespace(artifact_dict={'recognition_model':recognize,'detection_model':object()})
    with pymupdf.open(pdf) as doc:
        result=RasterOCR(converter)(doc[0],[20,20,250,90])
        assert result['lines'][0]['confidence']==.4


def test_empty_raster_region_in_one_page_does_not_discard_other_pages(tmp_path):
    pdf,pages=native_fixture(tmp_path)
    pages[0]['regions'].append({'region_id':'blank','kind':'Text','bbox':[20,200,250,230],
                               'marker_text':'Incorrect converter text on blank region.'})
    def no_text(*a):raise EmptyRasterRegion('uniform')
    raw,report=transcribe_visible(pdf,pages,'paper',ocr=no_text)
    assert not report['issues'] and any(w['kind']=='empty_visible_region' for w in report['warnings'])
    assert 'Incorrect converter' not in raw


@pytest.mark.parametrize('flag',[None,False,True])
def test_foundation_failure_timing_does_not_raise_a_second_error(tmp_path,flag):
    from src.state.poster_state import ModelConfig,TimingMetrics
    from src.workflow.pipeline import save_timing_log
    state={'output_dir':str(tmp_path),'timing_metrics':TimingMetrics(pipeline_start=1,pipeline_end=11),
        'text_model':ModelConfig('text','local_text'),'vision_model':ModelConfig('vision','local_vision'),
        'generation_route':'optimization_family','editorial_version':'poster_editorial_v1',
        'errors':['Original extraction failure']}
    if flag is not None:state['joint_preparation']=flag
    result=save_timing_log(state)
    assert result['component_timing']['joint_preparation']['time_seconds']==0
    assert result['component_timing']['joint_preparation']['timing_scope']=='not_started'
    assert result['component_timing']['joint_preparation']['includes']==[]
    assert state['errors']==['Original extraction failure']


@pytest.mark.parametrize('path',['utils/editorial_pdf.py','utils/pdf_ocr.py'])
def test_paper_cache_binds_adaptive_selection_and_raster_implementation(path):
    from src.workflow.paper_cache import extraction_identity
    settings={'preparation_policy_version':'sample_editorial_v1','code_identity':{path:'before'}}
    before=extraction_identity(settings);settings['code_identity'][path]='after'
    assert before!=extraction_identity(settings)


def test_failed_parser_run_finishes_cli_with_original_error_and_real_timing(tmp_path,monkeypatch,capsys):
    from contextlib import nullcontext
    from src.workflow import exploration_cli as cli
    pdf=tmp_path/'failed.pdf';pdf.write_bytes(b'offline fixture')
    original=cli.create_state
    def create(*a,**k):
        state=original(*a,**k);state['output_dir']=str(tmp_path);return state
    class Runner:
        def __init__(self,**k):pass
        def run(self,state):
            state.update(generation_route='optimization_family',editorial_version='poster_editorial_v1',
                errors=['Unresolved visible PDF extraction'],run_state={'run_id':'run_test','finalized_samples':0,
                    'planned_samples':1,'rendered_samples':0,'scored_samples':0,'failed_samples':0,'status':'FAILED'})
            return state
    monkeypatch.setattr(cli,'create_state',create)
    monkeypatch.setattr(cli,'PosterExplorationRunner',Runner)
    monkeypatch.setattr(cli,'tee_console_output',lambda p:nullcontext())
    monkeypatch.setattr('sys.argv',['samples','--paper_path',str(pdf),'--samples','1',
                                  '--text_model','local-text','--vision_model','local-vision'])
    assert cli.main()==1
    output=capsys.readouterr().out
    assert 'FAILED' in output and 'KeyError' not in output and 'Traceback' not in output
    assert json.loads((tmp_path/'timing_cost_log.json').read_text())['component_timing']['joint_preparation']['timing_scope']=='not_started'
