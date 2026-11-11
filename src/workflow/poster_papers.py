"""Paper folder names are labels; PDF bytes, not filenames or models, identify papers."""
import re
import unicodedata

VERSION = 'poster_paper_groups_v1'
_ID = r'(?:pdf|unknown)_[0-9a-f]{64}'


def validate_paper(paper):
    if (not isinstance(paper.get('paper_id'), str)
            or not re.fullmatch(_ID, paper['paper_id'])
            or not isinstance(paper.get('paper_title'), str)
            or not paper['paper_title'].strip()):
        raise ValueError('Invalid poster paper identity')
    return {key: paper[key] for key in ('paper_id', 'paper_title')}


def folder_paper_id(name):
    match = re.fullmatch(r'[\w-]+--(' + _ID + r')', name)
    if not match or len(name.encode('utf-8')) > 200:
        raise ValueError('Invalid paper directory name')
    return match.group(1)


def paper_folder(paper):
    validate_paper(paper)
    label = unicodedata.normalize('NFKC', paper['paper_title'])
    label = re.sub(r'[^\w-]+', '_', label).strip('_-') or 'Paper'
    # Leave room for the complete fingerprint, including on Unicode filesystems.
    label = label.encode('utf-8')[:96].decode('utf-8', errors='ignore').rstrip('_-') or 'Paper'
    return label + '--' + paper['paper_id']
