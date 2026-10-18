from contextlib import contextmanager
from contextvars import ContextVar

_enabled = ContextVar("syncing_events_enabled", default=True)


def sync_events_enabled():
    return _enabled.get()


@contextmanager
def suppress_sync_events():
    token = _enabled.set(False)
    try:
        yield
    finally:
        _enabled.reset(token)
