"""Literal PDF text for the source-editorial route, with region/glyph provenance.

Marker supplies regions and their order, never the authoritative characters. No
OCR, dictionary repair, fuzzy acceptance or model call occurs here. A usable PDF
text layer is required; unresolved extraction stops before scientific writing.
"""
from collections import Counter
from pathlib import Path
import io
from importlib.metadata import version, PackageNotFoundError
from functools import lru_cache
import math
import re
import unicodedata

from utils.persistence import digest, file_hash, _atomic_json

EXTRACTION_VERSION = 'pdf_native_regions_v1'


@lru_cache(maxsize=1)
def extraction_environment():
    result={}
    for package in ('PyMuPDF','fonttools','marker-pdf','pdftext','surya-ocr'):
        try:
            result[package]=version(package)
        except PackageNotFoundError:
            result[package]='not_installed'
    return result


class SourceExtractionError(ValueError):
    pass


def _bbox(obj):
    polygon = getattr(obj, 'polygon', None)
    box = getattr(polygon, 'bbox', None)
    if box is None or len(box) != 4 or not all(math.isfinite(float(x)) for x in box):
        raise SourceExtractionError('Marker region has no finite PDF-coordinate bounds')
    return tuple(float(x) for x in box)


def _kind(block):
    value = getattr(block, 'block_type', '')
    return getattr(value, 'name', str(value).split('.')[-1])


def marker_regions(document):
    """Retain Marker traversal; recurse groups, not table/equation internals."""
    pages = []
    for page in document.pages:
        regions, seen = [], set()
        def visit(block_id):
            key = str(block_id)
            if key in seen:
                raise SourceExtractionError('Duplicate/cyclic Marker region: '+key)
            seen.add(key)
            block = page.get_block(block_id)
            kind = _kind(block)
            children = getattr(block, 'structure', None) or []
            if children and kind.endswith('Group'):
                for child in children:
                    visit(child)
                return
            record={'region_id': key, 'kind': kind, 'bbox': _bbox(block),
                'heading_level': getattr(block, 'heading_level', None),
                'marker_text': block.raw_text(document) or ''}
            if kind=='Table' and hasattr(block,'contained_blocks'):
                record['marker_cells']=[{'text':child.raw_text(document),
                    'row_id':getattr(child,'row_id',None),'col_id':getattr(child,'col_id',None)}
                    for child in block.contained_blocks(document) if _kind(child)=='TableCell']
            regions.append(record)
        for block_id in page.structure or []:
            visit(block_id)
        pages.append({'page_index': page.page_id, 'bbox': _bbox(page), 'regions': regions})
    return pages


def _contains(box, x, y):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _inside(inner, outer):
    return inner[0] >= outer[0] and inner[1] >= outer[1] and inner[2] <= outer[2] and inner[3] <= outer[3]




def _decode_named_glyph(pdf, page, font_name, char, cache):
    """Use the PDF's embedded glyph name, never OCR or a spelling guess.

    Some TeX extension fonts encode large delimiters as control codes. Their
    native text trace still identifies the exact glyph ID. Only unambiguous
    embedded CFF names with a known Unicode interpretation are accepted.
    """
    import pymupdf
    from fontTools.cffLib import CFFFontSet
    key=('traces',page.number)
    if key not in cache:
        index={}
        for span in page.get_texttrace():
            for _,gid,origin,_ in span['chars']:
                point=(span['font'],round(origin[0],3),round(origin[1],3))
                index.setdefault(point,set()).add(gid)
        cache[key]=index
    origin=char['origin']
    gids=cache[key].get((font_name,round(origin[0],3),round(origin[1],3)),set())
    fonts={f[0] for f in page.get_fonts(full=True) if f[3].split('+')[-1]==font_name}
    if len(gids)!=1 or len(fonts)!=1:
        return None
    xref=next(iter(fonts));gid=next(iter(gids))
    if ('font',xref) not in cache:
        _,extension,_,data=pdf.extract_font(xref)
        names=[]
        if extension=='cff' and data:
            cff=CFFFontSet()
            try:
                cff.decompile(io.BytesIO(data),None)
                if len(cff.fontNames)==1:
                    names=list(cff[cff.fontNames[0]].charset)
            except (ValueError,AssertionError,IndexError):
                pass
        cache[('font',xref)]=(names,digest(data.hex()))
    names,font_digest=cache[('font',xref)]
    if not 0<=gid<len(names):
        return None
    name=names[gid]
    unicode_value=pymupdf.glyph_name_to_unicode(name)
    value=chr(unicode_value) if 0<unicode_value<=0x10ffff and unicode_value!=0xfffd else ''
    if not value:
        match=re.fullmatch(r'(parenleft|parenright|braceleft|braceright|bracketleft|bracketright)(?:big|Big|bigg|Bigg)',name)
        if match:
            value={'parenleft':'(','parenright':')','braceleft':'{','braceright':'}',
                   'bracketleft':'[','bracketright':']'}[match[1]]
    if not value or unicodedata.category(value) in {'Co','Cc'}:
        return None
    return {'text':value,'original_text':char['c'],'font_name':font_name,'font_xref':xref,
            'font_digest':font_digest,'glyph_id':gid,'glyph_name':name,
            'method':'embedded_cff_glyph_name','page':page.number+1,'bbox':list(char['bbox'])}


