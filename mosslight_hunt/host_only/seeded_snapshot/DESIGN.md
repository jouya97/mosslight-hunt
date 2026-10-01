# Design: a garden with a field station

Mosslight treats a terrarium as both a living postcard and a place to practice observation. The garden has a deterministic ecology; tending tools change it; the notebook records what happened; the field station measures differences and lets the gardener try future care on copies.

## State and boundaries

The original `Cell` retains moisture, nutrients, base shade, species, age and vitality. Version 2 adds a `workbench` object containing parallel tile habitat settings, inventories, nursery batches, observations, specimens, tasks, named beds, plans, care rules, wildlife and daily history. All extension defaults are neutral, so a version 1 garden retains its original ecology after migration.

`World.from_dict` validates portable state; `state.validate` checks workbench types, ranges, collection limits, unique IDs and coordinates. ID allocation is shared by all collections. `to_dict` returns independent mutable data. JSON saves carry an explicit version. No random generator state, dates from the wall clock, filesystem locations, or server history is serialized.

`commands.execute` clones a world, dispatches one operation, validates the result, and commits it with a single revision increment. It is the application mutation boundary used by the command CLI and HTTP API. Failed commands leave the original object unchanged. `replay` composes commands on another copy. Lower-level functions are also public and validate their own arguments; they can increment the revision for individual actions, while the command boundary produces one revision for the complete command.

The HTTP server serializes edits under a lock. Persistence occurs before the replacement world is published. Undo and redo hold independent save snapshots, capped at 30 user edits. Restoration takes a fresh revision; branching after undo clears redo. Legacy unconditional imports preserve a save's revision for compatibility. Imports with a revision check get a fresh revision.

## Daily order

1. Increment day; execute due care plans by ID. A plan's complete tile set succeeds or fails together.
2. Select weather from seed and day. Read the old grid for moisture exchange and propagation parents.
3. Resolve terrain moisture, effective shade, plant nutrient consumption and comfort, deaths, then births.
4. Evaluate all enabled care-rule conditions against the same resulting grid. Apply matching actions by rule ID and tile order.
5. Advance nursery batches, decay mulch, return log nutrients, update stress, count visitors and append the day's census.

A newly born plant does not become a propagation parent on the same day. A scheduled planting does participate in that day's ecology. A rule planting occurs after ecology and starts at age zero. The calendar and almanac reveal deterministic weather but do not advance time.

## Distinct workbench systems

- Habitat traits modify water and light. Wildlife is a derived census, not an independent source of randomness.
- Harvesting and seed collection have separate maturity and vitality gates. Basic tending remains freely available, so materials are an optional gardening workflow.
- The propagation bench occupies no grid tiles. Seed batches and cuttings need water; ready plants retain their nursery vigor when planted out.
- Notes and specimens are archival observations. Tasks are reminders; they do not silently perform garden actions.
- Beds store coordinate sets. Plans and rules copy their coordinates when created, so deleting or changing a bed cannot redirect existing care.
- Forecasts run the ordinary ecology on independent saves. Experiments run a control plus named treatments with before-day interventions, sharing the same initial world and weather.
- CSV transfers all tile measurements; blueprints transfer only terrain, structures and species. Those formats serve different purposes and have separate validation rules.

## Interfaces

The browser uses the same command vocabulary as scripts and the CLI. Read endpoints return machine-readable data suitable for local tools. The SVG renderer escapes authored titles and uses only local vector primitives. Notebook text is placed in DOM text nodes; authored text is never treated as HTML.

| Method | Route | Data |
| --- | --- | --- |
| GET | `/api/world` | Save, summary, undo/redo counts |
| GET | `/api/catalog` | Field guide and all command argument signatures |
| GET | `/api/report` | Census, patches, alerts, due tasks, beds, nursery |
| GET | `/api/forecast?days=7&every=1` | Timeline and future save |
| GET | `/api/recommend?species=moss&limit=10` | Ranked empty planting locations |
| GET | `/api/notes?q=wet&tag=pond` | Filtered notebook observations |
| GET | `/api/almanac?days=12` | Future weather, rainfall totals, dry spells |
| GET | `/api/calendar?days=12` | Calendar with open tasks and plan occurrences |
| GET | `/api/nursery` | Batches with readiness and water advice |
| GET | `/api/transect?x1=0&y1=0&x2=3&y2=3` | Inclusive tile measurements along a line |
| GET | `/api/blueprint?x1=0&y1=0&x2=3&y2=2` | Rectangular reusable design |
| GET | `/api/svg?layer=art` | Interactive SVG; any catalog layer |
| GET | `/api/history.svg?metric=moisture` | Daily history SVG |
| GET | `/api/survey.csv`, `/api/notebook.md` | Portable text exports |
| POST | `/api/command` | `{"command":{"op":"...","args":{...}},"revision":0}` |
| POST | `/api/replay` | `{"commands":[...],"revision":0}` |
| POST | `/api/step`, `/api/action` | Compatible original day/action shortcuts |
| POST | `/api/new` | Seed and optional width/height |
| POST | `/api/import` | `{"world":<save>,"revision":0}` |
| POST | `/api/undo`, `/api/redo` | Optional revision |
| POST | `/api/experiment` | Days, sampling interval, named treatment events |

Mutations accept an optional integer revision. A stale or noninteger revision returns 409. Invalid bodies and arguments return 400; a filesystem failure returns 500 without publishing the edit. Unknown routes return 404. Bodies are limited to 4 MB. Responses disable caching. The original GET assets are `/`, `/app.js`, and `/app.css`.

## Visual language

The garden illustration keeps velvet moss clusters, branching ferns, clover petals and glowing mushroom caps. Terrain uses distinct colors and structures have small marks. Numeric map layers use one fixed 0–100 color scale so separate days remain comparable. History prints use fixed percentage or tile-count axes and actual day spacing. Every export is a standalone SVG without external fonts or raster assets.

See [BEHAVIORS.md](BEHAVIORS.md) for numerical contracts and [COMMANDS.md](COMMANDS.md) for working examples.
