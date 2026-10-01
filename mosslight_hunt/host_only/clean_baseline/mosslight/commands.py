"""One transactional command vocabulary for scripts, HTTP, and the CLI."""
from __future__ import annotations
import copy
from . import gardening as tools, habitat, notebook, planning, nursery
from .engine import act, step
from .model import World
from .validation import mapping


def _dispatch(world, op, args):
    functions = {
        "tend": act, "grow": step, "tend_many": tools.tend_many,
        "transplant": tools.transplant, "prune": tools.prune, "harvest": tools.harvest,
        "collect_seed": tools.collect_seed, "sow": tools.sow, "craft": tools.craft,
        "apply_material": tools.apply_material, "terrain": habitat.set_terrain,
        "structure": habitat.set_structure, "shade": habitat.set_shade,
        "note": notebook.add_note, "edit_note": notebook.edit_note,
        "delete_entry": notebook.delete_entry, "specimen": notebook.press_specimen,
        "task": notebook.add_task, "complete_task": notebook.complete_task,
        "rename": notebook.rename_garden, "bed": planning.add_bed,
        "delete_bed": planning.delete_bed, "schedule": planning.schedule,
        "cancel_plan": planning.cancel_plan, "rule": planning.add_rule,
        "enable_rule": planning.enable_rule, "delete_rule": planning.delete_rule,
    }
    functions.update(nursery_seed=nursery.start_seeds, cutting=nursery.take_cutting,
                     nursery_water=nursery.water_batch, plant_out=nursery.plant_out,
                     nursery_discard=nursery.discard_batch)
    from .exchange import apply_blueprint, import_csv
    functions.update(blueprint=apply_blueprint, import_csv=import_csv)
    if not isinstance(op,str) or op not in functions:
        raise ValueError("Unknown command")
    try:
        result = functions[op](world, **args)
    except TypeError as exc:
        raise ValueError(f"Invalid arguments for {op}: {exc}") from exc
    return None if isinstance(result,World) else result


def execute(world, command):
    mapping(command,"Command")
    if set(command) - {"op","args"}:
        raise ValueError("Command accepts only op and args")
    args = mapping(command.get("args",{}),"Command arguments")
    trial = World.from_dict(copy.deepcopy(world.to_dict()))
    result = _dispatch(trial,command.get("op"),args)
    # Validate the complete output before publishing any part of a command.
    trial = World.from_dict(trial.to_dict())
    trial.revision = world.revision+1
    world.__dict__.update(trial.__dict__)
    return copy.deepcopy(result)


def command_catalog():
    """Machine-readable command signatures, kept in step with Python functions."""
    import inspect
    names = {
        "tend":act,"grow":step,"tend_many":tools.tend_many,"transplant":tools.transplant,
        "prune":tools.prune,"harvest":tools.harvest,"collect_seed":tools.collect_seed,
        "sow":tools.sow,"craft":tools.craft,"apply_material":tools.apply_material,
        "terrain":habitat.set_terrain,"structure":habitat.set_structure,"shade":habitat.set_shade,
        "note":notebook.add_note,"edit_note":notebook.edit_note,"delete_entry":notebook.delete_entry,
        "specimen":notebook.press_specimen,"task":notebook.add_task,"complete_task":notebook.complete_task,
        "rename":notebook.rename_garden,"bed":planning.add_bed,"delete_bed":planning.delete_bed,
        "schedule":planning.schedule,"cancel_plan":planning.cancel_plan,"rule":planning.add_rule,
        "enable_rule":planning.enable_rule,"delete_rule":planning.delete_rule,
    }
    names.update(nursery_seed=nursery.start_seeds, cutting=nursery.take_cutting,
                 nursery_water=nursery.water_batch, plant_out=nursery.plant_out,
                 nursery_discard=nursery.discard_batch)
    from .exchange import apply_blueprint,import_csv
    names.update(blueprint=apply_blueprint,import_csv=import_csv)
    return {name:{key: {"required":p.default is inspect.Parameter.empty,
                       "default":None if p.default is inspect.Parameter.empty else p.default}
                  for key,p in inspect.signature(function).parameters.items() if key != "world"}
            for name,function in names.items()}
