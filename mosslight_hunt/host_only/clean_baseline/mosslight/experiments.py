"""Controlled, repeatable garden experiments on independent virtual copies."""
from __future__ import annotations
import copy
from .analysis import census,compare
from .commands import execute
from .engine import step
from .model import World
from .validation import integer,mapping,sequence,text


def experiment(world,days,treatments,every=1):
    """Run a control and 1–8 treatments; commands occur before their offset day.

    Offset zero applies before the initial sample. Offset one applies before
    the first daily step. Every branch starts from precisely the same save.
    """
    integer(days,"Experiment days",1,120)
    integer(every,"Sample interval",1,120)
    sequence(treatments,"Treatments",8)
    if not treatments:
        raise ValueError("Supply at least one treatment")
    names = {"control"}
    validated = []
    for treatment in treatments:
        mapping(treatment,"Treatment")
        name = text(treatment.get("name"),"Treatment name",80)
        if name.casefold() in names:
            raise ValueError("Treatment names must be unique; control is reserved")
        names.add(name.casefold())
        events = sequence(treatment.get("events",[]),"Treatment events",100)
        for event in events:
            mapping(event,"Treatment event")
            integer(event.get("offset"),"Event offset",0,days)
            command = mapping(event.get("command"),"Treatment command")
            if command.get("op") == "grow":
                raise ValueError("Experiment events cannot advance time")
        validated.append({"name":name,"events":copy.deepcopy(events)})
    branches = []
    worlds = []
    for treatment in [{"name":"control","events":[]},*validated]:
        trial = World.from_dict(world.to_dict())
        samples = []
        for offset in range(days+1):
            for event in treatment["events"]:
                if event["offset"] == offset:
                    execute(trial,event["command"])
            if offset:
                step(trial)
            if offset%every == 0 or offset == days:
                samples.append({"offset":offset,"day":trial.day,**census(trial)})
        worlds.append(trial)
        branches.append({"name":treatment["name"],"samples":samples,"final":census(trial)})
    for branch,trial in zip(branches,worlds):
        delta = compare(worlds[0],trial)
        branch["against_control"] = {key:delta[key] for key in ("changed_tiles","population_delta","coverage_delta")}
    return {"start_day":world.day,"end_day":world.day+days,"branches":branches}


def rank_experiment(result,metric="coverage"):
    """Rank final coverage, richness, diversity, or mean vitality; stable ties."""
    from .validation import choice
    choice(metric,("coverage","richness","diversity","vitality"),"ranking metric")
    mapping(result,"Experiment result")
    rows = []
    for branch in sequence(result.get("branches"),"Branches",9):
        final = branch["final"]
        value = final["averages"]["vitality"] if metric == "vitality" else final[metric]
        rows.append({"name":branch["name"],"value":value})
    rows.sort(key=lambda r:-r["value"])
    for rank,row in enumerate(rows,1):
        row["rank"] = rank
    return rows
