"""Adaptive visible-source extraction for the current editorial route only.

Native transcription is preferred; bounded raster OCR resolves missing/broken
text and conflicting numerical readings. Diagnostics are provenance, not proof
of scientific truth. Legacy source-editorial extraction remains strict.
"""
from copy import deepcopy
from collections import Counter
from difflib import SequenceMatcher
from decimal import Decimal, InvalidOperation
import math
import re
import unicodedata

from utils.persistence import digest, file_hash, _atomic_json
from utils.source_pdf import (SourceExtractionError, marker_regions, transcribe_regions,
    extraction_environment, _comparison_text)
from utils.pdf_ocr import MIN_CONFIDENCE, EmptyRasterRegion

VERSION = 'editorial_visible_source_v2'
MAX_OCR_REGIONS_PER_PAGE = 24
DECORATIVE = {'PageHeader', 'PageFooter'}
VISUAL = {'Picture', 'Figure'}
BAD_GLYPH = re.compile(r'\(cid:\d+\)|\ufffd')
NUMBERS = re.compile(r'[+−-]?\s*(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)'
                     r'(?:[eE]\s*[+−-]?\s*\d+)?(?:\s*%)?')


def _usable(text):
    return bool(text.strip()) and not BAD_GLYPH.search(text) and not any(
        unicodedata.category(c) in {'Co', 'Cc'} and c not in '\n\t\r' for c in text)


def _fold(text):
    # Comparison only. Source characters, signs and formula layout are retained.
    return ''.join(c for c in unicodedata.normalize('NFKC', _comparison_text(text)).casefold()
                   if c.isalnum())


def _similar(a, b):
    a, b = _fold(a), _fold(b)
    # Bounded diagnostic comparison; never used to accept differing numbers.
    return SequenceMatcher(None,a[:8000],b[:8000]).ratio() >= .65


def _quantities(text):
    values = Counter()
    for token,count in Counter(re.sub(r'\s+','',m.group())
                               for m in NUMBERS.finditer(_comparison_text(text))).items():
        percent = token.endswith('%')
        number = token.rstrip('%').replace(',','').replace('−','-')
        try:
            sign,digits,exponent = Decimal(number).as_tuple()
            while len(digits)>1 and digits[-1]==0:
                digits=digits[:-1];exponent+=1
            if not any(digits):exponent=0
            number = ('decimal',sign,digits,exponent)
        except InvalidOperation:
            pass
        values[(number,percent)] += count
    return values


def _normalized_pages(pdf, pages):
    """Map displayed Marker boxes back to native PDF coordinates after rotation."""
    import pymupdf
    pages = deepcopy(pages)
    for page, layout in zip(pdf, pages):
        origin = layout['bbox']
        if (len(origin)!=4 or not all(math.isfinite(float(v)) for v in origin)
                or origin[2]<=origin[0] or origin[3]<=origin[1]):
            raise SourceExtractionError('Invalid Marker page bounds')
        sx = page.rect.width/(origin[2]-origin[0])
        sy = page.rect.height/(origin[3]-origin[1])
        for region in layout['regions']:
            a,b,c,d = region['bbox']
            rect = pymupdf.Rect((a-origin[0])*sx, (b-origin[1])*sy,
                                (c-origin[0])*sx, (d-origin[1])*sy)*page.derotation_matrix
            region['bbox'] = list(rect)
        layout['bbox'] = list(page.rect*page.derotation_matrix)
    return pages


def _ocr_block(page, region, ocr):
    if ocr is None:
        raise SourceExtractionError('Raster OCR unavailable')
    receipt = ocr(page, region['bbox'])
    lines = receipt.get('lines') if isinstance(receipt, dict) else None
    if not isinstance(lines, list) or not receipt.get('image_hash') or not receipt.get('engine'):
        raise SourceExtractionError('Raster OCR result lacks image/engine provenance')
    selected = []
    import pymupdf
    bounds = pymupdf.Rect(region['bbox'])
    for line in lines:
        text = str(line.get('text', '')).strip()
        if not text:
            continue
        confidence = float(line.get('confidence', 0))
        box = line.get('bbox')
        if (not _usable(text) or not math.isfinite(confidence) or confidence < MIN_CONFIDENCE
                or not isinstance(box, (list, tuple)) or len(box) != 4
                or not all(math.isfinite(float(v)) for v in box)
                or pymupdf.Rect(box).is_empty or not (bounds+(-.5,-.5,.5,.5)).contains(pymupdf.Rect(box))):
            raise SourceExtractionError('Low-confidence or invalid raster OCR line')
        selected.append({'text':text, 'bbox':list(pymupdf.Rect(box)&bounds), 'confidence':confidence})
    if not selected:
        raise SourceExtractionError('Raster OCR found no usable visible text')
    return {**deepcopy(region), 'page':page.number+1, 'pdf_bbox':list(region['bbox']),
        'text':'\n'.join(line['text'] for line in selected), 'native_lines':[], 'glyphs':[],
        'ocr_lines':selected, 'method':'raster_ocr',
        'ocr_receipt':{k:deepcopy(v) for k,v in receipt.items() if k != 'lines'}}


