"""Attempt-local, bounded measurement reuse; never serialized as scientific state."""

from collections import Counter, OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import hashlib
import inspect
import json
from pathlib import Path
import threading
import time


DEFAULTS = {
    "enabled": True,
    "reuse_wrapping": True,
    "exact_cache_entries": 4096,
    "line_cache_entries": 8192,
    "wrap_cache_entries": 8192,
    "glyph_cache_entries": 16384,
    "font_cache_entries": 64,
    "max_text_payload_bytes": 32 * 1024 * 1024,
    "verbose_measurements": False,
}
_CURRENT = ContextVar("poster_layout_measurements", default=None)
_OBSERVER = ContextVar("poster_layout_progress_observer", default=None)
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "poster_config.yaml"


def validate_settings(settings):
    result = {**DEFAULTS, **(settings or {})}
    for name in ("enabled", "reuse_wrapping", "verbose_measurements"):
        if not isinstance(result[name], bool):
            raise ValueError(f"layout_performance.{name} must be boolean")
    for name in DEFAULTS.keys() - {"enabled", "reuse_wrapping", "verbose_measurements"}:
        value = result[name]
        maximum = 256 * 1024 * 1024 if name == "max_text_payload_bytes" else 65536
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
            raise ValueError(f"layout_performance.{name} must be an integer in 0..{maximum}")
    return result


def file_identity(path):
    path = Path(path)
    stat = path.stat()
    return (str(path.resolve()), stat.st_dev, stat.st_ino, stat.st_size,
            stat.st_mtime_ns, stat.st_ctime_ns)


def freeze(value):
    """Exact values, no rounding or whitespace normalization."""
    if isinstance(value, dict):
        return tuple(sorted((key, freeze(item)) for key, item in value.items()))
    if isinstance(value, (tuple, list)):
        return tuple(freeze(item) for item in value)
    return value


def _text_bytes(value):
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, dict):
        return sum(_text_bytes(key) + _text_bytes(item) for key, item in value.items())
    if isinstance(value, (tuple, list)):
        return sum(_text_bytes(item) for item in value)
    return 0


def current_context():
    context = _CURRENT.get()
    # A copied async context must not share mutable cache objects across threads.
    return context if context and not context.closed and context.thread_id == threading.get_ident() else None


@contextmanager
def progress_observer(observer):
    token = _OBSERVER.set(observer)
    try:
        yield
    finally:
        _OBSERVER.reset(token)


