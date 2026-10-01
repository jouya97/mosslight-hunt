"""Terrain, passive garden structures, and seasonal wildlife."""
from __future__ import annotations
from .catalog import TERRAINS, STRUCTURES
from .validation import choice, integer


def effective_shade(world, index):
    cell = world.cells[index]
    x, y = index % world.width, index // world.width
    canopy = 0
    for a, b in ((x, y), (x-1, y), (x+1, y), (x, y-1)):
        if 0 <= a < world.width and 0 <= b < world.height:
            structure = world.workbench["tiles"][b * world.width + a]["structure"]
            canopy += 15 if structure == "shade_cloth" else 0
    return min(100, cell.shade + canopy)


def set_terrain(world, x, y, terrain):
    from .engine import log
    choice(terrain, TERRAINS, "terrain")
    index = world.index(x, y)
    tile, cell = world.workbench["tiles"][index], world.cells[index]
    tile["terrain"] = terrain
    if not TERRAINS[terrain]["plantable"]:
        cell.species, cell.age, cell.vitality = None, 0, 0
        tile["stress"] = 0
        tile["mulch"] = 0
        cell.moisture = 100 if terrain == "pond" else 0
    world.revision += 1
    log(world, f"Tile {x+1}, {y+1} becomes {terrain}.")


def set_structure(world, x, y, structure):
    choice(structure, STRUCTURES, "structure")
    world.workbench["tiles"][world.index(x, y)]["structure"] = structure
    world.revision += 1


def set_shade(world, x, y, shade):
    integer(shade, "Shade", 0, 100)
    world.cell(x, y).shade = shade
    world.revision += 1


def water_balance(world, index, before, neighbor_mean, rain, evaporation):
    """Return daily moisture. Passive effects are independent of visit order."""
    tile = world.workbench["tiles"][index]
    terrain = tile["terrain"]
    if terrain in ("pond", "stone"):
        return 100 if terrain == "pond" else 0
    trait = TERRAINS[terrain]
    evaporation = max(0, evaporation + trait["evaporation"] - tile["mulch"] // 20)
    gain = rain + (trait["rain_bonus"] if rain else 0)
    if tile["structure"] == "rain_barrel":
        gain += 6
        from .semantics import barrel_adjustment
        gain += barrel_adjustment(before)
    x, y = index % world.width, index // world.width
    pond_neighbors = sum(
        world.workbench["tiles"][b * world.width+a]["terrain"] == "pond"
        for a, b in ((x-1,y), (x+1,y), (x,y-1), (x,y+1))
        if 0 <= a < world.width and 0 <= b < world.height
    )
    return max(0, min(100, before + (neighbor_mean-before)//4 + gain - evaporation + 2*pond_neighbors))


def after_day(world, births, losses):
    """Update mulch decay, stress, visitors and a bounded daily census."""
    from .analysis import census
    from .engine import season
    for cell, tile in zip(world.cells, world.workbench["tiles"]):
        if tile["mulch"]:
            tile["mulch"] -= 1
            if world.day % 3 == 0 and tile["mulch"] > 0:
                cell.nutrients = min(100, cell.nutrients + 1)
        if tile["structure"] == "log":
            cell.nutrients = min(100, cell.nutrients + 2)
        if cell.species:
            tile["stress"] = min(100, tile["stress"]+5) if cell.vitality <= 30 else max(0, tile["stress"]-3)
        else:
            tile["stress"] = 0
    healthy_clover = sum(c.species == "clover" and c.vitality >= 50 for c in world.cells)
    houses = sum(t["structure"] == "bee_house" for t in world.workbench["tiles"])
    glowing = sum(c.species == "glowcap" and c.vitality >= 40 for c in world.cells)
    wet_rich = sum(c.moisture >= 45 and c.nutrients >= 40 and t["terrain"] == "soil"
                   for c, t in zip(world.cells, world.workbench["tiles"]))
    world.workbench["visitors"] = {
        "bees": 0 if season(world.day) == "Hush" else healthy_clover//3 + min(houses, healthy_clover),
        "fireflies": int(glowing / 2 + 0.5), "worms": wet_rich//4,
    }
    info = census(world)
    world.workbench["history"].append({"day": world.day, "occupied": info["occupied"],
        "moisture": info["averages"]["moisture"], "nutrients": info["averages"]["nutrients"],
        "vitality": info["averages"]["vitality"], "births": births, "losses": losses})
    world.workbench["history"] = world.workbench["history"][-240:]
