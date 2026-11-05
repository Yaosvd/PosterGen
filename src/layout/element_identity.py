"""Stable identities for actual layout objects, independent of geometry and order."""

VERSION = 'poster_element_ids_v1'
_SECTION_SUFFIXES = {'section_title': 'title', 'section_container': 'container',
                     'title_accent_block': 'title_accent_block',
                     'title_accent_line': 'title_accent_line', 'mixed': 'mixed'}
_GLOBAL_IDS = {'title': 'poster_title', 'aff_logo': 'aff_logo',
               'conf_logo': 'conf_logo', 'qr_code': 'qr_code'}


def element_id(element):
    """Preserve explicit IDs; derive missing IDs only from an object's own role/owner."""
    explicit = element.get('id')
    if explicit is not None and explicit != '':
        if not isinstance(explicit, str) or not explicit.strip():
            raise ValueError('Layout element id must be a nonblank string')
        return explicit
    kind, section = element.get('type'), element.get('section_id')
    if section:
        if kind in _SECTION_SUFFIXES:
            return str(section) + '_' + _SECTION_SUFFIXES[kind]
        if kind == 'text':
            return str(section)  # Preserve RenderFit's existing no-ID body convention.
        if kind == 'visual' and element.get('visual_id'):
            return str(section) + '_' + str(element['visual_id'])
    return _GLOBAL_IDS.get(kind)


def identified_layout(layout):
    """Return shallow object copies with unique IDs; never mutate source artifacts."""
    result, seen = [], set()
    for original in layout:
        element = dict(original)
        identity = element_id(element)
        if identity:
            if identity in seen:
                raise ValueError('Duplicate layout element id: ' + identity)
            seen.add(identity)
            element['id'] = identity
        result.append(element)
    return result