def _comparison_text(text):
    # Comparison only: the emitted source always retains native characters.
    value = re.sub(r'<[^>]*>', '', text)
    value = re.sub(r'(?<=\w)-[ \t]*\n[ \t]*(?=\w)', '', value)
    value = value.replace('ﬁ','fi').replace('ﬂ','fl').replace('ﬃ','ffi').replace('ﬄ','ffl')
    return value


def _prose_agrees(native, marker):
    a,b = (_comparison_text(t) for t in (native,marker))
    # The observed converter loses the i/l of fi/fl. Accept only that known
    # glyph discrepancy, never arbitrary edit-distance/dictionary corrections.
    letters = lambda t: ''.join(re.findall('[A-Za-z]+',t)).replace('fi','f').replace('fl','f')
    return letters(a)==letters(b) and _numbers(a)==_numbers(b)


def _numbers(text):
    # Never concatenate numbers across lines or table cells.
    return Counter(re.sub(r'\s+','',v).replace('−','-') for v in re.findall(
        r'[+−-]?\s*\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][+−-]?\d+)?(?:\s*%)?',_comparison_text(text)))


def transcribe_regions(pdf_path, pages, marker_text):
    """Every emitted non-whitespace glyph belongs to one actual native region.

    Native line order is retained *inside* each region, including tables and
    equations. No global x/y sorting, dehyphenation, symbol folding or NFKC is
    applied. Scan-only/mixed OCR regions, ambiguous overlaps, unassigned text and
    undecodable glyphs fail closed with page/region diagnostics.
    """
    import pymupdf
    blocks, issues, page_reports, recoveries, font_cache = [], [], [], [], {}
    with pymupdf.open(pdf_path) as pdf:
        if len(pages) != len(pdf) or [p['page_index'] for p in pages] != list(range(len(pdf))):
            raise SourceExtractionError('Marker/PDF page coverage or page order mismatch')
        for page, layout in zip(pdf, pages):
            if page.rotation:
                issues.append({'page':page.number+1,'kind':'unsupported_rotated_page','rotation':page.rotation})
            origin = layout['bbox']
            if origin[2] <= origin[0] or origin[3] <= origin[1]:
                raise SourceExtractionError('Invalid Marker page bounds')
            sx, sy = page.rect.width/(origin[2]-origin[0]), page.rect.height/(origin[3]-origin[1])
            regions = []
            for region in layout['regions']:
                box = region['bbox']
                bounds = [(box[0]-origin[0])*sx, (box[1]-origin[1])*sy,
                          (box[2]-origin[0])*sx, (box[3]-origin[1])*sy]
                if not all(math.isfinite(v) for v in bounds) or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                    raise SourceExtractionError('Invalid Marker region bounds: '+region['region_id'])
                regions.append({**region, 'pdf_bbox': bounds, 'lines': [], 'native_lines': [], 'glyphs': []})
            # Expanding the PDF's own fi/fl ligatures is typography, not spelling
            # correction. Mathematical superscripts and all other Unicode stay.
            flags = pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES & ~pymupdf.TEXT_PRESERVE_LIGATURES
            data = page.get_text('rawdict', flags=flags)
            glyph_count = assigned_count = 0
            for native in data['blocks']:
                for line in native.get('lines', []):
                    local = {i: [] for i in range(len(regions))}
                    for span in line['spans']:
                        for char in span['chars']:
                            value, box = char['c'], list(char['bbox'])
                            if not value.isspace():
                                glyph_count += 1
                            if any(c == '\ufffd' or unicodedata.category(c) in {'Co', 'Cc'} for c in value):
                                recovery=_decode_named_glyph(pdf,page,span['font'],char,font_cache)
                                if recovery:
                                    value=recovery['text'];recoveries.append(recovery)
                                else:
                                    issues.append({'page': page.number+1, 'kind': 'undecodable_glyph', 'bbox': box, 'text': value})
                            x, y = (box[0]+box[2])/2, (box[1]+box[3])/2
                            owners = [i for i,r in enumerate(regions) if _contains(r['pdf_bbox'], x, y)]
                            # An enclosing picture may contain a nested caption;
                            # accept only one uniquely innermost region.
                            owners = [i for i in owners if not any(j != i and
                                regions[j]['pdf_bbox'] != regions[i]['pdf_bbox'] and
                                _inside(regions[j]['pdf_bbox'], regions[i]['pdf_bbox']) for j in owners)]
                            if len(owners) != 1:
                                if not value.isspace():
                                    issues.append({'page': page.number+1, 'kind': 'unmapped_glyph' if not owners else 'ambiguous_region',
                                        'bbox': box, 'text': value, 'regions': [regions[i]['region_id'] for i in owners]})
                                continue
                            local[owners[0]].append({'text': value, 'bbox': box, 'font':span['font'], 'size':span['size'], 'original_text':char['c']})
                            if not value.isspace():
                                assigned_count += 1
                    for i, chars in local.items():
                        if not chars or not any(not c['text'].isspace() for c in chars):
                            continue
                        regions[i]['lines'].append(''.join(c['text'] for c in chars).strip())
                        regions[i]['native_lines'].append({'text':''.join(c['text'] for c in chars).strip(),
                            'bbox':[min(c['bbox'][0] for c in chars),min(c['bbox'][1] for c in chars),
                                    max(c['bbox'][2] for c in chars),max(c['bbox'][3] for c in chars)]})
                        regions[i]['glyphs'].extend(chars)
            if not glyph_count:
                issues.append({'page': page.number+1, 'kind': 'missing_native_text_layer'})
            for region in regions:
                text = '\n'.join(region.pop('lines')).strip()
                marker = region.pop('marker_text')
                if not text and marker.strip() and region['kind'] not in {'Picture', 'Figure'}:
                    issues.append({'page': page.number+1, 'region_id': region['region_id'], 'kind': 'ocr_only_region',
                        'marker_text': marker, 'bbox': region['pdf_bbox']})
                if not text:
                    continue
                if (marker.strip() and region['kind'] in {'Text','TextInlineMath','Caption','SectionHeader','ListItem','Footnote','PageHeader','PageFooter'}
                        and not _prose_agrees(text, marker)):
                    issues.append({'page':page.number+1,'region_id':region['region_id'],
                        'kind':'unresolved_text_disagreement','native_text':text,'marker_text':marker,
                        'bbox':region['pdf_bbox']})
                cells=region.get('marker_cells')
                numeric_peer='\n'.join(c['text'] for c in cells) if cells else marker
                if ((region['kind']=='Table' and cells or region['kind']=='Equation' and marker.strip())
                        and _numbers(text)!=_numbers(numeric_peer)):
                    issues.append({'page':page.number+1,'region_id':region['region_id'],
                        'kind':'unresolved_table_or_equation_numbers','native_text':text,'marker_text':numeric_peer})
                if re.search(r'\(cid:\d+\)', text):
                    issues.append({'page': page.number+1, 'region_id': region['region_id'], 'kind': 'unmapped_font_encoding'})
                blocks.append({**region, 'page': page.number+1, 'text': text,
                    'marker_text': marker, 'text_agrees': ' '.join(text.split()) == ' '.join(marker.split())})
            page_reports.append({'page': page.number+1, 'native_nonspace_glyphs': glyph_count,
                                 'assigned_nonspace_glyphs': assigned_count})
    parts, offset = [], 0
    for block in blocks:
        # The heading marker is structural metadata, not a newly written claim.
        level = block.get('heading_level')
        prefix = '#' * (min(6, max(1, level)) if isinstance(level, int) else 2)+' ' if block['kind'] == 'SectionHeader' else ''
        block['start'] = offset+len(prefix)
        block['end'] = block['start']+len(block['text'])
        part = prefix+block['text']
        parts.append(part)
        offset += len(part)+2
    text = '\n\n'.join(parts)
    report = {'version': EXTRACTION_VERSION, 'status': 'rejected' if issues else 'native_text_mapped',
        'environment':dict(extraction_environment()), 'pdf_hash': file_hash(pdf_path), 'marker_digest': digest(marker_text), 'text_digest': digest(text),
        'pages': page_reports, 'blocks': blocks, 'issues': issues, 'font_recoveries':recoveries,
        'limits': 'Native text/region coverage is not a universal certificate of visible PDF glyph semantics. '
                  'Image-only text and incorrectly encoded but printable glyphs require separate source review.'}
    report['digest'] = digest(report)
    return text, report


