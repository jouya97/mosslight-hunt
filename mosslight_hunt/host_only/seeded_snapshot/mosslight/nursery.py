"""A small propagation bench for seeds and cuttings, away from the grid."""
from __future__ import annotations
from .catalog import SPECIES_GUIDE, TERRAINS
from .notebook import find_entry, _room
from .state import identifier
from .validation import choice, integer

MATURITY = {"moss":3, "fern":4, "clover":2, "glowcap":5}


def start_seeds(world, species, count=1):
    choice(species,SPECIES_GUIDE,"species")
    integer(count,"Seed count",1,20)
    if world.workbench["seeds"][species] < count:
        raise ValueError("Not enough stored seeds")
    _room(world,"nursery")
    entry = _batch(world,species,count,"seed")
    world.workbench["seeds"][species] -= count
    return entry


def take_cutting(world,x,y):
    cell = world.cell(x,y)
    if not cell.species or cell.age < 5 or cell.vitality < 60:
        raise ValueError("A cutting needs age 5 and vitality 60")
    _room(world,"nursery")
    entry = _batch(world,cell.species,1,"cutting")
    cell.vitality -= 12
    return entry


def _batch(world,species,count,source):
    entry = {"id":identifier(world.workbench),"species":species,"count":count,
             "source":source,"day":world.day,"age":0,"hydration":3,"vitality":60,"status":"growing"}
    world.workbench["nursery"].append(entry)
    world.revision += 1
    return entry.copy()


def water_batch(world,ident):
    batch = find_entry(world,"nursery",ident)
    if batch["status"] not in ("growing","ready"):
        raise ValueError("Only living nursery batches can be watered")
    batch["hydration"] = min(3,batch["hydration"]+1)
    world.revision += 1


def advance_nursery(world):
    from .engine import log
    for batch in world.workbench["nursery"]:
        if batch["status"] not in ("growing","ready"):
            continue
        if batch["hydration"]:
            batch["hydration"] -= 1
            batch["age"] += 1
            batch["vitality"] = min(100,batch["vitality"]+(3 if batch["status"] == "growing" else 0))
        else:
            batch["age"] += 1
            batch["vitality"] = max(0,batch["vitality"]-20)
        if batch["vitality"] == 0:
            batch["status"] = "failed"
            log(world,f"Nursery batch {batch['id']} dried out.")
        elif batch["age"] >= MATURITY[batch["species"]] and batch["status"] == "growing":
            batch["status"] = "ready"
            log(world,f"A batch of {batch['species']} is ready to plant.")


def plant_out(world,ident,x,y):
    batch = find_entry(world,"nursery",ident)
    cell = world.cell(x,y)
    terrain = world.workbench["tiles"][world.index(x,y)]["terrain"]
    if batch["status"] != "ready" or batch["count"] < 1:
        raise ValueError("The nursery batch is not ready")
    if cell.species or not TERRAINS[terrain]["plantable"]:
        raise ValueError("Plant seedlings on empty plantable ground")
    cell.species,cell.age,cell.vitality = batch["species"],0,batch["vitality"]
    cell.nutrients = max(0,cell.nutrients-4) if batch["count"] == 1 else cell.nutrients
    batch["count"] -= 1
    if batch["count"] == 0:
        batch["status"] = "planted"
    world.revision += 1


def discard_batch(world,ident):
    batch = find_entry(world,"nursery",ident)
    if batch["status"] in ("discarded","planted"):
        raise ValueError("This nursery batch is already closed")
    batch["status"] = "discarded"
    batch["count"] = 0
    world.revision += 1


def nursery_report(world):
    import copy
    result = []
    for batch in world.workbench["nursery"]:
        entry = copy.deepcopy(batch)
        entry["days_to_ready"] = max(0,MATURITY[batch["species"]]-batch["age"])
        entry["needs_water"] = batch["hydration"] == 0 and batch["status"] in ("growing","ready")
        result.append(entry)
    return result
