"""Explicit retained simulation releases for reproducible local experiments."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path

from .semantics import ACTIVE_RELEASE

DEFAULT_VERSION = "classic-1"
CURRENT_VERSION = "conservation-2"
VERSIONS = {
    "classic-1": "Original garden ecology: rain barrels add six moisture on rainy days.",
    "conservation-2": "Rain barrels deliver at most six moisture, limited by the previous-day deficit to 70.",
}
KERNEL_FILES = ("analysis", "catalog", "commands", "engine", "exchange", "gardening",
                "habitat", "model", "notebook", "nursery", "planning", "semantics",
                "state", "validation", "weather", "runtime")


def version_info(version=DEFAULT_VERSION):
    if version not in VERSIONS:
        raise ValueError("Unknown simulation release")
    digest = hashlib.sha256(version.encode())
    for name in KERNEL_FILES:
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name + ".py").read_bytes())
    return {"id": version, "schema": 2, "fingerprint": digest.hexdigest()}


def releases():
    return [{**version_info(name), "description": description}
            for name, description in VERSIONS.items()]


def execute_for(version, world, command):
    from .commands import execute
    version_info(version)
    token = ACTIVE_RELEASE.set(version)
    try:
        return execute(world, copy.deepcopy(command))
    finally:
        ACTIVE_RELEASE.reset(token)


def step_for(version, world, days=1):
    from .engine import step
    version_info(version)
    token = ACTIVE_RELEASE.set(version)
    try:
        return step(world, days)
    finally:
        ACTIVE_RELEASE.reset(token)


def execution_version(definition):
    """The saved release, independent of the version preferred for new trials."""
    return definition["runtime"]["id"]


def verify_runtime(recorded):
    actual = version_info(recorded["id"])
    if actual != recorded:
        raise ValueError("The historical simulation kernel has changed; restore its recorded installation")
