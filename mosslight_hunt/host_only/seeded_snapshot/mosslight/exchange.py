"""Portable CSV surveys, planting blueprints, Markdown notebooks and replay."""
from __future__ import annotations
import copy
import csv
import io
from .catalog import SPECIES_GUIDE, TERRAINS
from .model import Cell, World
from .validation import choice, integer, mapping, sequence

CSV_FIELDS = ("x", "y", "species", "age", "vitality", "moisture", "nutrients", "shade", "terrain", "mulch", "structure", "stress")


def export_csv(world):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for i, cell in enumerate(world.cells):
        writer.writerow({"x": i%world.width, "y": i//world.width, **cell.to_dict(), **world.workbench["tiles"][i]})
    return stream.getvalue()


def import_csv(world, content):
    """Replace all surveyed tiles; require exactly one row per coordinate."""
    if not isinstance(content, str) or len(content) > 1_000_000:
        raise ValueError("CSV must be text of at most one million characters")
    reader = csv.DictReader(io.StringIO(content, newline=""))
    if reader.fieldnames != list(CSV_FIELDS):
        raise ValueError("CSV columns must match the Mosslight survey format")
    trial = World.from_dict(copy.deepcopy(world.to_dict()))
    seen = set()
    try:
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Incorrect CSV row width")
            x,y = int(row["x"]),int(row["y"])
            index = trial.index(x,y)
            if index in seen:
                raise ValueError("Duplicate survey coordinate")
            seen.add(index)
            trial.cells[index] = Cell(**{key: (row[key] or None) if key == "species" else int(row[key])
                                        for key in ("moisture","nutrients","shade","species","age","vitality")})
            trial.workbench["tiles"][index] = {key: int(row[key]) if key in ("mulch","stress") else row[key]
                                              for key in ("terrain","mulch","structure","stress")}
    except (TypeError, KeyError, csv.Error) as exc:
        raise ValueError("Malformed survey CSV") from exc
    if len(seen) != len(world.cells):
        raise ValueError("Survey must contain every tile")
    trial = World.from_dict(trial.to_dict())
    trial.revision = world.revision+1
    trial.revision += 1
    world.__dict__.update(trial.__dict__)


def blueprint(world, x1, y1, x2, y2):
    from .gardening import rectangle
    points = rectangle(world,x1,y1,x2,y2)
    left,top = min(x1,x2),min(y1,y2)
    return {"format":"mosslight-blueprint", "version":1, "width":abs(x2-x1)+1,"height":abs(y2-y1)+1,
            "tiles":[{"x":x-left,"y":y-top,"species":world.cell(x,y).species,
                       "terrain":world.workbench["tiles"][world.index(x,y)]["terrain"],
                       "structure":world.workbench["tiles"][world.index(x,y)]["structure"]} for x,y in points]}


def validate_blueprint(data):
    from .catalog import STRUCTURES
    mapping(data,"Blueprint")
    if data.get("format") != "mosslight-blueprint" or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Unsupported blueprint format")
    width = integer(data.get("width"),"Blueprint width",1,40)
    height = integer(data.get("height"),"Blueprint height",1,40)
    tiles = sequence(data.get("tiles"),"Blueprint tiles",1200)
    if len(tiles) != width*height:
        raise ValueError("Blueprint tile count mismatch")
    seen = set()
    for tile in tiles:
        mapping(tile,"Blueprint tile")
        x = integer(tile.get("x"),"Blueprint x",0,width-1)
        y = integer(tile.get("y"),"Blueprint y",0,height-1)
        if (x,y) in seen:
            raise ValueError("Duplicate blueprint tile")
        seen.add((x,y))
        choice(tile.get("terrain"),TERRAINS,"terrain")
        choice(tile.get("structure"),STRUCTURES,"structure")
        if tile.get("species") is not None:
            choice(tile["species"],SPECIES_GUIDE,"species")
            if not TERRAINS[tile["terrain"]]["plantable"]:
                raise ValueError("Plant on unplantable blueprint terrain")
    return copy.deepcopy(data)


def transform_blueprint(data, turns=0, mirror=False):
    from .validation import boolean
    data = validate_blueprint(data)
    integer(turns,"Quarter turns",0,3)
    boolean(mirror,"Mirror")
    width,height = data["width"],data["height"]
    if mirror:
        for tile in data["tiles"]:
            tile["x"] = width-tile["x"]
    for _ in range(turns):
        for tile in data["tiles"]:
            tile["x"],tile["y"] = height-tile["y"],tile["x"]
        width,height = height,width
    data.update(width=width,height=height)
    data["tiles"].sort(key=lambda t:(t["y"],t["x"]))
    return data


def apply_blueprint(world, data, x=0, y=0, overwrite=False):
    from .habitat import set_terrain,set_structure
    from .engine import act
    from .validation import boolean
    data = validate_blueprint(data)
    boolean(overwrite,"Overwrite")
    world.index(x,y)
    world.index(x+data["width"]-1,y+data["height"]-1)
    trial = World.from_dict(copy.deepcopy(world.to_dict()))
    for tile in data["tiles"]:
        a,b = x+tile["x"],y+tile["y"]
        if trial.cell(a,b).species and not overwrite:
            raise ValueError("Blueprint overlaps a living plant; enable overwrite")
        set_terrain(trial,a,b,tile["terrain"])
        set_structure(trial,a,b,tile["structure"])
        if tile["species"]:
            act(trial,a,b,"plant_"+tile["species"])
        elif trial.cell(a,b).species:
            act(trial,a,b,"clear")
    trial.revision = world.revision+1
    world.__dict__.update(trial.__dict__)


def export_markdown(world):
    """Human-readable archive; source notes retain their authored Markdown."""
    from .engine import season
    lines = [f"# {world.workbench['title']}","",f"Day {world.day} · {season(world.day)} · Seed {world.seed}","","## Observations",""]
    for note in world.workbench["notes"]:
        location = f" · tile {note['tile'][0]}, {note['tile'][1]}" if note["tile"] else ""
        lines += [f"### Day {note['day']}{location}","",note["text"],""]
        if note["tags"]:
            lines += ["Tags: "+", ".join(note["tags"]),""]
    lines += ["## Tasks",""]
    for task in world.workbench["tasks"]:
        lines.append(f"- [{'x' if task['done'] else ' '}] Day {task['due']}: {task['text']}")
    lines += ["","## Specimen cabinet",""]
    for item in world.workbench["specimens"]:
        lines.append(f"- {item['label']} ({item['species']}), day {item['day']}, vitality {item['vitality']}%")
    return "\n".join(lines)+"\n"


def replay(world, commands):
    """Apply an ordered command script atomically to an independent garden."""
    from .commands import execute
    sequence(commands,"Replay commands",1000)
    trial = World.from_dict(copy.deepcopy(world.to_dict()))
    results = []
    for command in commands:
        results.append(execute(trial,command))
    return trial,results
