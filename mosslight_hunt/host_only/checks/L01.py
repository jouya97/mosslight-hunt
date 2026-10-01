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
            # Own the reference fixture despite the separate P11 loader-alias seed.
            trial = World.from_dict(copy.deepcopy(values["source:" + replicate]))
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

# Five deterministic placements of one ordinary plan edit, using separate
# SQLite connections. No sleeps, nondeterministic scheduler or magic values.
for placement in ("before_prepare", "after_prepare", "after_compute", "after_publish", "after_reopen"):
  for seed, label in ((7, "north bed"), (19, "ridge")):
    with tempfile.TemporaryDirectory() as temp:
      path = Path(temp) / "workspace.sqlite"
      store, editor = EnsembleStore(path), EnsembleStore(path)
      plans = {"routine": {"events": [event("compost")]}, "dry care": {"events": [event("water")]}}
      ident = store.create({label: garden(seed)}, 2, plans,
                           {"adaptive": {"plan": "routine"}}, [{"name": "Care", "route": "adaptive"}])
      finish(store, ident)
      # The prior graph contains routine but no dry-care edge. The condition
      # now discovers dry care while the editor replaces that shared plan.
      store.edit(ident, {"route:adaptive": {"plan": "routine", "when": {"metric": "moisture", "below": 55, "plan": "dry care"}}})
      change = {"plan:dry care": {"events": [event("plant_moss")]}}
      if placement == "before_prepare": editor.edit(ident, change)
      ticket = store.prepare(ident)
      if placement == "after_prepare": editor.edit(ident, change)
      computed = store.compute(ticket)
      if placement in ("after_compute", "after_reopen"): editor.edit(ident, change)
      if placement == "after_reopen":
          store.close(); store = EnsembleStore(path)
      store.publish(ticket, computed)
      assert_visible_matches_snapshot(store, ident)
      if placement == "after_publish":
          editor.edit(ident, change)
          assert_visible_matches_snapshot(store, ident)
      finish(store, ident)
      assert_visible_matches_snapshot(store, ident)
      editor.close(); store.close()