class MeasurementContext:
    def __init__(self, settings=None):
        self.settings = validate_settings(settings)
        self.thread_id = threading.get_ident()
        self.started = time.perf_counter()
        self.cache = OrderedDict()
        self.counts = Counter()
        self.stats = {}
        self.payload_bytes = self.peak_payload_bytes = 0
        self.configuration = None
        self.configuration_identity = None
        self.configuration_digest = None
        self.failures = 0
        self.fallbacks = Counter()
        self.phases = []
        self.phase_count = 0
        self.phase_stack = []
        self.closed = False

    def config(self, loader):
        identity = (id(loader), file_identity(CONFIG_PATH))
        if self.configuration_identity != identity:
            configuration = loader()
            # Re-read on the next request if a concurrent file change occurred.
            after = (id(loader), file_identity(CONFIG_PATH))
            self.configuration = deepcopy(configuration)
            self.configuration_identity = identity if identity == after else None
            self.configuration_digest = hashlib.sha256(json.dumps(
                configuration, sort_keys=True, ensure_ascii=False,
            ).encode("utf-8")).hexdigest()
        return deepcopy(self.configuration)

    def memo(self, bucket, key, compute, *, clone=False, cache=True, valid=None):
        stats = self.stats.setdefault(bucket, {
            "requests": 0, "hits": 0, "computed": 0, "evictions": 0,
            "peak_entries": 0, "compute_seconds": 0.0,
        })
        stats["requests"] += 1
        identity = (bucket, key)
        if self.settings["enabled"] and cache and identity in self.cache:
            stats["hits"] += 1
            value, _ = self.cache[identity]
            self.cache.move_to_end(identity)
            return deepcopy(value) if clone else value
        failures = self.failures
        start = time.perf_counter()
        try:
            stats["computed"] += 1
            value = compute()
        finally:
            stats["compute_seconds"] += time.perf_counter() - start
        limit = self.settings[f"{bucket}_cache_entries"]
        size = _text_bytes(key) + _text_bytes(value)
        budget = self.settings["max_text_payload_bytes"]
        if (self.settings["enabled"] and cache and not self.closed and limit
                and size <= budget and self.failures == failures
                and (valid is None or valid())):
            while self.counts[bucket] >= limit:
                oldest = next(item for item in self.cache if item[0] == bucket)
                self._evict(oldest)
            while self.cache and self.payload_bytes + size > budget:
                self._evict(next(iter(self.cache)))
            self.cache[identity] = (deepcopy(value) if clone else value, size)
            self.counts[bucket] += 1
            self.payload_bytes += size
            self.peak_payload_bytes = max(self.peak_payload_bytes, self.payload_bytes)
            stats["peak_entries"] = max(stats["peak_entries"], self.counts[bucket])
        return value

    def _evict(self, identity):
        _, size = self.cache.pop(identity)
        self.payload_bytes -= size
        self.counts[identity[0]] -= 1
        self.stats[identity[0]]["evictions"] += 1

    def emit(self, label, **fields):
        event = {"type": "layout_detail", "label": label, **fields}
        observer = _OBSERVER.get()
        if observer:
            observer(event)
        else:
            from utils.src.logging_utils import log_agent_info
            details = " | ".join(f"{key} {value}" for key, value in fields.items())
            log_agent_info("layout_search", label + (f" | {details}" if details else ""))

    @contextmanager
    def phase(self, kind, **fields):
        self.phase_count += 1
        record = {"id": self.phase_count, "kind": kind, **fields}
        if self.phase_stack:
            record["parent_id"] = self.phase_stack[-1]
        self.phase_stack.append(record["id"])
        start = time.perf_counter()
        self.emit(f"{kind} started", **fields)
        try:
            yield
        except BaseException:
            record["status"] = "error"
            raise
        else:
            record["status"] = "completed"
        finally:
            self.phase_stack.pop()
            record["elapsed_seconds"] = round(time.perf_counter() - start, 6)
            if len(self.phases) < 256:
                self.phases.append(record)
            self.emit(f"{kind} {record['status']}", **fields,
                      elapsed=f"{record['elapsed_seconds']:.1f}s")

    def report(self, status):
        from importlib.metadata import version
        return {
            "schema_version": 1, "adapter_version": 1, "status": status,
            "enabled": self.settings["enabled"], "settings": dict(self.settings),
            "elapsed_seconds": round(time.perf_counter() - self.started, 6),
            "dependencies": {name: version(name) for name in ("python-pptx", "Pillow")},
            "caches": deepcopy(self.stats), "peak_text_payload_bytes": self.peak_payload_bytes,
            "compute_seconds_are_inclusive": True, "phase_seconds_are_inclusive": True,
            "payload_is_process_rss_limit": False, "measurement_failures": self.failures,
            "compatibility_fallbacks": dict(self.fallbacks), "phases": deepcopy(self.phases),
            "phases_truncated": self.phase_count > 256,
        }

    def close(self):
        self.cache.clear()
        self.configuration = None
        self.counts.clear()
        self.payload_bytes = 0
        self.closed = True


@contextmanager
def measurement_scope(settings=None):
    context = MeasurementContext(settings)
    token = _CURRENT.set(context)
    try:
        yield context
    finally:
        _CURRENT.reset(token)
        context.close()


def measured_phase(kind):
    def decorate(function):
        signature = inspect.signature(function)
        @wraps(function)
        def wrapped(*args, **kwargs):
            context = current_context()
            if context is None:
                return function(*args, **kwargs)
            bound = signature.bind(*args, **kwargs)
            fields = {name: bound.arguments[name] for name in ("family_id",)
                      if name in bound.arguments}
            variant = bound.arguments.get("variant") or (bound.arguments.get("candidate") or {}).get("variant")
            if variant:
                fields["variant"] = variant["variant_id"]
            with context.phase(kind, **fields):
                return function(*args, **kwargs)
        return wrapped
    return decorate


def cached_measurement(bucket):
    def decorate(function):
        signature = inspect.signature(function)
        @wraps(function)
        def wrapped(*args, **kwargs):
            context = current_context()
            if context is None:
                return function(*args, **kwargs)
            if not context.settings["enabled"]:
                return context.memo(bucket, (), lambda: function(*args, **kwargs), cache=False)
            from src.layout import text_height_measurement as measurement
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            values = bound.arguments
            context.config(measurement.load_config)
            try:
                font = file_identity(measurement.get_font_file_path(values["font_name"], bold=values["bold"]))
            except OSError:
                context.fallbacks["font_identity_unavailable"] += 1
                return context.memo(bucket, (), lambda: function(*args, **kwargs), cache=False)
            key = (function.__name__, freeze(values), context.configuration_digest, font)
            configuration_identity = context.configuration_identity
            def unchanged():
                try:
                    return (configuration_identity == context.configuration_identity
                            and configuration_identity is not None
                            and file_identity(CONFIG_PATH) == configuration_identity[1]
                            and file_identity(font[0]) == font)
                except OSError:
                    return False
            return context.memo(bucket, key, lambda: function(*args, **kwargs),
                                clone=True, valid=unchanged)
        return wrapped
    return decorate
