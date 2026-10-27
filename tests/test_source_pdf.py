"""Literal PDF extraction and exact paragraph binding; no model/GPU calls."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pymupdf
import pytest

from utils.source_pdf import (transcribe_regions, marker_regions, extract_source_text,
                              validate_extraction, SourceExtractionError)
from utils.persistence import digest, file_hash
from src.workflow.source_document import (build_document, bind_paragraph_refs,
    paragraph_hints, validate_refs, locate_refs, SourceProtocolError)


def native_fixture(tmp_path, lines=None):
    pdf=tmp_path/'native.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page()
        for x,y,text in lines or [(30,50,'The first finding significantly improves efficacy by 3%-17%.')]:
            page.insert_text((x,y),text,fontsize=10)
        doc.save(pdf)
    with pymupdf.open(pdf) as doc:
        pages=[{'page_index':i,'bbox':list(p.rect),'regions':[
            {'region_id':f'{i}:{j}','kind':'Text','heading_level':None,'bbox':list(b[:4]),
             'marker_text':b[4].replace('fi','f')} for j,b in enumerate(p.get_text('blocks')) if b[6]==0]}
            for i,p in enumerate(doc)]
    return pdf,pages


def test_native_glyphs_restore_actual_pdf_letters_without_dictionary_repair(tmp_path):
    pdf,pages=native_fixture(tmp_path)
    raw,report=transcribe_regions(pdf,pages,'The frst fnding signifcantly improves effcacy by 3%-17%.')
    assert 'first finding significantly improves efficacy' in raw
    assert '3%-17%' in raw and not report['issues']
    assert report['blocks'][0]['marker_text']!=report['blocks'][0]['text']
    assert report['blocks'][0]['glyphs'] and validate_extraction(report,raw,file_hash(pdf))
    state={'raw_text':raw,'pdf_path':str(pdf),'source_extraction_report':report}
    doc=build_document(state)
    assert doc['units'][0]['source_location']['pdf_regions'][0]['page']==1


def test_does_not_correct_a_typo_actually_present_in_pdf(tmp_path):
    pdf,pages=native_fixture(tmp_path,[(30,50,'The frst result is udpated, not updated.')])
    pages[0]['regions'][0]['marker_text']='The first result is updated, not updated.'
    raw,report=transcribe_regions(pdf,pages,'The first result is updated, not updated.')
    assert 'frst' in raw and 'udpated' in raw
    assert report['status']=='rejected' and report['issues'][0]['kind']=='unresolved_text_disagreement'


def test_region_order_preserves_column_traversal_not_pdf_creation_order(tmp_path):
    pdf,pages=native_fixture(tmp_path,[(320,50,'RIGHT column result: 70%.'),(30,50,'LEFT column setup: 5%.')])
    pages[0]['regions']=[{'region_id':side,'kind':'Text','heading_level':None,
        'bbox':box,'marker_text':text} for side,box,text in [('LEFT',[0,0,280,100],'LEFT column setup: 5%.'),('RIGHT',[300,0,590,100],'RIGHT column result: 70%.')]]
    raw,report=transcribe_regions(pdf,pages,'LEFT then RIGHT')
    assert raw.index('LEFT')<raw.index('RIGHT') and not report['issues']
    assert all(p['native_nonspace_glyphs']==p['assigned_nonspace_glyphs'] for p in report['pages'])


@pytest.mark.parametrize('damage',['omitted_region','overlap','empty_text_layer','ocr_only_region'])
def test_unresolved_native_source_never_gets_an_accepted_proof(tmp_path,damage):
    pdf,pages=native_fixture(tmp_path)
    if damage=='omitted_region':pages[0]['regions']=[]
    if damage=='overlap':pages[0]['regions'].append({**pages[0]['regions'][0],'region_id':'duplicate'})
    if damage=='empty_text_layer':
        blank=tmp_path/'scan.pdf'
        with pymupdf.open() as doc:
            doc.new_page();doc.save(blank)
        pdf=blank
    if damage=='ocr_only_region':
        pages[0]['regions'].append({'region_id':'ocr','kind':'Text','heading_level':None,
                                  'bbox':[30,150,250,200],'marker_text':'An OCR-only claim with 99%.'})
    raw,report=transcribe_regions(pdf,pages,'untrusted OCR')
    assert report['issues'] and report['status']=='rejected'
    with pytest.raises(SourceExtractionError):validate_extraction(report,raw,file_hash(pdf))


@pytest.mark.parametrize('damage',['text','pdf','digest','coverage'])
def test_proof_binds_complete_text_pdf_and_glyph_coverage(tmp_path,damage):
    pdf,pages=native_fixture(tmp_path)
    raw,report=transcribe_regions(pdf,pages,'original')
    pdfhash=file_hash(pdf)
    if damage=='text':raw+=' unsupported addition'
    if damage=='pdf':pdfhash='other PDF'
    if damage=='digest':report['blocks'][0]['text']='Changed'
    if damage=='coverage':
        report['pages'][0]['assigned_nonspace_glyphs']-=1
        report.pop('digest');report['digest']=digest(report)
    with pytest.raises(SourceExtractionError):validate_extraction(report,raw,pdfhash)


def test_program_copies_quotes_and_preserves_case_and_real_typos(tmp_path):
    doc=build_document({'raw_text':'# Method\n\nwe use the frst result.\n\nThe gain is 3%, not 70%.'})
    source=doc['units'][0]['source_id']
    ref={'source_id':source,'paragraph_ids':[source+':p1']}
    bound=bind_paragraph_refs({'source_refs':[ref]},doc)
    assert bound['source_refs'][0]['quote']=='we use the frst result.'
    assert paragraph_hints(bound,doc)=={'source_refs':[ref]}
    assert validate_refs(bound['source_refs'],doc)
    assert locate_refs(bound['source_refs'],doc)[0]['matches'][0]['original_quote']=='we use the frst result.'
    forged=deepcopy(bound['source_refs']);forged[0]['quote']='We use the first result.'
    with pytest.raises(ValueError):validate_refs(forged,doc)


@pytest.mark.parametrize('ids',[['src_00001:p9'],['src_00002:p1'],['src_00001:p1','src_00001:p1'],[]])
def test_invalid_paragraph_locations_are_not_guessed(tmp_path,ids):
    doc=build_document({'raw_text':'# Method\n\nOriginal supported meaning.'})
    with pytest.raises(SourceProtocolError):
        bind_paragraph_refs({'source_refs':[{'source_id':'src_00001','paragraph_ids':ids}]},doc)


def test_repeated_paragraph_quote_keeps_selected_actual_location(tmp_path):
    doc=build_document({'raw_text':'# Method\n\nRepeated statement.\n\nRepeated statement.'})
    ref=bind_paragraph_refs({'source_refs':[{'source_id':'src_00001','paragraph_ids':['src_00001:p2']}]},doc)['source_refs']
    location=locate_refs(ref,doc)[0]
    assert location['location_status']=='located'
    assert location['matches'][0]['paragraph_ids']==['src_00001:p2']


def test_groups_keep_children_order_and_rescale_page_coordinates(tmp_path):
    pdf,pages=native_fixture(tmp_path)
    box=pages[0]['regions'][0]['bbox']
    child=SimpleNamespace(block_type=SimpleNamespace(name='Text'),structure=[],polygon=SimpleNamespace(bbox=[x*2 for x in box]),
                          heading_level=None,raw_text=lambda doc:'The frst fnding signifcantly improves effcacy by 3%-17%.')
    group=SimpleNamespace(block_type=SimpleNamespace(name='ListGroup'),structure=['child'])
    page=SimpleNamespace(page_id=0,structure=['group'],polygon=SimpleNamespace(bbox=[x*2 for x in pages[0]['bbox']]),
                         get_block=lambda key:{'child':child,'group':group}[key])
    document=SimpleNamespace(pages=[page])
    raw,report=extract_source_text(pdf,document,'marker output',tmp_path)
    assert not report['issues'] and 'first finding' in raw
    assert (tmp_path/'marker_raw.md').read_text()=='marker output'
    assert json.loads((tmp_path/'source_extraction.json').read_text())['digest']==report['digest']


def test_pdf_source_requires_extraction_proof_before_document_freeze(tmp_path):
    pdf,_=native_fixture(tmp_path)
    with pytest.raises(SourceExtractionError,match='proof'):
        build_document({'pdf_path':str(pdf),'raw_text':'Unverified text'})


def test_one_locator_repair_cannot_change_story_and_is_durable(tmp_path,monkeypatch):
    from test_source_editorial import source_state, Agent
    import src.workflow.source_editorial as editorial
    state=source_state(tmp_path)
    wire=paragraph_hints(state['source_narrative_plan'],state['source_document'])
    bad=deepcopy(wire);bad['sections'][0]['source_refs'][0]['paragraph_ids']=['src_00001:p999']
    agent=Agent(json.dumps(bad),json.dumps(wire))
    monkeypatch.setattr(editorial,'agent_for',lambda *a,**kw:agent)
    editorial.source_narrative_node(state)
    assert len(agent.calls)==2
    root=Path(state['sample_preparation_dir'])
    assert (root/'source_format_correction.json').is_file()
    assert (root/'source/narrative/parsed_00.json').is_file()
    assert (root/'source/narrative/bound_01.json').is_file()
    assert state['source_narrative_plan']['sections'][0]['source_refs'][0]['quote'].startswith('A shared policy')
    # Replay reads the exact charged responses without additional calls.
    editorial.source_narrative_node(state)
    assert len(agent.calls)==2


def test_locator_recovery_cannot_rewrite_prose_or_valid_neighbor(tmp_path):
    from test_source_editorial import source_state, Agent
    from src.workflow.source_requests import SourceRequests
    from src.workflow.source_editorial import CANDIDATE_SCHEMA
    state=source_state(tmp_path,count=2)
    wire=paragraph_hints({'modules':state['source_candidate']['modules']},state['source_document'])
    bad=deepcopy(wire);bad['modules'][0]['source_refs'][0]['paragraph_ids']=['src_00001:p999']
    repaired=deepcopy(wire);repaired['modules'][0]['entries'][0]['text']='A newly rewritten scientific explanation.'
    agent=Agent(json.dumps(bad),json.dumps(repaired))
    journal=SourceRequests(state,'source/locator_repair','task',CANDIDATE_SCHEMA)
    with pytest.raises(SourceProtocolError,match='no remaining'):
        journal.call(agent)
    assert len(agent.calls)==2 and (journal.root/'validation_01.json').is_file()


def test_explicit_false_science_never_spends_locator_recovery(tmp_path):
    from test_source_editorial import source_state, Agent, verdict_for
    from src.workflow.source_requests import SourceRequests
    from src.workflow.source_verification import VERDICT_SCHEMA, validate_verdict_protocol, targets_for
    state=source_state(tmp_path,count=1);module=state['source_candidate']['modules'][0]
    verdict=paragraph_hints(verdict_for(module,state),state['source_document'])
    verdict['coverage'][0]['supported']=False
    verdict['coverage'][0]['source_refs'][0]['paragraph_ids']=['src_00001:p999']
    agent=Agent(json.dumps(verdict))
    result=SourceRequests(state,'source/rejected','task',VERDICT_SCHEMA).call(agent,
        lambda v:validate_verdict_protocol(module,v,state['source_document'],targets_for(module)))
    assert result['coverage'][0]['supported'] is False and len(agent.calls)==1
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()


@pytest.mark.parametrize('changed',['70% instead of 3%-17%.','-3%-17%.','3%-70%.'])
def test_conflicting_scientific_numbers_block_preparation(tmp_path,changed):
    pdf,pages=native_fixture(tmp_path)
    pages[0]['regions'][0]['marker_text']='The first finding significantly improves efficacy by '+changed
    _,report=transcribe_regions(pdf,pages,'converter result')
    assert any(i['kind']=='unresolved_text_disagreement' for i in report['issues'])


def test_printed_typo_is_preserved_when_both_decoders_agree(tmp_path):
    pdf,pages=native_fixture(tmp_path,[(30,50,'The frst result is udpated.')])
    pages[0]['regions'][0]['marker_text']='The frst result is udpated.'
    raw,report=transcribe_regions(pdf,pages,'The frst result is udpated.')
    assert not report['issues'] and 'frst' in raw and 'udpated' in raw


def test_actual_marker_schema_accepts_native_region_transcription(tmp_path):
    from marker.schema.blocks import Text
    from marker.schema.groups.page import PageGroup
    from marker.schema.document import Document
    from marker.schema.polygon import PolygonBox
    pdf,pages=native_fixture(tmp_path)
    def polygon(box):
        a,b,c,d=box
        return PolygonBox(polygon=[[a,b],[c,b],[c,d],[a,d]])
    child=Text(polygon=polygon(pages[0]['regions'][0]['bbox']),page_id=0,block_id=0)
    page=PageGroup(polygon=polygon(pages[0]['bbox']),page_id=0,children=[child],structure=[child.id])
    document=Document(filepath=str(pdf),pages=[page])
    raw,report=extract_source_text(pdf,document,'The frst result',tmp_path)
    assert not report['issues'] and 'first finding' in raw


@pytest.mark.parametrize('glyph,expected',[('braceleftbigg','{'),('parenleftbig','('),('parenrightbig',')'),('unknownscientificglyph',None)])
def test_control_codes_decode_only_from_embedded_exact_glyph_identity(glyph,expected):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from utils.source_pdf import _decode_named_glyph
    names=['.notdef',glyph]
    builder=FontBuilder(1000,isTTF=False)
    builder.setupGlyphOrder(names);builder.setupCharacterMap({26:glyph})
    strings={name:T2CharStringPen(600,None).getCharString() for name in names}
    builder.setupCFF('Test-Regular',{'FullName':'Test Regular','FamilyName':'Test','Weight':'Regular'},strings,{})
    data=builder.font['CFF '].compile(builder.font)
    pdf=SimpleNamespace(extract_font=lambda xref:('Subset+Test','cff','Type1',data))
    page=SimpleNamespace(number=0,get_fonts=lambda **kw:[(7,'cff','Type1','Subset+Test','F1','',0)],
        get_texttrace=lambda:[{'font':'Test','chars':[(65533,1,(10.,20.),(10.,10.,20.,20.))]}])
    result=_decode_named_glyph(pdf,page,'Test',{'c':'\x1a','origin':(10.,20.),'bbox':(10.,10.,20.,20.)},{})
    if expected is None:assert result is None
    else:
        assert result['text']==expected and result['glyph_name']==glyph and result['glyph_id']==1
        assert result['font_xref']==7 and result['original_text']=='\x1a'


@pytest.mark.parametrize('source_mode',[False,True])
def test_parser_uses_native_source_before_any_model_and_keeps_classic_independent(tmp_path,monkeypatch,source_mode):
    from src.agents.parser import Parser
    from src.state.poster_state import TokenUsage
    import utils.source_pdf as native
    parser=Parser.__new__(Parser);parser.name='parser'
    marker='The frst fnding.';canonical='The first finding.'
    monkeypatch.setattr(parser,'_extract_raw_text',lambda *a:(marker,('document',None,{})))
    monkeypatch.setattr(parser,'_extract_assets',lambda *a:({},{}))
    monkeypatch.setattr(parser,'_cleanup_unused_assets',lambda *a:None)
    expected=canonical if source_mode else marker
    def title(raw,*a):
        assert raw==expected
        return 'Paper','Authors'
    monkeypatch.setattr(parser,'_extract_title_authors',title)
    monkeypatch.setattr(parser,'_classify_visual_assets',lambda figures,tables,raw,*a:({},0,0) if raw==expected else pytest.fail('Wrong source'))
    monkeypatch.setattr(parser,'_generate_narrative_content',lambda *a:({},0,0))
    monkeypatch.setattr(parser,'_extract_structured_sections',lambda raw,*a:{} if raw==expected else pytest.fail('Wrong sections'))
    called=[]
    def extract(*a):
        called.append(True);return canonical,{'diagnostic':'synthetic parser boundary test','blocks':[]}
    monkeypatch.setattr(native,'extract_source_text',extract)
    state={'pdf_path':'diagnostic.pdf','output_dir':str(tmp_path),'poster_name':'test','tokens':TokenUsage(),
        'text_model':None,'errors':[], 'source_editorial_version':'source_editorial_v1' if source_mode else None,
        'generation_route':'optimization_family' if source_mode else 'classic'}
    parser(state)
    assert not state['errors'] and state['raw_text']==expected and bool(called)==source_mode


def test_parser_stops_before_model_calls_when_extraction_is_uncertain(tmp_path,monkeypatch):
    from src.agents.parser import Parser
    import utils.source_pdf as native
    parser=Parser.__new__(Parser);parser.name='parser'
    monkeypatch.setattr(parser,'_extract_raw_text',lambda *a:('uncertain text',('document',None,{})))
    def fail(*a):raise SourceExtractionError('Unresolved original PDF glyph')
    monkeypatch.setattr(native,'extract_source_text',fail)
    monkeypatch.setattr(parser,'_extract_title_authors',lambda *a:pytest.fail('No model after bad source'))
    state={'pdf_path':'diagnostic.pdf','output_dir':str(tmp_path),'source_editorial_version':'source_editorial_v1','errors':[]}
    parser(state)
    assert state['errors']==['Unresolved original PDF glyph']


@pytest.mark.parametrize('field',['coverage','fully_expressed','meaning_source_supported'])
def test_negative_verdict_fields_reject_science_without_locator_repair(tmp_path,field):
    from test_source_editorial import source_state, Agent, verdict_for
    from src.workflow.source_requests import SourceRequests
    from src.workflow.source_verification import VERDICT_SCHEMA,validate_verdict_protocol,check_module_verdict,targets_for
    from src.workflow.source_document import SourceOutputError
    state=source_state(tmp_path,count=1);module=state['source_candidate']['modules'][0]
    value=paragraph_hints(verdict_for(module,state),state['source_document'])
    if field=='coverage':value['coverage'][-1]['supported']=False
    else:value['obligations'][0][field]=False
    value['coverage'][0]['source_refs'][0]['paragraph_ids']=['src_00001:p999']
    agent=Agent(json.dumps(value));targets=targets_for(module)
    verdict=SourceRequests(state,'source/negative_field','task',VERDICT_SCHEMA).call(agent,
        lambda v:validate_verdict_protocol(module,v,state['source_document'],targets))
    with pytest.raises(SourceOutputError) as result:
        check_module_verdict(module,verdict,state['source_document'],targets,{'core':{}})
    assert not isinstance(result.value,SourceProtocolError)
    assert len(agent.calls)==1
    assert not (Path(state['sample_preparation_dir'])/'source_format_correction.json').exists()


def test_locator_recovery_preserves_other_valid_reference_fields(tmp_path,monkeypatch):
    from test_source_editorial import source_state,Agent
    import src.workflow.source_editorial as editorial
    state=source_state(tmp_path)
    wire=paragraph_hints(state['source_narrative_plan'],state['source_document'])
    bad=deepcopy(wire);bad['sections'][0]['source_refs'][0]['paragraph_ids']=['src_00001:p999']
    repaired=deepcopy(wire);repaired['obligations'][0]['source_refs'][0]['paragraph_ids']=['src_00001:p1']
    agent=Agent(json.dumps(bad),json.dumps(repaired))
    monkeypatch.setattr(editorial,'agent_for',lambda *a,**kw:agent)
    with pytest.raises(SourceProtocolError,match='no remaining'):
        editorial.source_narrative_node(state)
    assert len(agent.calls)==2


def test_source_rechecks_actual_pdf_identity_after_extraction(tmp_path):
    from src.workflow.source_document import source_material
    pdf,pages=native_fixture(tmp_path)
    raw,report=transcribe_regions(pdf,pages,'converter')
    doc=build_document({'pdf_path':str(pdf),'raw_text':raw,'source_extraction_report':report})
    pdf.write_bytes(b'a different paper')
    with pytest.raises(ValueError,match='PDF changed'):
        source_material({'source_document':doc,'pdf_path':str(pdf)})


def test_formula_and_table_source_retains_literal_line_positions(tmp_path):
    from src.workflow.source_document import source_material
    pdf,pages=native_fixture(tmp_path,[(30,50,'Budget 15: HAGS 3%, baseline 2%.'),(30,80,'Budget 20: HAGS 17%, baseline 9%.')])
    for region in pages[0]['regions']:region['kind']='Table'
    raw,report=transcribe_regions(pdf,pages,'converter table')
    doc=build_document({'pdf_path':str(pdf),'raw_text':raw,'source_extraction_report':report})
    material=source_material({'source_document':doc})
    lines=[line for unit in material['units'] for region in unit['pdf_layout'] for line in region['lines']]
    assert any('Budget 15' in line['text'] for line in lines)
    assert any('Budget 20' in line['text'] for line in lines)
    assert all(len(line['bbox'])==4 for line in lines)


def test_native_caption_binding_uses_same_page_exact_region_and_no_spelling_guesses(tmp_path):
    from utils.source_pdf import bind_asset_captions
    figures={'1':{'page':0,'caption':'Figure 1: The frst fnding.'}}
    report={'blocks':[{'kind':'Caption','page':1,'region_id':'caption','pdf_bbox':[1,2,3,4],
        'marker_text':'Figure 1: The frst fnding.','text':'Figure 1: The first finding.'}]}
    bind_asset_captions(figures,{},report,tmp_path)
    assert figures['1']['caption']=='Figure 1: The first finding.'
    assert figures['1']['caption_source']['page']==1
    report['blocks'].append(deepcopy(report['blocks'][0]))
    with pytest.raises(SourceExtractionError,match='ambiguous'):
        bind_asset_captions({'1':{'page':0,'caption':'Figure 1: The frst fnding.'}},{},report,tmp_path)


def test_table_numbers_keep_cell_boundaries_and_reject_changed_values(tmp_path):
    pdf,pages=native_fixture(tmp_path,[(30,50,'3.00 17.00')])
    region=pages[0]['regions'][0];region['kind']='Table'
    region['marker_text']='3.0017.00'
    region['marker_cells']=[{'text':'3.00'},{'text':'17.00'}]
    _,report=transcribe_regions(pdf,pages,'table')
    assert not report['issues']
    region['marker_cells'][1]['text']='70.00'
    _,report=transcribe_regions(pdf,pages,'table')
    assert any(i['kind']=='unresolved_table_or_equation_numbers' for i in report['issues'])


def test_number_comparison_handles_sign_spacing_and_never_joins_neighbors():
    from utils.source_pdf import _numbers
    assert _numbers('Authors1, Authors34, result −1 and 5%.')==_numbers('Authors1\n, Authors34\n, result − 1 and 5 %.')
    assert _numbers('5 10')!=_numbers('510')
    assert _numbers('3.00\n17.00')==_numbers('3.00\t17.00')


@pytest.mark.parametrize('source,accepted',[
    ('In particular, improvement ranges\nfrom 3%-17% over the most competitive baseline.',True),
    ('The improvement ranges from 3% - 17%.',True),
    ('The improvement is 3% to 17%.',True),
    ('Subtract 3%-17%.',False),
    ('The improvement ranges from -3%-17%.',False),
    ('The improvement ranges from 3%--17%.',False),
    ('The improvement ranges from 3%−17%.',False),
    ('The improvement ranges from 3-17%.',False),
])
def test_only_explicit_original_unsigned_percent_range_supports_paraphrase(source,accepted):
    from src.workflow.source_verification import numeric_support
    assert numeric_support('The improvement is 3% to 17%.',[{'quote':source}]) is accepted
    assert not numeric_support('The improvement is 3% to 18%.',[{'quote':source}])


def test_scientific_rejection_during_locator_recovery_is_recorded_as_rejection(tmp_path):
    from test_source_editorial import source_state,Agent,verdict_for
    from src.workflow.source_requests import SourceRequests
    from src.workflow.source_verification import VERDICT_SCHEMA,validate_verdict_protocol,targets_for
    state=source_state(tmp_path,count=1);module=state['source_candidate']['modules'][0]
    initial=paragraph_hints(verdict_for(module,state),state['source_document'])
    initial['coverage'][0]['source_refs'][0]['paragraph_ids']=['src_00001:p999']
    rejected=deepcopy(initial);rejected['status']='insufficient_source'
    agent=Agent(json.dumps(initial),json.dumps(rejected))
    journal=SourceRequests(state,'source/locator_negative','task',VERDICT_SCHEMA)
    result=journal.call(agent,lambda v:validate_verdict_protocol(module,v,state['source_document'],targets_for(module)))
    assert result['status']=='insufficient_source' and len(agent.calls)==2
    assert json.loads((journal.root/'verdict.json').read_text())['payload']['parsed']['status']=='insufficient_source'
