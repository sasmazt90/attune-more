"""Request-local numerical speech timing; never contains text or identifiers."""
from contextvars import ContextVar
from math import isfinite

_timing = ContextVar('mental_generation_timing', default=None)
NAMES = ('total', 'verify', 'warm-wait', 'worker', 'worker-verify-assets',
         'worker-verify-source', 'worker-import-runtime', 'worker-load-model',
         'worker-inference', 'worker-encode-wav')


def begin():
    _timing.set({})


def record(name, seconds):
    current = _timing.get()
    if current is not None and name in NAMES and type(seconds) in (int, float) and isfinite(seconds) and 0 <= seconds < 86400:
        current[name] = round(seconds * 1000, 3)


def phases(rows):
    # Rows have already passed the worker protocol's bounded numerical validation.
    for left, right in zip(rows, rows[1:]):
        record('worker-' + left['phase'], right['elapsedSeconds'] - left['elapsedSeconds'])


def server_timing():
    values = _timing.get() or {}
    return ', '.join('tts-' + name + ';dur=' + str(values[name]) for name in NAMES if name in values)