def extract_source_text(pdf_path, document, marker_text, content_dir):
    directory = Path(content_dir)
    # Preserve the actual original converter output, including on failure.
    (directory/'marker_raw.md').write_text(marker_text, encoding='utf-8')
    try:
        text, report = transcribe_regions(pdf_path, marker_regions(document), marker_text)
    except SourceExtractionError as exc:
        _atomic_json(directory/'source_extraction.json', {'version':EXTRACTION_VERSION,
            'status':'rejected','pdf_hash':file_hash(pdf_path),'marker_digest':digest(marker_text),
            'issues':[{'kind':'invalid_region_layout','reason':str(exc)}]})
        raise
    _atomic_json(directory/'source_extraction.json', report)
    if report['issues']:
        first = report['issues'][0]
        raise SourceExtractionError(f"Unresolved PDF extraction: {len(report['issues'])} issue(s); {first}. See source_extraction.json")
    return text, report


def validate_extraction(report, raw, pdf_hash):
    body = dict(report or {})
    expected = body.pop('digest', None)
    if (body.get('version') != EXTRACTION_VERSION or body.get('status') != 'native_text_mapped' or
            body.get('issues') or body.get('environment') != extraction_environment() or expected != digest(body) or body.get('text_digest') != digest(raw) or
            body.get('pdf_hash') != pdf_hash or not body.get('pages') or
            any(p['native_nonspace_glyphs'] == 0 or p['native_nonspace_glyphs'] != p['assigned_nonspace_glyphs'] for p in body['pages'])):
        raise SourceExtractionError('Missing, corrupt or incomplete original-PDF extraction proof')
    return report


