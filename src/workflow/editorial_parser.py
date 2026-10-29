"""Upstream-style model material preparation, with durable request receipts."""
from src.workflow.editorial_requests import obj, STRING, STRINGS, request


def title_authors(state, text):
    value = request(state, 'editorial_metadata', {'original_text':text},
                    obj({'title':STRING,'authors':STRING}), directory='editorial/paper/metadata')
    if not value['title'].strip() or not value['authors'].strip():
        from src.workflow.editorial_contract import EditorialOutputError
        raise EditorialOutputError('Empty paper title/authors')
    return value['title'], value['authors']


def narrative(state, text):
    def validate(value):
        from src.workflow.editorial_contract import EditorialStructureError
        missing=[(key,) for key,text in value.items() if not text.strip()]
        if missing:raise EditorialStructureError('ABT fields must contain useful paper material',missing)
    return request(state, 'editorial_abt', {'original_text':text}, obj({k:STRING for k in
        ('and','but','therefore','poster_hook','key_impact')}), directory='editorial/paper/abt',validator=validate)


def sections(state, text):
    section = obj({'section_name':STRING,'section_type':{'enum':['foundation','method','evaluation','discussion','other'],
        'type':'string'},'content':STRING,'key_points':STRINGS,'importance':{'type':'string','enum':['high','medium','low']},
        'contains_figures':STRINGS,'contains_tables':STRINGS})
    def validate(value):
        from src.workflow.editorial_contract import EditorialOutputError
        if any(not s['content'].strip() or not s['section_name'].strip() for s in value['paper_sections']):
            raise EditorialOutputError('Empty model-organized paper section')
    return request(state, 'editorial_sections', {'original_text':text},
        obj({'paper_sections':{'type':'array','items':section,'minItems':1}}),
        directory='editorial/paper/sections', validator=validate)


def classify(state, figures, tables, text):
    from src.agents.visual_classification import ROLE_FIELDS, normalize_visual_classification
    visuals = [{'id':f'{prefix}_{key}','caption':a.get('caption',''),'aspect_ratio':a.get('aspect',1)}
               for prefix, assets in (('figure',figures),('table',tables)) for key,a in assets.items()]
    if not visuals:
        value, audit = normalize_visual_classification(None, [], source='no_visual_assets')
    else:
        raw = request(state, 'editorial_visuals', {'original_text':text,'visuals':visuals},
            obj({'key_visual':{'type':['string','null']}, **{role:STRINGS for role in ROLE_FIELDS}}),
            directory='editorial/paper/visuals')
        value, audit = normalize_visual_classification(raw, visuals, source='model')
    state['visual_classification_report'] = audit
    return value