def _assemble(blocks):
    parts, offset = [], 0
    for block in blocks:
        level = block.get('heading_level')
        prefix = ('#'*min(6,max(1,level if isinstance(level,int) else 2))+' '
                  if block['kind']=='SectionHeader' else '')
        block['start'], block['end'] = offset+len(prefix), offset+len(prefix)+len(block['text'])
        parts.append(prefix+block['text']); offset += len(parts[-1])+2
    return '\n\n'.join(parts)


def _page_ocr_order(block, regions):
    """Use Marker column/region traversal without dropping any OCR line."""
    grouped = {}
    for line in block['ocr_lines']:
        a,b,c,d = line['bbox']; x,y = (a+c)/2,(b+d)/2
        owners = [(i,r) for i,r in enumerate(regions)
                  if r['bbox'][0]<=x<=r['bbox'][2] and r['bbox'][1]<=y<=r['bbox'][3]]
        if not owners:
            block['reading_order'] = 'ocr_detection_order_uncertain'
            return [block]
        index,region = min(owners,key=lambda pair:(
            (pair[1]['bbox'][2]-pair[1]['bbox'][0])*(pair[1]['bbox'][3]-pair[1]['bbox'][1]),pair[0]))
        grouped.setdefault(index,[]).append(line)
    result=[]
    for index,lines in sorted(grouped.items()):
        region=regions[index]
        result.append({**deepcopy(block), **deepcopy(region),
            'pdf_bbox':[min(l['bbox'][0] for l in lines),min(l['bbox'][1] for l in lines),
                        max(l['bbox'][2] for l in lines),max(l['bbox'][3] for l in lines)],
            'ocr_lines':lines,'text':'\n'.join(l['text'] for l in lines),
            'reading_order':'marker_regions_then_ocr_lines'})
    return result


