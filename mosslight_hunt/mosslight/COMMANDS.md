# Command recipes

Every command below can be passed as the last argument to `python3 -B -m mosslight command garden.json '<command>'`, submitted in the studio's command desk, or wrapped as `{"command":<command>,"revision":N}` for `POST /api/command`. Use `python3 -B -m mosslight guide` for live argument signatures.

## Landscape and tending

```json
{"op":"tend","args":{"x":0,"y":0,"action":"plant_moss"}}
{"op":"tend_many","args":{"tiles":[[0,0],[1,0]],"action":"water"}}
{"op":"terrain","args":{"x":2,"y":2,"terrain":"pond"}}
{"op":"structure","args":{"x":1,"y":1,"structure":"shade_cloth"}}
{"op":"shade","args":{"x":0,"y":0,"shade":67}}
{"op":"transplant","args":{"x":0,"y":0,"to_x":3,"to_y":0}}
{"op":"prune","args":{"x":3,"y":0}}
{"op":"grow","args":{"days":7}}
```

Actions are water, compost, clear, plant_moss, plant_fern, plant_clover and plant_glowcap. Structures are none, shade_cloth, rain_barrel, bee_house and log. Terrain is soil, sand, peat, pond or stone.

## Materials and propagation

These operations have maturity, resource and empty-ground requirements; see [the workbench guide](WORKBENCH.md).

```json
{"op":"harvest","args":{"x":0,"y":0}}
{"op":"collect_seed","args":{"x":1,"y":0}}
{"op":"sow","args":{"x":2,"y":0,"species":"moss"}}
{"op":"craft","args":{"recipe":"mulch","amount":2}}
{"op":"apply_material","args":{"x":0,"y":0,"material":"mulch"}}
{"op":"cutting","args":{"x":0,"y":0}}
{"op":"nursery_seed","args":{"species":"clover","count":2}}
{"op":"nursery_water","args":{"ident":1}}
{"op":"plant_out","args":{"ident":1,"x":3,"y":1}}
{"op":"nursery_discard","args":{"ident":1}}
```

IDs in examples are illustrative: use the `result.id` returned by creation, the save, the report or the browser list to find the actual ID. The propagation bench is independent of grid watering.

## Field notebook

```json
{"op":"rename","args":{"title":"The lantern hollow"}}
{"op":"note","args":{"content":"The moss has crossed the stone path.","labels":["moss","dawn"],"tile":[2,3]}}
{"op":"edit_note","args":{"ident":1,"content":"The moss approached the path.","labels":["moss"]}}
{"op":"task","args":{"content":"Check nursery water","due":5}}
{"op":"complete_task","args":{"ident":2,"done":true}}
{"op":"specimen","args":{"x":2,"y":3,"label":"First crossing"}}
{"op":"delete_entry","args":{"collection":"notes","ident":1}}
```

Deleting an entry supports notes, tasks and specimens. Search and exports are read endpoints rather than mutation commands.

## Beds, schedules and conditional care

```json
{"op":"bed","args":{"name":"Fern hollow","tiles":[[1,1],[2,1],[1,2],[2,2]]}}
{"op":"schedule","args":{"name":"Morning pour","day":5,"tiles":[[1,1],[2,1]],"action":"water","repeat":3,"runs":4}}
{"op":"cancel_plan","args":{"ident":2}}
{"op":"rule","args":{"name":"Dry roots","tiles":[[1,1],[2,1]],"metric":"moisture","operator":"below","threshold":30,"action":"water"}}
{"op":"enable_rule","args":{"ident":3,"enabled":false}}
{"op":"delete_rule","args":{"ident":3}}
{"op":"delete_bed","args":{"ident":1}}
```

Plans require a future first day. Tasks can be overdue. Plans and rules keep their selected locations when a bed is changed later.

## Designs and measurements

To apply an exported blueprint, read the JSON and pass it as `data`:

```python
import json
from mosslight.commands import execute
from mosslight.model import load, save
from mosslight.exchange import transform_blueprint

world = load("garden.json")
with open("hollow-pattern.json", encoding="utf-8") as source:
    pattern = transform_blueprint(json.load(source), turns=1, mirror=True)
execute(world, {"op": "blueprint", "args": {
    "data": pattern, "x": 2, "y": 2, "overwrite": True}})
save(world, "garden.json")
```

CSV imports use `{"op":"import_csv","args":{"content":"x,y,species,...\n..."}}`. The CSV must contain every tile and exactly the exported columns. Notebook entries and plans remain available after the survey import.

Python also exposes `gardening.brush`, `gardening.rectangle`, `analysis.transect`, `analysis.patches`, `analysis.suitability`, `analysis.census`, `notebook.search_notes`, `weather.next_weather`, and `experiments.rank_experiment`. These read/selection functions do not mutate the garden.

## Controlled experiment files

An experiment file is a JSON array of named treatments. All treatments and the automatic control start from the same input save. Events at offset 0 affect the initial sample; offset 1 acts before the first day of ecology. A treatment can contain several interventions, in authored order, including events later in the experiment.

```json
[
  {"name":"Shelter","events":[
    {"offset":0,"command":{"op":"structure","args":{"x":0,"y":0,"structure":"shade_cloth"}}}
  ]},
  {"name":"Extra water","events":[
    {"offset":1,"command":{"op":"tend","args":{"x":0,"y":0,"action":"water"}}},
    {"offset":4,"command":{"op":"tend","args":{"x":0,"y":0,"action":"water"}}}
  ]}
]
```

Run with `python3 -B -m mosslight experiment garden.json treatments.json --days 7 --every 2`. The result includes the control and each treatment's census timeline and final differences. The source file is untouched.
