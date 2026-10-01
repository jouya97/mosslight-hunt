import copy, json, tempfile
from pathlib import Path
from mosslight.ensembles import EnsembleStore
from mosslight.model import World, Cell
from mosslight.analysis import census
from mosslight.runtime import execute_for, step_for
from mosslight.ensemble_compute import digest


def garden(seed=7, moisture=40, width=4):
    return World(seed, width, 4, cells=[Cell(moisture, 50, 50) for _ in range(width*4)])

def event(action="water", x=0, offset=0):
    return {"offset": offset, "command": {"op": "tend", "args": {"x": x, "y": 0, "action": action}}}

def finish(store, ident):
    for _ in range(1000):
        if store.work_once(ident) is None:
            return store.report(ident)
    raise AssertionError("ensemble did not quiesce")

def numerical(result):
    return {"comparisons": result["comparisons"], "outcomes": [
        {key: row[key] for key in ("identity", "payload", "selected_plan", "reads", "cache_key")}
        for row in result["outcomes"]]}

def full_reference(store, ident, revision):
    # Separate, deliberately slow interpreter. It never calls evaluate, replay,
    # summarize, reads stored outcomes, or consults the dependency graph/cache.
    values = store.inputs(ident, revision)
    definition = store._workspace(ident)["definition"]
    outcomes = {}
    for replicate in definition["replicates"]:
        for treatment in [{"name": "control", "route": None}, *definition["treatments"]]:
            trial = World.from_dict(values["source:" + replicate])
            plan = None
            if treatment["route"] is not None:
                route = values["route:" + treatment["route"]]
                plan = route["plan"]
                when = route.get("when")
                if when:
                    sample = census(trial)
                    value = sample["averages"][when["metric"]] if when["metric"] in sample["averages"] else sample[when["metric"]]
                    if value < when["below"]:
                        plan = when["plan"]
            events = values["plan:" + plan]["events"] if plan else []
            samples = []
            for day in range(definition["days"] + 1):
                for command in (e["command"] for e in events if e["offset"] == day):
                    execute_for(definition["runtime"]["id"], trial, command)
                if day:
                    step_for(definition["runtime"]["id"], trial)
                if day % definition["every"] == 0 or day == definition["days"]:
                    samples.append({"offset": day, "day": trial.day, **census(trial)})
            outcomes[(replicate, treatment["name"])] = {"samples": samples, "world": trial.to_dict(), "final": census(trial)}
    return outcomes

def assert_visible_matches_snapshot(store, ident):
    try:
        report = store.report(ident)
    except ValueError:
        return
    expected = full_reference(store, ident, report["revision"])
    for row in report["result"]["outcomes"]:
        key = (row["identity"]["replicate"], row["identity"]["treatment"])
        for field in ("samples", "world", "final"):
            assert row["payload"][field] == expected[key][field], ("visible result mixes input revisions", report["revision"], key, field)

with tempfile.TemporaryDirectory() as temp:
    store = EnsembleStore(Path(temp) / "workspace.sqlite")
    source = garden()
    ident = store.create({"cutting tray A": source, "cutting tray B": copy.deepcopy(source)}, 2,
                         {"care": {"events": [event("plant_moss")]}}, {"care": {"plan": "care"}},
                         [{"name": "Care", "route": "care"}])
    nodes = store.status(ident)["nodes"]
    hits = 0
    for node in nodes:
        ticket = store.prepare(ident, node["node"])
        computed = store.compute(ticket)
        hits += computed["cache_hit"]
        assert computed["identity"] == {"replicate": node["replicate"], "treatment": node["treatment"]}, "cached producer identity replaced requested cohort identity"
        assert store.publish(ticket, computed)
    report = store.report(ident)
    assert len(report["result"]["outcomes"]) == 4
    store.close()
