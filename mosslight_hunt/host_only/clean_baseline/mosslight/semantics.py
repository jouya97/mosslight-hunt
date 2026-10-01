"""Execution-local ecological release policy; ordinary gardens keep classic rules."""
from contextvars import ContextVar

ACTIVE_RELEASE = ContextVar("mosslight_release", default="classic-1")


def barrel_adjustment(previous_moisture):
    if ACTIVE_RELEASE.get() == "conservation-2":
        return min(6, max(0, 70 - previous_moisture)) - 6
    return 0