def transcribe_visible(pdf_path, pages, marker_text, *, ocr=None):
    import pymupdf
    with pymupdf.open(pdf_path) as pdf:
        pages = _normalized_pages(pdf, pages)
    _, native = transcribe_regions(pdf_path, pages, marker_text, native_coordinates=True)
    warnings, errors, blocks, page_reports = [], [], [], []
    by_id = {(b['page'],b['region_id']):b for b in native['blocks']}
    with pymupdf.open(pdf_path) as pdf:
        for page, layout, coverage in zip(pdf, pages, native['pages']):
            page_issues = [i for i in native['issues'] if i['page']==page.number+1]
            geometrical = any(i['kind'] in {'unmapped_glyph','ambiguous_region'} for i in page_issues)
            # Invalid ownership needs an independent visible-page transcription,
            # rather than attaching missing characters to guessed prose regions.
            regions = layout['regions']
            page_fallback = geometrical or (not coverage['native_nonspace_glyphs'] and
                any(r['kind'] not in DECORATIVE|VISUAL and r.get('marker_text','').strip() for r in regions))
            page_fallback |= sum(i['kind']=='ocr_only_region' for i in page_issues)>MAX_OCR_REGIONS_PER_PAGE
            if page_fallback:
                regions = [{'region_id':f'page_{page.number+1}_visible', 'kind':'Text',
                            'bbox':list(page.rect*page.derotation_matrix), 'marker_text':''}]
                warnings.append({'page':page.number+1,'kind':'native_layout_ocr_fallback'})
            selected, ocr_calls = [], 0
            for region in regions:
                key = (page.number+1,region['region_id'])
                original = by_id.get(key)
                text = original['text'] if original else ''
                marker = region.get('marker_text','')
                cells = region.get('marker_cells')
                numeric_peer = '\n'.join(c['text'] for c in cells) if cells else marker
                issues = [i for i in page_issues if i.get('region_id')==region['region_id']]
                numeric_conflict = (any(i['kind']=='unresolved_table_or_equation_numbers' for i in issues)
                                    and _quantities(text)!=_quantities(numeric_peer))
                # Converter-only extra text is not a replacement of a native
                # value. This also handles clipped Form XObject contents leaking
                # into headers/captions in PDFium, without emitting those extras.
                extra = bool(_fold(text) and _fold(text) in _fold(marker)
                    and not (_quantities(text)-_quantities(numeric_peer)) and page.get_xobjects()
                    and not page.get_images())
                if _usable(text) and not page_fallback:
                    conflict = (_quantities(text)!=_quantities(numeric_peer) and bool(numeric_peer.strip()))
                    # Tables and equations have different decoder traversal and
                    # notation. Their numerical checks remain; prose similarity
                    # must not misclassify cell order / LaTeX as corrupt text.
                    severe = (region['kind'] not in {'Table','Equation'} and bool(marker.strip())
                              and not _similar(text,marker) and not extra)
                    if (not numeric_conflict and (not conflict or extra or region['kind'] in DECORATIVE)
                            and not severe):
                        selected.append({**deepcopy(original), 'method':'native_pdf'})
                        if issues or _fold(text)!=_fold(marker):
                            warnings.append({'page':page.number+1,'region_id':region['region_id'],
                                'kind':'native_preferred_converter_extra' if extra else 'native_preferred_text_disagreement',
                                'native_text':text, 'marker_text':marker})
                        continue
                elif not text and (not marker.strip() or region['kind'] in VISUAL) and not page_fallback:
                    continue
                try:
                    if ocr_calls >= MAX_OCR_REGIONS_PER_PAGE:
                        raise SourceExtractionError('Per-page raster OCR region budget exhausted')
                    ocr_calls += 1
                    recovered = _ocr_block(page, region, ocr)
                    if _usable(text):
                        # Numerical substitutions require raster agreement with
                        # one decoder. Never resolve them by similarity or voting
                        # on prose alone. The independent OCR remains recorded.
                        numbers = _quantities(recovered['text'])
                        if numbers == _quantities(text) and _similar(text,recovered['text']):
                            chosen = {**deepcopy(original), 'method':'native_pdf',
                                      'ocr_receipt':recovered['ocr_receipt'], 'ocr_lines':recovered['ocr_lines']}
                        elif numbers == _quantities(numeric_peer) and _fold(recovered['text']) == _fold(marker):
                            chosen = recovered
                        else:
                            raise SourceExtractionError('Visible OCR cannot resolve numerical disagreement')
                    else:
                        chosen = recovered
                    ordered = _page_ocr_order(chosen,layout['regions']) if page_fallback else [chosen]
                    selected.extend(ordered)
                    if any(b.get('reading_order')=='ocr_detection_order_uncertain' for b in ordered):
                        warnings.append({'page':page.number+1,'region_id':region['region_id'],
                                         'kind':'ocr_reading_order_uncertain'})
                    warnings.append({'page':page.number+1,'region_id':region['region_id'],
                        'kind':'visible_ocr_reconciled','selected_method':chosen['method']})
                except EmptyRasterRegion:
                    warnings.append({'page':page.number+1,'region_id':region['region_id'],
                                     'kind':'empty_visible_region'})
                except (SourceExtractionError, ValueError, RuntimeError) as exc:
                    item = {'page':page.number+1,'region_id':region['region_id'],
                            'kind':'unresolved_visible_region','reason':str(exc), 'bbox':region['bbox']}
                    (warnings if region['kind'] in DECORATIVE else errors).append(item)
            blocks.extend(selected)
            page_reports.append({**coverage, 'rotation':page.rotation, 'ocr_calls':ocr_calls,
                'selected_regions':len(selected), 'method':'visible_ocr_page' if page_fallback else 'region_selection'})
            if not selected and not any(e['page']==page.number+1 for e in errors):
                warnings.append({'page':page.number+1, 'kind':'no_text_regions',
                                 'reason':'Blank or visual-only page; assets remain available to Parser'})
    raw = _assemble(blocks)
    if not any(b['kind'] not in DECORATIVE and _usable(b['text']) for b in blocks):
        errors.append({'page':0,'kind':'no_usable_body_text'})
    report = {'version':VERSION,'status':'rejected' if errors else 'extracted_with_warnings' if warnings else 'extracted',
        'environment':dict(extraction_environment()), 'pdf_hash':file_hash(pdf_path),
        'marker_digest':digest(marker_text),'text_digest':digest(raw),'pages':page_reports,
        'blocks':blocks,'issues':errors,'warnings':warnings,'native_diagnostics':native['issues'],
        'font_recoveries':native['font_recoveries'],
        'limits':{'ocr_regions_per_page':MAX_OCR_REGIONS_PER_PAGE,'minimum_ocr_confidence':MIN_CONFIDENCE,
                  'scientific_truth_verified':False}}
    report['digest'] = digest(report)
    return raw, report


