"""Strict model-request JSON; numeric conversion must not stringify bad data."""
import json
import math


def request_json(value):
    """Encode JSON plus NumPy numeric scalars, identifying invalid field paths.

    Keep ordinary JSON serialization unchanged. Arrays, arbitrary objects and
    non-finite numbers are errors, not strings or silently missing fields.
    """
    def native(item, path):
        if item is None or type(item) in (str, bool, int):
            return item
        if type(item) is float:
            if not math.isfinite(item):
                raise ValueError(f'Non-finite request number at {path}')
            return item
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                if not isinstance(key, str):
                    raise TypeError(f'Non-string request key at {path}')
                escaped = key.replace('~', '~0').replace('/', '~1')
                result[key] = native(child, path + '/' + escaped)
            return result
        if isinstance(item, (list, tuple)):
            return [native(child, path + '/' + str(i)) for i, child in enumerate(item)]
        import numpy as np
        if isinstance(item, (np.bool_, np.integer, np.floating)):
            converted = item.item()
            # Extended-precision scalars may stay NumPy objects: do not lose
            # precision or recurse indefinitely by coercing them to float.
            if type(converted) in (bool, int, float):
                return native(converted, path)
        kind = type(item).__module__ + '.' + type(item).__name__
        raise TypeError(f'Unsupported request value at {path}: {kind}')

    return json.dumps(native(value, '$'), ensure_ascii=False, allow_nan=False)
