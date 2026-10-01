"""Precise garden tools, harvests, seed banking and material recipes."""
from __future__ import annotations
import copy
from .catalog import RECIPES, SPECIES_GUIDE, TERRAINS
from .validation import choice, coordinates, integer


def rectangle(world, x1, y1, x2, y2):
    world.index(x1, y1)
    world.index(x2, y2)
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    return [(x, y) for y in range(top, bottom+1) for x in range(left, right+1)]


def brush(world, x, y, radius=1, shape="diamond"):
    world.index(x, y)
    integer(radius, "Radius", 0, 40)
    choice(shape, ("diamond", "square", "circle"), "brush shape")
    result = []
    for b in range(max(0, y-radius), min(world.height, y+radius+1)):
        for a in range(max(0, x-radius), min(world.width, x+radius+1)):
            dx, dy = abs(a-x), abs(b-y)
            if shape == "diamond" and dx+dy > radius:
                continue
            if shape == "circle" and dx*dx+dy*dy > radius*radius:
                continue
            result.append((a, b))
    return result


def tend_many(world, tiles, action):
    """All selected tiles succeed or the complete operation is rolled back."""
    from .engine import act
    from .model import World
    points = coordinates(world, tiles)
    trial = World.from_dict(copy.deepcopy(world.to_dict()))
    for x, y in points:
        act(trial, x, y, action)
    trial.revision = world.revision + 1
    world.__dict__.update(trial.__dict__)
    return len(points)


def transplant(world, x, y, to_x, to_y):
    source = world.cell(x, y)
    target = world.cell(to_x, to_y)
    if (x, y) == (to_x, to_y):
        raise ValueError("Choose a different destination")
    if source.species is None or target.species is not None:
        raise ValueError("Move a living plant to an empty tile")
    tile = world.workbench["tiles"][world.index(to_x, to_y)]
    if not TERRAINS[tile["terrain"]]["plantable"]:
        raise ValueError("Destination terrain cannot support plants")
    target.species, target.age, target.vitality = source.species, source.age, max(1, source.vitality-10)
    source.species, source.age, source.vitality = None, 0, 0
    source_index = world.index(x, y)
    tile["stress"] = world.workbench["tiles"][source_index]["stress"]
    world.workbench["tiles"][source_index]["stress"] = 0
    world.revision += 1


def prune(world, x, y):
    cell = world.cell(x, y)
    if cell.species is None:
        raise ValueError("There is no plant to prune")
    cell.age = max(0, cell.age-5)
    cell.vitality = min(100, cell.vitality+8)
    world.revision += 1


def harvest(world, x, y):
    cell = world.cell(x, y)
    if cell.species is None:
        raise ValueError("There is no plant to harvest")
    info = SPECIES_GUIDE[cell.species]
    if cell.age < info["harvest_age"] or cell.vitality < 40:
        raise ValueError(f"Harvest needs age {info['harvest_age']} and vitality 40")
    amount = info["yield"] + (1 if cell.vitality >= 80 else 0)
    stock = world.workbench["inventory"]
    if stock[info["resource"]] + amount > 1_000_000:
        raise ValueError("Inventory is full")
    stock[info["resource"]] += amount
    cell.age = 0
    cell.vitality = max(1, cell.vitality-15)
    world.revision += 1
    return {info["resource"]: amount}


def collect_seed(world, x, y):
    cell = world.cell(x, y)
    if cell.species is None or cell.age < 5 or cell.vitality < 50:
        raise ValueError("Seed collection needs a plant aged 5 with vitality 50")
    seeds = world.workbench["seeds"]
    if seeds[cell.species] >= 1_000_000:
        raise ValueError("Seed bank is full")
    seeds[cell.species] += 1
    cell.age = 0
    cell.vitality -= 5
    world.revision += 1
    return cell.species


def sow(world, x, y, species):
    choice(species, SPECIES_GUIDE, "species")
    cell = world.cell(x, y)
    if cell.species:
        raise ValueError("Sow into an empty tile")
    if world.workbench["seeds"][species] < 1:
        raise ValueError("No stored seed for this species")
    from .engine import act
    act(world, x, y, "plant_"+species)
    world.workbench["seeds"][species] -= 1


def craft(world, recipe, amount=1):
    choice(recipe, RECIPES, "recipe")
    integer(amount, "Craft amount", 1, 1000)
    info = RECIPES[recipe]
    stock = world.workbench["inventory"]
    for key, cost in info["cost"].items():
        if stock[key] < cost*amount:
            raise ValueError(f"Need {cost*amount} {key}")
    for key, count in info["makes"].items():
        if stock[key] + count*amount > 1_000_000:
            raise ValueError("Inventory is full")
    for key, cost in info["cost"].items():
        stock[key] -= cost*amount
    for key, count in info["makes"].items():
        stock[key] += count*amount
    world.revision += 1
    return {key: value*amount for key, value in info["makes"].items()}


def apply_material(world, x, y, material):
    choice(material, ("compost", "mulch", "tonic"), "material")
    cell = world.cell(x, y)
    tile = world.workbench["tiles"][world.index(x, y)]
    if not TERRAINS[tile["terrain"]]["plantable"]:
        raise ValueError("Materials need plantable ground")
    if material == "tonic" and cell.species is None:
        raise ValueError("Tonic needs a living plant")
    if world.workbench["inventory"][material] < 1:
        raise ValueError(f"No {material} in inventory")
    world.workbench["inventory"][material] -= 1
    if material == "compost":
        cell.nutrients = min(100, cell.nutrients+40)
    elif material == "mulch":
        tile["mulch"] = min(100, tile["mulch"]+30)
    else:
        cell.vitality = min(100, cell.vitality+25)
        tile["stress"] = max(0, tile["stress"]-20)
    world.revision += 1
