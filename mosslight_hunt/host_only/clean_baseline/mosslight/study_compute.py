"""Pure bounded work and complete-cohort scoring for staged studies."""
from __future__ import annotations

import copy

from .analysis import census
from .ensemble_compute import measurement
from .model import World
from .runtime import execute_for, step_for, verify_runtime
from .validation import integer


def advance(claim, offsets=1):
    integer(offsets, "Work offsets", 1, 121)
    verify_runtime(claim["definition"]["runtime"])
    version = claim["definition"]["runtime"]["id"]
    state = copy.deepcopy(claim["state"])
    world = World.from_dict(copy.deepcopy(state["world"]))
    events = [] if claim["treatment"] == "control" else claim["plans"][claim["treatment"]]
    stop = min(claim["until"] + 1, state["next_offset"] + offsets)
    for offset in range(state["next_offset"], stop):
        for event in events:
            if event["offset"] == offset:
                execute_for(version, world, event["command"])
        if offset:
            step_for(version, world)
        if offset % claim["definition"]["every"] == 0 or offset == claim["until"]:
            state["samples"].append({"offset": offset, "day": world.day, **census(world)})
        state["next_offset"] = offset + 1
    state["world"] = copy.deepcopy(world.to_dict())
    return state


def readiness(stage, jobs):
    """Use small status records to distinguish usable previews from decisions."""
    indexed = {(job["replicate"], job["treatment"]): job for job in jobs}
    names = ["control", *stage["treatments"]]
    common = [replicate for replicate in stage["cohort"]
              if all(indexed[(replicate, name)]["status"] == "complete" for name in names)]
    return {"terminal": all(job["status"] in ("complete", "failed") for job in jobs),
            "pending": sum(job["status"] in ("ready", "running") for job in jobs),
            "common": common, "excluded": [r for r in stage["cohort"] if r not in common]}


def progress(stage, jobs, metric):
    """Preview common support; terminal is independent of preview availability."""
    support = readiness(stage, jobs)
    common = support["common"]
    indexed = {(job["replicate"], job["treatment"]): job for job in jobs}
    scores = []
    for name in stage["treatments"]:
        effects = [measurement(indexed[(replicate, name)]["state"]["samples"][-1], metric)
                   - measurement(indexed[(replicate, "control")]["state"]["samples"][-1], metric)
                   for replicate in common]
        scores.append({"treatment": name, "score": round(sum(effects)/len(effects), 6) if effects else None})
    # Stable sort retains the original treatment order for ties.
    ranking = sorted(scores, key=lambda item: -item["score"]) if common else scores
    return {**support, "ranking": ranking}
