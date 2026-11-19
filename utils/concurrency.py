"""Host-local, crash-releasing resource slots for managed batch workers."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import time


class WorkStopped(BaseException):
    """Cancellation must not be swallowed by generation failure handlers."""


def stopped():
    value = os.environ.get('RUBRICS_STOP_FILE')
    return bool(value and Path(value).exists())


def settings():
    path = os.environ.get('RUBRICS_RESOURCE_POLICY')
    return json.loads(Path(path).read_text()) if path else None


@contextmanager
def _locked_slot(resource, policy):
    if policy is None:
        yield 0, 0.0
        return
    count = policy['limits'][resource]
    if type(count) is not int or count < 1:
        raise ValueError('Resource limit must be a positive integer')
    root = Path(policy['root']) / resource
    root.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    acquired = None
    try:
        while acquired is None:
            if stopped():
                raise WorkStopped()
            for index in range(count):
                stream = (root / f'{index}.lock').open('a')
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    stream.close()
                else:
                    acquired = stream
                    break
            if acquired is None:
                time.sleep(.2)
        if stopped():
            raise WorkStopped()
        yield index, time.monotonic() - start
    finally:
        if acquired is not None:
            acquired.close()


@contextmanager
def slot(resource):
    with _locked_slot(resource, settings()) as (_, queued):
        yield queued


@contextmanager
def marker_slot():
    policy = settings()
    devices = (policy or {}).get('marker_gpu_uuids')
    with _locked_slot('marker', policy) as (index, queued):
        visible = devices[index] if devices is not None else os.environ['CUDA_VISIBLE_DEVICES']
        yield index, queued, visible


def inherited_lease():
    value = os.environ.get('RUBRICS_COORDINATOR_FD')
    if value is None:
        return ()
    fd = int(value)
    os.fstat(fd)
    return (fd,)
