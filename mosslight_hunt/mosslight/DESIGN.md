# Design: a garden with a field station

Mosslight combines a living illustration with a place to practice observation.
A garden can be tended directly, recorded in a notebook and explored through
repeatable experiments. The studio, command line and Python modules work with the
same portable garden.

## A portable workspace

JSON saves retain the landscape, plants, habitat, resources, nursery, notebook,
care arrangements and daily observations. Opening an older supported save gives
it the defaults needed for current tools. A garden's seed and care history make
its future reproducible across the interfaces that use the same ecology release.

Experiments and forecasts preserve their starting gardens. Saved campaigns,
studies and histories extend this workflow across sessions, retaining the inputs
and provenance needed to review earlier results. See the [guide index](BEHAVIORS.md)
for each workflow.

## Interfaces

Use `python3 -B -m mosslight guide` or `/api/catalog` for the command vocabulary,
argument signatures, species traits and recipes. [Command recipes](COMMANDS.md)
show typical requests. Python modules also expose the underlying garden tools
for local scripts.

The studio is a local HTTP application. Read endpoints return measurements or
exports; edits use JSON requests. Revision checks let a caller detect that the
garden changed after it was read. Commands succeed as complete edits, and failed
edits preserve the prior garden. [Saving and sharing](PORTABILITY.md) explains
persistence, imports and session undo.

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

Mutations accept an optional integer revision. A stale or noninteger revision returns 409. Invalid bodies and arguments return 400; a filesystem failure returns 500 with the previous garden preserved. Unknown routes return 404. Bodies are limited to 4 MB. Responses disable caching. The original GET assets are `/`, `/app.js`, and `/app.css`.

## Visual language

Mosslight uses moss clusters, branching ferns, clover petals and glowing mushroom
caps to make a garden readable. Terrain has distinct colors and structures have
small marks. Measurement maps use a shared scale, and history prints preserve the
spacing between observation dates.

The studio serves its assets locally. Authored notebook text and titles remain
text, and standalone SVG exports need no external fonts or raster assets.
