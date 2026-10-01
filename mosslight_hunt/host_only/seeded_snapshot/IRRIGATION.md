# Irrigation design

Mosslight can compare multi-day valve schedules before committing a garden to a
watering setup. A design combines an ordinary saved world, a directed pipe layout,
a finite tank supply, optional daily refills, and the valve configurations the
operator is willing to use. The report preserves the original design, daily pipe
flows, delivered doses, ecology measurements and the resulting garden. It can be
saved as JSON and replayed under its recorded simulation release.

Create a problem with `mosslight.irrigation.definition(world, layout, choices,
days, supply, refill=None, version="classic-1")`, then call `solve(problem)`.
`replay(problem, schedule)` independently evaluates any proposed sequence of
choice indices. `save_design(path, result)` and `load_design(path)` retain and
validate replayable reports. The CLI accepts the same definition arguments in a
JSON object:

```
python -m mosslight.irrigation irrigation-problem.json irrigation-result.json
```

The layout has a `source` junction name, a `pipes` list and an `outlets` mapping.
Each pipe has `from`, `to` and integer `capacity` fields. Pipes are directed, can
share junctions, and may have parallel or opposing connections. An outlet has an
integer `demand` and a nonempty list of `[x,y]` tile coordinates. Outlet tile sets
must be disjoint. Choices contain a unique `name` and an `open` list of outlet
names. An empty list closes every valve for that day.

```
{
  "source": "tank",
  "pipes": [
    {"from": "tank", "to": "north", "capacity": 20},
    {"from": "tank", "to": "south", "capacity": 20}
  ],
  "outlets": {
    "north": {"demand": 20, "tiles": [[0,0], [1,0]]},
    "south": {"demand": 20, "tiles": [[0,3], [1,3]]}
  }
}
```

At each simulated day, the configured refill is added to the remaining tank
supply. The selected outlets request their configured demands, and the layout
allocates the maximum feasible integral delivery under its pipe capacities and
available supply. Input order determines allocation when multiple maximum-flow
solutions exist. Each outlet divides its delivered units evenly among its tiles,
with leftover units assigned in tile order. One unit adds one moisture point,
clipped at 100; units applied to saturated ground are still consumed. The ordinary
retained ecology simulator then advances one day, including its usual care plans,
rules, weather and species dynamics.

The design objective is the largest final sum of cell vitality across the whole
garden. Among equally scoring plans, retain the largest remaining tank supply;
any plan tied on both is acceptable. `solve` returns a global optimum over all
sequences of the supplied choices. It owns its working copies and does not mutate
the source garden or caller's definition. The result's input digest identifies
the frozen definition; it is an accidental-corruption check, not authentication.

This is an exact finite design tool. Runtime and memory can grow exponentially
with the number of choices and days. Start with short design windows and a small
set of useful valve choices. No fixed latency guarantee is made. Saved reports retain the inputs and daily
measurements needed to review a design later.
Garden saves, history publications and study reports continue to use their
existing independent workflows; an irrigation result contains a normal resulting
world that can be used wherever a saved source garden is accepted.
