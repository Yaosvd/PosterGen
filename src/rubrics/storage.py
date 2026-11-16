"""Checksum-bound receipts and atomic publication shared by the new framework."""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import json
import os
import tempfile

from utils.persistence import _atomic_json, digest, read_json


class IntegrityError(ValueError):
    """Corrupt or mismatched durable state; never silently fall back or resend."""


class WaitingForConfiguration(ValueError):
    pass


class RequestUncertain(RuntimeError):
    """A durable charge has no response; only explicit reconciliation may resolve it."""


class BudgetExceeded(RuntimeError):
    pass


@contextmanager
def lock(path, *, blocking=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as exc:
            raise RuntimeError('Another operation owns this framework resource') from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def write(path, value):
    _atomic_json(Path(path), {'payload': value, 'digest': digest(value)})


def read(path):
    try:
        value = read_json(Path(path))
        valid = isinstance(value,dict) and set(value)=={'payload','digest'} and digest(value['payload'])==value['digest']
    except (ValueError,TypeError,KeyError) as exc:
        raise IntegrityError(f'Invalid receipt: {path}') from exc
    if not valid:
        raise IntegrityError(f'Receipt checksum mismatch: {path}')
    return value['payload']


def immutable(path, value):
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise IntegrityError(f'Immutable receipt changed: {path}')
    else:
        write(path, value)


def text_file(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def request_once(root, identity, invoke):
    """Charge before calling. Concurrent callers and resumes cannot double-send."""
    root = Path(root)
    with lock(root / '.request.lock'):
        immutable(root / 'identity.json', identity)
        charged, returned = root / 'charge.json', root / 'response.json'
        if returned.exists():
            if not charged.exists():
                raise IntegrityError('Response exists without request charge')
            if read(charged) != {'identity': digest(identity)}:
                raise IntegrityError('Request charge changed')
            return read(returned)
        if charged.exists():
            raise RequestUncertain(f'Charged request has no durable response: {root}')
        write(charged, {'identity': digest(identity)})
        try:
            result = invoke()
            # Check strict serializability before declaring a response durable.
            json.dumps(result, allow_nan=False)
            write(returned, result)
            return result
        except BaseException as exc:
            write(root / 'failure.json', {'error_type': type(exc).__name__})
            raise
