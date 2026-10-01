"""Named beds, finite repeating care plans, and conditional daily rules."""
from __future__ import annotations
from .model import ACTIONS
from .notebook import find_entry, _room
from .state import identifier
from .validation import boolean, choice, coordinates, integer, text


def add_bed(world, name, tiles):
    name = text(name, "Bed name", 80)
    points = coordinates(world, tiles)
    if any(b["name"].casefold() == name.casefold() for b in world.workbench["beds"]):
        raise ValueError("A bed with that name already exists")
    _room(world, "beds")
    entry = {"id": identifier(world.workbench), "name": name, "tiles": [list(p) for p in points]}
    world.workbench["beds"].append(entry)
    world.revision += 1
    return entry.copy()


def delete_bed(world, ident):
    entry = find_entry(world, "beds", ident)
    world.workbench["beds"].remove(entry)
    world.revision += 1


def bed_tiles(world, ident):
    return [list(p) for p in find_entry(world, "beds", ident)["tiles"]]


def schedule(world, name, day, tiles, action, repeat=0, runs=1):
    name = text(name, "Plan name", 80)
    integer(day, "Scheduled day", world.day+1)
    integer(repeat, "Repeat interval", 0, 365)
    integer(runs, "Runs", 1, 1000)
    if runs > 1 and repeat == 0:
        raise ValueError("Multiple runs require a repeat interval")
    if day + repeat*(runs-1) > 1_000_000:
        raise ValueError("Plan extends beyond the garden calendar")
    choice(action, ACTIONS, "care action")
    points = coordinates(world, tiles)
    _room(world, "plans")
    entry = {"id": identifier(world.workbench), "name": name, "day": day, "action": action,
             "tiles": [list(p) for p in points], "repeat": repeat, "remaining": runs,
             "status": "pending", "last_error": ""}
    world.workbench["plans"].append(entry)
    world.revision += 1
    return entry.copy()


def cancel_plan(world, ident):
    entry = find_entry(world, "plans", ident)
    if entry["status"] != "pending":
        raise ValueError("Only pending plans can be cancelled")
    entry["status"] = "cancelled"
    world.revision += 1


def run_plans(world):
    """Execute before ecology, in id order; failures are recorded once."""
    from .gardening import tend_many
    from .engine import log
    due = sorted([p["id"] for p in world.workbench["plans"] if p["status"] == "pending" and p["day"] <= world.day])
    for ident in due:
        entry = find_entry(world, "plans", ident)
        try:
            tend_many(world, entry["tiles"], entry["action"])
            # tend_many replaces state, so retrieve the entry again.
            entry = find_entry(world, "plans", ident)
            entry["remaining"] -= 1
            if entry["remaining"] and entry["repeat"]:
                entry["day"] += entry["repeat"]
            else:
                entry["status"] = "done"
            log(world, f"Care plan completed: {entry['name']}")
        except ValueError as exc:
            entry = find_entry(world, "plans", ident)
            entry["status"] = "failed"
            entry["last_error"] = str(exc)[:240]
            log(world, f"Care plan failed: {entry['name']}")


def add_rule(world, name, tiles, metric, operator, threshold, action):
    name = text(name, "Rule name", 80)
    points = coordinates(world, tiles)
    choice(metric, ("moisture", "nutrients", "vitality"), "metric")
    choice(operator, ("below", "above"), "operator")
    integer(threshold, "Threshold", 0, 100)
    choice(action, ACTIONS, "care action")
    _room(world, "rules")
    entry = {"id": identifier(world.workbench), "name": name, "tiles": [list(p) for p in points],
             "metric": metric, "operator": operator, "threshold": threshold,
             "action": action, "enabled": True}
    world.workbench["rules"].append(entry)
    world.revision += 1
    return entry.copy()


def enable_rule(world, ident, enabled):
    boolean(enabled, "Enabled")
    find_entry(world, "rules", ident)["enabled"] = enabled
    world.revision += 1


def delete_rule(world, ident):
    entry = find_entry(world, "rules", ident)
    world.workbench["rules"].remove(entry)
    world.revision += 1


def run_rules(world):
    """Evaluate all conditions against the same post-ecology snapshot."""
    from .engine import act, log
    matches = []
    for rule in sorted(world.workbench["rules"], key=lambda r: r["id"]):
        if not rule["enabled"]:
            continue
        for x, y in rule["tiles"]:
            value = getattr(world.cell(x, y), rule["metric"])
            applies = value < rule["threshold"] if rule["operator"] == "below" else value > rule["threshold"]
            if applies:
                matches.append((rule["id"], x, y, rule["action"]))
    failed = set()
    for ident, x, y, action in matches:
        try:
            act(world, x, y, action)
        except ValueError:
            failed.add(ident)
    for ident in sorted(failed):
        log(world, f"Care rule {ident} skipped unsuitable ground.")