def validate_visible(report, raw, pdf_hash):
    body = deepcopy(report or {}); expected = body.pop('digest', None)
    if (body.get('version')!=VERSION or body.get('status') not in {'extracted','extracted_with_warnings'}
            or body.get('issues') or body.get('environment')!=extraction_environment()
            or expected!=digest(body) or body.get('text_digest')!=digest(raw)
            or body.get('pdf_hash')!=pdf_hash or not body.get('pages') or not body.get('blocks')):
        raise SourceExtractionError('Missing, corrupt or unresolved visible-source extraction record')
    rebuilt = _assemble(deepcopy(body['blocks']))
    if rebuilt != raw or any(b.get('method') not in {'native_pdf','raster_ocr'} for b in body['blocks']):
        raise SourceExtractionError('Selected source blocks differ from emitted text')
    if [p['page'] for p in body['pages']] != list(range(1,len(body['pages'])+1)):
        raise SourceExtractionError('Visible-source page coverage is inconsistent')
    for block in body['blocks']:
        if not _usable(block['text']) or block['page'] not in {p['page'] for p in body['pages']}:
            raise SourceExtractionError('Invalid selected visible-source block')
        if block['method']=='native_pdf' and not block.get('glyphs'):
            raise SourceExtractionError('Native source block lost its glyph provenance')
        if (block['method']=='raster_ocr' or block.get('ocr_receipt')) and (
                not block.get('ocr_receipt',{}).get('image_hash') or not block['ocr_receipt'].get('engine')
                or not block.get('ocr_lines') or any(
                    not math.isfinite(l.get('confidence',0)) or l.get('confidence',0)<MIN_CONFIDENCE
                    for l in block['ocr_lines'])):
            raise SourceExtractionError('OCR source block lost its raster provenance or confidence')
    return report


def quality_summary(report):
    if not report or report.get('version')!=VERSION:
        return None
    return {'version':VERSION,'status':report['status'],
        'selected_methods':dict(Counter(b['method'] for b in report['blocks'])),
        'warning_count':len(report['warnings']),
        'warnings':[{'page':i.get('page'),'region_id':i.get('region_id'),'kind':i['kind']}
                    for i in report['warnings'][:100]],
        'warnings_truncated':len(report['warnings'])>100,
        'scientific_truth_verified':False,
        'instructions':'OCR and native selections are extraction results, not scientific verification. '
            'Do not invent missing text or treat unresolved caption metadata as a verified original caption.'}


def extract_visible_text(pdf_path, document, marker_text, content_dir, *, ocr=None):
    from pathlib import Path
    directory = Path(content_dir)
    (directory/'marker_raw.md').write_text(marker_text, encoding='utf-8')
    try:
        raw, report = transcribe_visible(pdf_path, marker_regions(document), marker_text, ocr=ocr)
    except SourceExtractionError as exc:
        _atomic_json(directory/'source_extraction.json', {'version':VERSION,'status':'rejected',
            'pdf_hash':file_hash(pdf_path),'issues':[{'kind':'invalid_region_layout','reason':str(exc)}]})
        raise
    _atomic_json(directory/'source_extraction.json', report)
    if report['issues']:
        raise SourceExtractionError(f"Unresolved visible PDF extraction: {len(report['issues'])} issue(s); {report['issues'][0]}")
    validate_visible(report, raw, file_hash(pdf_path))
    return raw, report


def bind_visible_captions(figures, tables, report, content_dir):
    """Bind unique selected captions; retain ambiguous metadata with diagnostics."""
    from pathlib import Path
    audit = []
    for prefix, assets in (('figure',figures),('table',tables)):
        for key, asset in assets.items():
            caption = asset.get('caption',''); page = asset.get('page')
            matches = [b for b in report['blocks'] if b['kind'] in {'Caption','Footnote','Text'}
                and ' '.join(b.get('marker_text','').split())==' '.join(caption.split())
                and (page is None or b['page']==page+1)]
            if len(matches)==1:
                b = matches[0]; asset['caption'] = b['text']
                asset['caption_source'] = {'status':b['method']+'_caption','page':b['page'],
                                          'region_id':b['region_id'],'bbox':b['pdf_bbox']}
            else:
                asset['caption_source'] = {'status':'marker_caption_unresolved',
                    'reason':'missing' if not matches else 'ambiguous'}
            audit.append({'visual_id':prefix+'_'+str(key),'marker_caption':caption,
                          'caption':asset['caption'],'source':asset['caption_source']})
    _atomic_json(Path(content_dir)/'asset_caption_audit.json',{'version':VERSION,'captions':audit})
