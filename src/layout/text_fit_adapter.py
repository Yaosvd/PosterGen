"""Local python-pptx 1.0.2 adapter; no dependency edits or global monkey-patches."""

from importlib.metadata import version
from functools import lru_cache
import unicodedata

from PIL import ImageFont
try:
    from pptx.text.layout import TextFitter, _LineSource, _rendered_size as _original_size
except ImportError:  # An unverified future backend may move its private helper.
    TextFitter = None

from src.layout.measurement_context import current_context, file_identity


def _rendered_size(text, point_size, font_file):
    context = current_context()
    identity = file_identity(font_file)
    def compute():
        font = context.memo("font", (identity, point_size),
                            lambda: ImageFont.truetype(font_file, point_size))
        try:
            width, height = font.getsize(text)
        except AttributeError:
            left, top, right, bottom = font.getbbox(text)
            width, height = right - left, bottom - top
        return int(width / 72.0 * 914400), int(height / 72.0 * 914400)
    return context.memo("glyph", (text, point_size, identity), compute)


class OptimizedFitError(RuntimeError):
    """An adapter error must not become a legacy 'text does not fit' result."""


class TextWidthError(ValueError):
    """No legal glyph cluster fits the fixed width, irrespective of height."""


def clusters(text):
    """Keep combining marks and joined glyph sequences together at soft wraps."""
    result = []
    for char in text:
        if result and (unicodedata.category(char).startswith('M') or char == '\u200d' or result[-1].endswith('\u200d')):
            result[-1] += char
        else:
            result.append(char)
    return result


def fitting_prefix(text, width, measure):
    parts = clusters(text)
    lo, hi = 0, len(parts)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if measure(''.join(parts[:mid])) <= width:
            lo = mid
        else:
            hi = mid - 1
    if not lo:
        raise TextWidthError('A glyph cluster exceeds the available text width')
    # Prefer an existing legal punctuation break before forcing a glyph break.
    # This affects layout only; no character is inserted into authored text.
    if lo < len(parts):
        breaks = [i + 1 for i in range(lo) if parts[i] in {'-', '/', '\u2010'}]
        if breaks:
            lo = breaks[-1]
    return ''.join(parts[:lo]), ''.join(parts[lo:])


class _SafeTextFitter(TextFitter or tuple):
    """Preserve ordinary word wrapping; soft-wrap long words like the renderer."""
    def _size(self, text, point_size):
        return _original_size(text, point_size, self._font_file)

    def _break_line(self, line_source, point_size):
        value = super()._break_line(line_source, point_size)
        if value is not None:
            return value
        words = line_source._text.split()
        if not words:
            return '', type(line_source)('')
        prefix, tail = fitting_prefix(words[0], self._width, lambda t: self._size(t, point_size)[0])
        return prefix, type(line_source)(' '.join([tail, *words[1:]]).strip())

    @property
    def _fits_inside_predicate(self):
        original = super()._fits_inside_predicate
        def predicate(point_size):
            try:
                return original(point_size)
            except TextWidthError:
                return False
        return predicate


def _width_info(text_frame, font_file, max_size):
    width, height = text_frame._extents
    if width <= 0:
        raise TextWidthError('Text frame has nonpositive usable width')
    size = int(max_size)
    context = current_context()
    def measure(text):
        return (_rendered_size(text, size, font_file) if context and context.settings['enabled']
                else _original_size(text, size, font_file))[0]
    def compute():
        if any(measure(c) > width for c in set(clusters(text_frame.text)) if not c.isspace()):
            raise TextWidthError('A glyph cluster exceeds the available text width at the fixed font size')
        if not any(measure(word) > width for word in text_frame.text.split()):
            return None
        fitter = (_CachedTextFitter if context and context.settings['enabled'] and context.settings['reuse_wrapping']
                  else _SafeTextFitter)(_LineSource(text_frame.text), (width, height), font_file)
        return {'soft_wrapped_lines': len(fitter._wrap_lines(_LineSource(text_frame.text), size))}
    if context and context.settings['enabled']:
        return context.memo('wrap', ('width_info', text_frame.text, width, size, file_identity(font_file)), compute)
    return compute()


class _CachedTextFitter(_SafeTextFitter):
    def _wrap_lines(self, line_source, point_size):
        context = current_context()
        key = (line_source._text, self._width, point_size, file_identity(self._font_file))
        def compute():
            lines = super(_CachedTextFitter, self)._wrap_lines(line_source, point_size)
            # _wrap_lines returns strings, not the _Line search-tree objects.
            return tuple(lines)
        lines = context.memo("wrap", key, compute)
        return list(lines)

    def _size(self, text, point_size):
        return _rendered_size(text, point_size, self._font_file)

    def _fits_in_width_predicate(self, point_size):
        return lambda line: _rendered_size(line.text, point_size, self._font_file)[0] <= self._width

    @property
    def _fits_inside_predicate(self):
        def predicate(point_size):
            try:
                lines = self._wrap_lines(self._line_source, point_size)
            except TextWidthError:
                return False
            height = _rendered_size("Ty", point_size, self._font_file)[1]
            return height * len(lines) <= self._height
        return predicate


@lru_cache(maxsize=1)
def backend_versions():
    return version("python-pptx"), version("Pillow")


def fit_text(text_frame, font_file, max_size):
    context = current_context()
    if text_frame.text == '':
        return None
    if backend_versions() != ('1.0.2', '10.4.0'):
        if context:
            context.fallbacks['unverified_dependency_version'] += 1
        return text_frame.fit_text(font_file=font_file, max_size=max_size)
    if TextFitter is None or not all(hasattr(TextFitter, name) for name in (
        '_wrap_lines', '_fits_in_width_predicate', 'best_fit_font_size')):
        if context:
            context.fallbacks['unverified_backend_interface'] += 1
        return text_frame.fit_text(font_file=font_file, max_size=max_size)
    info = _width_info(text_frame, font_file, max_size)
    optimized = context and context.settings['enabled'] and context.settings['reuse_wrapping']
    fitter = _CachedTextFitter if optimized else _SafeTextFitter
    try:
        size = fitter.best_fit_font_size(text_frame.text, text_frame._extents, max_size, font_file)
    except TextWidthError:
        raise
    except (TypeError, ValueError, OSError) as exc:
        if not optimized:
            raise
        # Check the same guarded behavior without caching. An adapter bug is
        # fatal, never reclassified as an ordinary physical fitting failure.
        try:
            _SafeTextFitter.best_fit_font_size(text_frame.text, text_frame._extents, max_size, font_file)
        except Exception as original:
            if type(original) is type(exc) and str(original) == str(exc):
                raise original
        raise OptimizedFitError('Cached fitting disagreed with original failure behavior') from exc
    except Exception as exc:
        if not optimized:
            raise
        raise OptimizedFitError('Unexpected cached fitting error') from exc
    if size is None:
        # Even a one-point probe needs some height. This is a normal failed
        # height probe, not a width error and not a successful unchanged frame.
        return {**(info or {}), 'height_probe_fits': False}
    text_frame._apply_fit('Calibri', size, False, False)
    return info
