"""Read-only garden measurements, habitat advice and deterministic forecasts."""
from __future__ import annotations
import copy
import math
from collections import deque
from .catalog import SPECIES_GUIDE, TERRAINS
from .validation import choice, coordinates, integer


def census(world, tiles=None):
    points = coordinates(world, tiles) if tiles is not None else [(x,y) for y in range(world.height) for x in range(world.width)]
    cells = [world.cell(x,y) for x,y in points]
    living = [c for c in cells if c.species]
    population = {s: sum(c.species == s for c in cells) for s in SPECIES_GUIDE}
    averages = {k: round(sum(getattr(c,k) for c in cells)/len(cells), 2) for k in ("moisture", "nutrients", "shade")}
    averages["vitality"] = round(sum(c.vitality for c in living)/len(living), 2) if living else 0
    proportions = [v/len(living) for v in population.values() if v] if living else []
    return {"tiles": len(cells), "occupied": len(living), "empty": len(cells)-len(living),
            "coverage": round(100*len(living)/len(cells), 2), "population": population,
            "averages": averages, "richness": len(proportions),
            "diversity": round(-sum(p*math.log(p) for p in proportions), 4),
            "endangered": sum(c.vitality < 25 for c in living),
            "oldest": max((c.age for c in living), default=0)}


def suitability(world, x, y, species):
    from .habitat import effective_shade
    choice(species, SPECIES_GUIDE, "species")
    index = world.index(x,y)
    cell = world.cells[index]
    tile = world.workbench["tiles"][index]
    shade = effective_shade(world, index)
    info = SPECIES_GUIDE[species]
    if not TERRAINS[tile["terrain"]]["plantable"]:
        return {"score": 0, "reasons": ["Terrain cannot support plants"], "effective_shade": shade}
    moisture_penalty = abs(cell.moisture-info["moisture"])
    shade_penalty = abs(shade-info["shade"])
    nutrient_penalty = max(0, 20-cell.nutrients)*2
    score = max(0, 100-moisture_penalty-shade_penalty-nutrient_penalty)
    reasons = []
    if moisture_penalty > 20:
        reasons.append("Too dry" if cell.moisture < info["moisture"] else "Too wet")
    if shade_penalty > 20:
        reasons.append("Too bright" if shade < info["shade"] else "Too shaded")
    if cell.nutrients < 20:
        reasons.append("Soil needs nutrients")
    return {"score": score, "reasons": reasons or ["Comfortable habitat"], "effective_shade": shade}


def recommendations(world, species, limit=10, empty_only=True):
    integer(limit, "Limit", 1, 1200)
    choice(species, SPECIES_GUIDE, "species")
    if type(empty_only) is not bool:
        raise ValueError("empty_only must be true or false")
    result = []
    for y in range(world.height):
        for x in range(world.width):
            if empty_only and world.cell(x,y).species:
                continue
            if not TERRAINS[world.workbench["tiles"][world.index(x,y)]["terrain"]]["plantable"]:
                continue
            result.append({"x": x, "y": y, **suitability(world,x,y,species)})
    return sorted(result, key=lambda r: (-r["score"], r["y"], r["x"]))[:limit]


