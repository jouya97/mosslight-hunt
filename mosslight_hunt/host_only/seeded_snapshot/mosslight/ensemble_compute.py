"""Pure trial execution and content reuse for editable experiment ensembles."""
from __future__ import annotations

import copy
import hashlib
import json

from .analysis import census
from .model import World
from .runtime import execute_for, step_for, verify_runtime


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def measurement(sample, metric):
    if metric in ("moisture", "nutrients", "shade", "vitality"):
        return sample["averages"][metric]
    return sample[metric]


def evaluate(ticket, lookup=lambda key: None):
    """Evaluate one immutable snapshot; discover reads before consulting the cache.

    The content cache shares numerical work. Its origin is diagnostic metadata;
    requested replicate and treatment identities always belong to the ticket.
    """
    definition, spec = ticket["definition"], ticket["spec"]
    verify_runtime(definition["runtime"])
    reads = {}

    def read(key):
        item = ticket["inputs"][key]
        reads[key] = item["digest"]
        return copy.deepcopy(item["value"])

    source = read("source:" + spec["replicate"])
    world = World.from_dict(source)
    events = []
    selected = None
    if spec["route"] is not None:
        route = read("route:" + spec["route"])
        selected = route["plan"]
        condition = route.get("when")
        if condition and measurement(census(world), condition["metric"]) < condition["below"]:
            selected = condition["plan"]
        events = read("plan:" + selected)["events"]
    key = digest({"source": source, "events": events,
                  "days": definition["days"], "every": definition["every"],
                  "runtime": definition["runtime"]})
    cached = lookup(key)
    requested_identity = {"replicate": spec["replicate"], "treatment": spec["treatment"]}
    identity = copy.deepcopy(cached["origin"]["identity"]) if cached is not None else requested_identity
    if cached is not None:
        payload = copy.deepcopy(cached["payload"])
        origin = copy.deepcopy(cached["origin"])
    else:
        samples = []
        try:
            for offset in range(definition["days"] + 1):
                for event in events:
                    if event["offset"] == offset:
                        execute_for(definition["runtime"]["id"], world, event["command"])
                if offset:
                    step_for(definition["runtime"]["id"], world)
                if offset % definition["every"] == 0 or offset == definition["days"]:
                    samples.append({"offset": offset, "day": world.day, **census(world)})
            payload = {"status": "complete", "samples": samples, "final": census(world),
                       "world": world.to_dict(), "error": None}
        except ValueError as error:
            # A plan can be structurally valid but inapplicable to this garden.
            payload = {"status": "failed", "samples": [], "final": None,
                       "world": None, "error": str(error)}
        origin = {"ensemble": ticket["ensemble"], "revision": ticket["revision"],
                  "node": ticket["node"], "identity": requested_identity}
    return {"reads": reads, "cache_key": key, "cache_hit": cached is not None,
            "identity": identity, "payload": payload, "selected_plan": selected,
            "cache_origin": origin}