def bind_asset_captions(figures, tables, report, content_dir):
    """Replace source caption metadata only with a uniquely located native caption."""
    audit=[]
    try:
        for kind,assets in (('figure',figures),('table',tables)):
            for key,asset in assets.items():
                caption=asset.get('caption','')
                page=asset.get('page')
                matches=[b for b in report['blocks'] if b['kind'] in {'Caption','Footnote','Text'} and
                    ' '.join(b['marker_text'].split())==' '.join(caption.split()) and
                    (page is None or b['page']==page+1)]
                if not matches and caption==kind.title()+' '+str(key):
                    asset['caption_source']={'status':'generated_label_only'}
                elif len(matches)!=1:
                    raise SourceExtractionError('Original caption location is missing/ambiguous: '+kind+'_'+str(key))
                else:
                    original=matches[0]
                    asset['caption']=original['text']
                    asset['caption_source']={'status':'native_pdf_caption','page':original['page'],
                        'region_id':original['region_id'],'bbox':original['pdf_bbox']}
                audit.append({'visual_id':kind+'_'+str(key),'marker_caption':caption,
                              'caption':asset['caption'],'source':asset['caption_source']})
    except SourceExtractionError as exc:
        _atomic_json(Path(content_dir)/'asset_caption_audit.json',{'status':'rejected','checked':audit,'error':str(exc)})
        raise
    _atomic_json(Path(content_dir)/'asset_caption_audit.json',{'status':'bound','captions':audit})
