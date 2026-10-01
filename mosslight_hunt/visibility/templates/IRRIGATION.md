# Irrigation design

Compare watering schedules before choosing a setup for a garden. An irrigation
design combines a saved world, a pipe layout, available tank water and the valve
settings you are willing to use. Mosslight compares schedules over the requested
number of days and reports the resulting garden, daily water deliveries and
ecology measurements.

## Create and compare schedules

Use `mosslight.irrigation.definition(world, layout, choices, days, supply,
refill=None, version="classic-1")` to prepare a design, then pass it to `solve`.
`supply` is the starting tank water. An optional `refill` list supplies one amount
for each day; the default is no refills. `choices` lists the allowed valve
settings, each with a unique `name` and an `open` list of outlet names. Include an
empty `open` list if leaving all valves closed is an option.

The chosen schedule gives the highest total garden vitality at the end of the
design period. When schedules finish with equal vitality, the one retaining more
tank water is preferred. Several schedules may be equally good. The comparison
covers the full period, including the effects of watering on later days.

To evaluate a schedule of your own, use `replay(problem, schedule)`, where
`schedule` contains one choice index per day. Use short design periods and a small
set of practical valve settings to begin with; comparing many choices over long
periods can take substantial time and memory. Preparing and running a design
leaves the original garden available for other work.

## Describe the layout

A layout contains a `source` junction name, a `pipes` list and an `outlets`
mapping. Each pipe specifies `from`, `to` and an integer `capacity`. Water moves
in the indicated direction. Pipes can share junctions and can run alongside each
other or in opposite directions. Each outlet specifies an integer `demand` and a
nonempty list of `[x, y]` garden tiles. A tile can belong to only one outlet.

```json
{
  "source": "tank",
  "pipes": [
    {"from": "tank", "to": "north", "capacity": 20},
    {"from": "tank", "to": "south", "capacity": 20}
  ],
  "outlets": {
    "north": {"demand": 20, "tiles": [[0, 0], [1, 0]]},
    "south": {"demand": 20, "tiles": [[0, 3], [1, 3]]}
  }
}
```

Daily refills enter the tank before watering. The system delivers as much water
as the open outlets, available supply and pipe capacities permit. Deliveries use
whole units. The order of your layout entries determines which allocation is
used when several deliver the same total amount.

Each outlet divides its delivery evenly among its tiles, assigning leftover
units in tile order. One unit adds one moisture point, up to 100. Water delivered
to saturated ground still comes out of the tank. After watering, the selected
ecology release advances the garden one day, including care plans, weather and
species dynamics.

## Save and revisit a design

`save_design(path, result)` writes a JSON report and `load_design(path)` reads and
validates one. Reports retain the original inputs, selected simulation release,
daily measurements and resulting world. Their input digest helps detect
accidental changes to saved data. Keep the full report to review or replay a
design later.

The command line accepts a JSON object containing the same arguments as
`definition`:

```sh
python -m mosslight.irrigation irrigation-problem.json irrigation-result.json
```

The resulting world is an ordinary garden save that can be used as the source
for other Mosslight workflows. See [Staged treatment studies](STUDIES.md) and
[Garden histories](HISTORY.md) for related ways to explore a garden's future.
