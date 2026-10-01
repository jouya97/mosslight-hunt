"""Version-two workbench state and save validation.

Extension data is deliberately separate from the original six cell fields, so
old gardens retain their initial ecology and every subsystem can be inspected.
"""
from __future__ import annotations
import copy
from .catalog import RESOURCES, STRUCTURES, TERRAINS
from .validation import boolean, choice, integer, mapping, sequence, tags, text


def defaults(size):
    return {
        "tiles": [{"terrain": "soil", "mulch": 0, "structure": "none", "stress": 0} for _ in range(size)],
        "inventory": {key: 0 for key in RESOURCES},
        "seeds": {key: 0 for key in ("moss", "fern", "clover", "glowcap")},
        "notes": [], "specimens": [], "tasks": [], "beds": [], "plans": [],
        "rules": [], "nursery": [], "history": [], "visitors": {"bees": 0, "fireflies": 0, "worms": 0},
        "next_id": 1, "title": "A world under glass",
    }


def identifier(state):
    result = state["next_id"]
    state["next_id"] += 1
    return result


def validate(world, raw):
    """Return an independent canonical copy; reject invalid cross references."""
    mapping(raw, "Workbench")
    state = defaults(len(world.cells))
    unknown = set(raw) - set(state)
    if unknown:
        raw = {key: value for key, value in raw.items() if key not in unknown}
    state.update(raw.copy())
    text(state["title"], "Garden title", 100)
    integer(state["next_id"], "Next identifier", 1)
    tiles = sequence(state["tiles"], "Tiles", 1200)
    if len(tiles) != len(world.cells):
        raise ValueError("Workbench tile count does not match garden")
    for tile in tiles:
        mapping(tile, "Tile settings")
        choice(tile.get("terrain"), TERRAINS, "terrain")
        choice(tile.get("structure"), STRUCTURES, "structure")
        integer(tile.get("mulch"), "Mulch", 0, 100)
        integer(tile.get("stress"), "Stress", 0, 100)
    for name, keys in (("inventory", RESOURCES), ("seeds", ("moss", "fern", "clover", "glowcap")),
                       ("visitors", ("bees", "fireflies", "worms"))):
        values = mapping(state[name], name)
        if set(values) != set(keys):
            raise ValueError(f"Invalid {name} keys")
        for value in values.values():
            integer(value, name)
    ids = set()
    bed_names = set()
    for name in ("notes", "specimens", "tasks", "beds", "plans", "rules", "nursery"):
        ids = set()
        for item in sequence(state[name], name, 500):
            mapping(item, name)
            ident = integer(item.get("id"), "Identifier", 1)
            if ident in ids or ident > state["next_id"]:
                raise ValueError("Identifiers must be unique and below next_id")
            ids.add(ident)
            if name in ("notes", "specimens", "tasks"):
                integer(item.get("day"), "Entry day", 0, world.day)
            if name == "nursery":
                choice(item.get("species"), state["seeds"], "nursery species")
                choice(item.get("source"), ("seed", "cutting"), "propagation source")
                choice(item.get("status"), ("growing", "ready", "failed", "planted", "discarded"), "nursery status")
                integer(item.get("day"), "Nursery day", 0, world.day)
                integer(item.get("age"), "Nursery age")
                integer(item.get("count"), "Nursery count", 0, 20)
                integer(item.get("hydration"), "Hydration", 0, 3)
                integer(item.get("vitality"), "Nursery vitality", 0, 100)
                if item["status"] in ("growing", "ready") and (item["count"] == 0 or item["vitality"] == 0):
                    raise ValueError("Living nursery batches need plants and vitality")
            elif name == "notes":
                text(item.get("text"), "Note", 2000)
                item["tags"] = tags(item.get("tags", []))
                if item.get("tile") is not None:
                    _point(world, item["tile"])
            elif name == "specimens":
                choice(item.get("species"), state["seeds"], "specimen species")
                text(item.get("label"), "Specimen label", 100)
                _point(world, item.get("tile"))
                for key in ("moisture", "nutrients", "shade", "vitality"):
                    integer(item.get(key), key, 0, 100)
                integer(item.get("age"), "Age")
            elif name == "tasks":
                text(item.get("text"), "Task", 240)
                integer(item.get("due"), "Due day")
                boolean(item.get("done"), "Task completed")
            elif name == "beds":
                bed_name = text(item.get("name"), "Bed name", 80).casefold()
                if bed_name in bed_names:
                    raise ValueError("Bed names must be unique")
                bed_names.add(bed_name)
                points = sequence(item.get("tiles"), "Bed tiles", 1200)
                if not points or len({tuple(_point(world, p)) for p in points}) != len(points):
                    raise ValueError("Bed must contain unique tiles")
            elif name == "plans":
                text(item.get("name"), "Plan name", 80)
                integer(item.get("day"), "Plan day")
                integer(item.get("repeat"), "Repeat interval", 0, 365)
                integer(item.get("remaining"), "Remaining runs", 0, 1000)
                choice(item.get("status"), ("pending", "done", "failed", "cancelled"), "plan status")
                if item["status"] == "pending" and item["remaining"] == 0:
                    raise ValueError("Pending plans need remaining runs")
                if item["remaining"] > 1 and item["repeat"] == 0:
                    raise ValueError("Multiple plan runs require a repeat interval")
                if item["status"] == "done" and item["remaining"] != 0:
                    raise ValueError("Completed plans cannot have remaining runs")
                if item["day"] + item["repeat"] * max(0, item["remaining"] - 1) > 1_000_000:
                    raise ValueError("Plan extends beyond the garden calendar")
                _care(item)
                for p in sequence(item.get("tiles"), "Plan tiles", 1200):
                    _point(world, p)
                if not item["tiles"] or len({tuple(p) for p in item["tiles"]}) != len(item["tiles"]):
                    raise ValueError("Plan requires unique tiles")
                text(item.get("last_error", ""), "Plan error", 240, blank=True)
            elif name == "rules":
                text(item.get("name"), "Rule name", 80)
                choice(item.get("metric"), ("moisture", "nutrients", "vitality"), "rule metric")
                choice(item.get("operator"), ("below", "above"), "rule operator")
                integer(item.get("threshold"), "Threshold", 0, 100)
                boolean(item.get("enabled"), "Rule enabled")
                _care(item)
                for p in sequence(item.get("tiles"), "Rule tiles", 1200):
                    _point(world, p)
                if not item["tiles"] or len({tuple(p) for p in item["tiles"]}) != len(item["tiles"]):
                    raise ValueError("Rule requires unique tiles")
    previous_day = -1
    for point in sequence(state["history"], "History", 240):
        mapping(point, "History point")
        integer(point.get("day"), "History day", 0, world.day)
        if point["day"] < previous_day:
            raise ValueError("History days must increase")
        previous_day = point["day"]
        for key in ("occupied", "births", "losses"):
            integer(point.get(key), key, 0, len(world.cells))
        for key in ("moisture", "nutrients", "vitality"):
            value = point.get(key)
            if type(value) not in (int, float) or not 0 <= value <= 100:
                raise ValueError(f"Invalid history {key}")
    for cell, tile in zip(world.cells, tiles):
        if tile["terrain"] == "pond" and cell.species is not None:
            raise ValueError("Ponds and stones cannot contain plants")
    return state


def _point(world, value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Tile must be [x, y]")
    world.index(*value)
    return value


def _care(item):
    choice(item.get("action"), ("water", "compost", "clear", "plant_moss", "plant_fern", "plant_clover", "plant_glowcap"), "care action")
