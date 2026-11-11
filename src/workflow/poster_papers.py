"""Paper folder names are labels; PDF bytes, not filenames or models, identify papers."""
import re

VERSION = 'poster_paper_groups_v2'
_ID = r'(?:pdf|unknown)_[0-9a-f]{64}'


def validate_paper(paper):
    if (not isinstance(paper.get('paper_id'), str)
            or not re.fullmatch(_ID, paper['paper_id'])
            or not isinstance(paper.get('paper_title'), str)
            or not paper['paper_title'].strip()):
        raise ValueError('Invalid poster paper identity')
    return {key: paper[key] for key in ('paper_id', 'paper_title')}


def folder_paper_id(name):
    """Read the fingerprint embedded in a legacy directory name, if present."""
    validate_folder(name)
    match = re.fullmatch(r'[\w-]+--(' + _ID + r')', name)
    return match.group(1) if match else None


def validate_folder(name):
    if (not isinstance(name, str) or not name or name in {'.', '..'}
            or any(c in '/\\' or ord(c) < 32 or ord(c) == 127 for c in name)
            or len(name.encode('utf-8')) > 200):
        raise ValueError('Invalid paper directory name')
    return name


def paper_folder(paper, number=1):
    validate_paper(paper)
    # Keep the actual title, including spaces/punctuation, on this Linux store.
    # Only path separators, control characters and oversized components need repair.
    label = re.sub(r'[/\\\x00-\x1f\x7f]', '_', paper['paper_title']).strip()
    if label in {'', '.', '..'}:
        label = 'Paper'
    suffix = f' ({number})' if number > 1 else ''
    label = label.encode('utf-8')[:200-len(suffix)].decode('utf-8', errors='ignore').rstrip()
    return validate_folder(label + suffix)