def patches(world, species=None):
    """Connected orthogonal groups; mixed species join unless filtered."""
    from .engine import neighbors
    if species is not None:
        choice(species, SPECIES_GUIDE, "species")
    remaining = {(i%world.width, i//world.width) for i,c in enumerate(world.cells)
                 if c.species and (species is None or c.species == species)}
    result = []
    while remaining:
        start = min(remaining, key=lambda p: (p[1],p[0]))
        queue = deque([start])
        remaining.remove(start)
        group = []
        while queue:
            point = queue.popleft()
            group.append(point)
            for other in neighbors(world, *point):
                if other in remaining:
                    remaining.remove(other)
                    queue.append(other)
        group.sort(key=lambda p: (p[1],p[0]))
        group_set = set(group)
        perimeter = sum(4-sum(n in group_set for n in neighbors(world,*p)) for p in group)
        result.append({"size": len(group), "tiles": [list(p) for p in group], "perimeter": perimeter,
                       "bounds": [min(p[0] for p in group), min(p[1] for p in group),
                                  max(p[0] for p in group), max(p[1] for p in group)]})
    return sorted(result, key=lambda p: (-p["size"], p["tiles"][0][1], p["tiles"][0][0]))


def transect(world, x1, y1, x2, y2):
    """Integer Bresenham transect, including both endpoints in travel order."""
    world.index(x1,y1)
    world.index(x2,y2)
    dx, dy = abs(x2-x1), -abs(y2-y1)
    sx, sy = (1 if x1 < x2 else -1), (1 if y1 < y2 else -1)
    error = dx+dy
    result = []
    while True:
        result.append({"x": x1, "y": y1, **world.cell(x1,y1).to_dict()})
        if (x1,y1) == (x2,y2):
            break
        double = 2*error
        if double >= dy:
            error += dy
            x1 += sx
        if double <= dx:
            error += dx
            y1 += sy
    return result


def forecast(world, days=7, every=1):
    from .engine import step
    from .model import World
    integer(days, "Forecast days", 1, 365)
    integer(every, "Sample interval", 1, 365)
    trial = World.from_dict(copy.deepcopy(world.to_dict()))
    timeline = [{"day": trial.day, "weather": trial.weather, **census(trial)}]
    for offset in range(1, days+1):
        step(trial)
        if offset % every == 0 or offset == days:
            timeline.append({"day": trial.day, "weather": trial.weather, **census(trial)})
    return {"start_day": world.day, "end_day": trial.day, "timeline": timeline, "world": trial.to_dict()}


def compare(before, after):
    if (before.width,before.height) != (after.width,after.height):
        raise ValueError("Compare gardens with the same dimensions")
    changes = []
    for i,(a,b) in enumerate(zip(before.cells,after.cells)):
        fields = {key: {"before": value, "after": b.to_dict()[key]}
                  for key,value in a.to_dict().items() if b.to_dict()[key] != value}
        terrain_a, terrain_b = before.workbench["tiles"][i], after.workbench["tiles"][i]
        fields.update({key: {"before":value,"after":terrain_b[key]}
                       for key,value in terrain_a.items() if terrain_b[key] != value})
        if fields:
            changes.append({"x":i%before.width,"y":i//before.width,"fields":fields})
    a,b = census(before),census(after)
    return {"days": after.day-before.day, "changed_tiles": len(changes), "changes": changes,
            "population_delta": {s:b["population"][s]-a["population"][s] for s in SPECIES_GUIDE},
            "coverage_delta": round(b["coverage"]-a["coverage"],2)}


def alerts(world):
    result = []
    for i,c in enumerate(world.cells):
        if not c.species:
            continue
        issues = []
        if c.vitality < 25:
            issues.append("low vitality")
        if c.moisture < 20:
            issues.append("dry soil")
        if c.nutrients < SPECIES_GUIDE[c.species]["upkeep"]:
            issues.append("hungry soil")
        if world.workbench["tiles"][i]["stress"] >= 50:
            issues.append("prolonged stress")
        if issues:
            result.append({"x":i%world.width,"y":i//world.width,"species":c.species,"issues":issues})
    return result


def report(world):
    from .notebook import task_list
    from .nursery import nursery_report
    from .engine import season
    return {"title": world.workbench["title"], "day": world.day, "season": season(world.day),
            "census": census(world), "patches": patches(world), "alerts": alerts(world),
            "nursery": nursery_report(world), "visitors": dict(world.workbench["visitors"]), "due_tasks": task_list(world,"due"),
            "beds": [{"id":b["id"],"name":b["name"],**census(world,b["tiles"])} for b in world.workbench["beds"]]}
