# Measuring and exploring a garden

The field station brings together observations of the current garden and
repeatable explorations of its future. Reports, surveys, almanacs, forecasts and
experiments leave the source garden available for further work.

## Read the landscape

```sh
python3 -B -m mosslight report garden.json
python3 -B -m mosslight recommend garden.json glowcap --limit 5
```

The census reports population, coverage, soil conditions and plant vitality.
Coverage is the percentage of selected ground occupied by plants. Soil averages
include bare ground; vitality averages describe living plants. An empty selection
has no living vitality. Richness counts present species, while diversity uses
Shannon entropy with natural logarithms to reflect the balance of their populations.
The ordinary shade average measures the ground's base shade.

Reports also identify plants that need attention, such as those short of water,
nutrients or vigor. Planting advice accounts for species preferences, soil
resources and shelter from structures. Recommendations rank suitable plantable
locations and normally omit occupied ground. The [growing guide](GROWING.md)
introduces the species and their habitats.

Patch surveys show connected areas of plants. Cells connect along shared edges;
a diagonal touch does not join them. A species filter narrows the survey, and
perimeter measures the exposed edges of each patch. A transect instead follows
a straight line through tile centers from one selected endpoint to the other,
including both ends and preserving the chosen direction.

From Python, use `analysis.patches` and `analysis.transect`. The studio API also
accepts `/api/transect?x1=0&y1=0&x2=3&y2=3` for a diagonal survey.

## Plan around weather

```sh
python3 -B -m mosslight almanac garden.json --days 12
python3 -B -m mosslight almanac garden.json --calendar
```

The almanac starts tomorrow by default and covers up to 365 days. It summarizes
rainfall, weather types and consecutive dry days within that period. The calendar
includes today and shows dated reminders and remaining care-plan occurrences.
For scripts, `weather.next_weather` finds a matching future day within a chosen
window, or returns null when there is none.

## Explore a future

```sh
python3 -B -m mosslight forecast garden.json --days 10 --every 3 -o future.json
python3 -B -m mosslight compare garden.json future.json
```

A forecast follows the same ecology as ordinary growth, recording the starting
garden, regular samples and the final day. This example samples elapsed days 0,
3, 6, 9 and 10. Duration and sampling interval each accept 1–365 days. Save the
future to a different path to keep the starting garden.

Compare gardens of equal dimensions to review cell and terrain changes,
population differences and changes in coverage. Gardens can have different seeds
or dates; choose comparisons that answer a useful question about your planting.

## Compare treatments

An experiment compares a control with up to eight named treatments, all beginning
from the same save. It can run for up to 120 days. Treatments contain ordered
garden commands at offsets within that period; the experiment handles time, so
interventions cannot use `grow`.

```sh
python3 -B -m mosslight experiment garden.json examples/treatments.json --days 12 --every 3
```

Offset zero affects the initial sample. Later offsets apply care before the
corresponding day grows. Commands at the same offset follow their authored order.
See [treatment file examples](COMMANDS.md#controlled-experiment-files) to compare
shelter and extra watering.

Results include each branch's timeline, final census and differences from
control. Initial and final observations are always included. Rank branches by
coverage, richness, diversity or mean vitality using `experiments.rank_experiment`.
An experiment leaves the source unchanged even if a treatment cannot be completed.
For work across sessions, see [campaigns](CAMPAIGNS.md), [ensembles](ENSEMBLES.md)
and [staged studies](STUDIES.md).

## Maps, illustrations and history prints

SVG artwork represents every tile and preserves authored titles as text.
Interactive maps support keyboard navigation. Measurement maps share a fixed
0–100 scale from sand (`#dab76d`) to teal (`#369294`), so colors can be compared
between gardens and days. Shade maps show the shelter plants experience,
including structures. Terrain maps use distinct categorical colors.

History charts place observations at their actual dates. Percentage axes span
0–100 and population axes span the garden's tile count. A lone observation remains
visible as a point, while an empty history offers guidance to begin growing.
Artwork and charts are standalone SVGs suitable for saving or sharing.
