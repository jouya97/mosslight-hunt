# The garden workbench

The workbench combines tending, propagation, a field notebook and regular care.
Start with the studio controls or the [command recipes](COMMANDS.md). The live
`python3 -B -m mosslight guide` lists command arguments, species traits and recipes.

## Care for a bed

Water raises moisture, compost enriches soil, and planting introduces a young
plant. These basic tools are freely available. Ponds and stones cannot be planted.
Use rectangles or diamond, circular and square brushes to tend larger areas;
selections stop at garden edges, and radius zero selects one tile.

```json
{"op":"tend_many","args":{"tiles":[[0,0],[1,0]],"action":"water"}}
```

An area operation treats each selected tile once and succeeds as a whole. A
rejected operation leaves the garden and its resources available to try again.
Transplanting moves a living plant to empty, plantable ground, carrying its age
and stress with it at some cost to vitality. Soil stays at its location. Pruning
rejuvenates a living plant without moving it.

## Harvest and propagate

Mature plants supply fiber, nectar or spores. The species guide gives harvest
ages and yields; vigorous plants yield more. Harvesting takes vigor and starts a
new growth period before the next harvest. Seed collection likewise requires a
healthy developed plant. Stored seeds can be sown directly into empty ground or
raised on the propagation bench.

Craft compost, mulch and tonic from harvested resources. The guide lists recipe
costs and outputs. Crafted compost enriches ground, mulch protects moisture and
tonic restores a living plant's vigor. Crafting and material use require enough
inventory and room for the result. Resource balances never become negative.

The propagation bench holds seed batches and individual cuttings outside the
grid. A batch needs regular watering even after it is ready. Watering restores a
three-day supply. Hydrated days develop the batch and improve its vigor; dry days
halt development and weaken it. Moss needs three growing days, fern four, clover
two and glowcap five. A batch that dries out completely fails.

Plant ready seedlings into empty, plantable ground. Each starts with its nursery
vigor and uses four nutrient points from its new site. A batch remains available
until all its seedlings have been planted or it is discarded. Check the nursery
report for readiness and water advice without advancing time.

## Keep a field notebook

Give the garden a title and record tagged observations, with optional tile
locations. Search note text without regard to case, filter by tag, or select an
inclusive date range. Tags are treated consistently despite capitalization,
surrounding whitespace or repeated entries. Editing a note preserves its identity
and original observation date.

Specimens preserve measurements of a living plant at the time of collection.
They remain useful after the garden changes, and collecting one leaves the plant
in place. The [notebook export](PORTABILITY.md#archiving-the-notebook-and-artwork)
turns observations and specimens into a portable record.

Tasks are reminders with a due date and completion status. They can be entered
with past dates, marked complete, reopened or deleted. Due tasks include today's
reminders; overdue tasks are from earlier days. Lists place earlier due dates
first. Creating or completing a reminder does not perform garden care.

Use returned IDs to refer to entries; deleting an entry does not make its ID
available for a new object. Each notebook, planning or nursery collection holds
up to 500 entries. Notes support up to 2,000 characters and 12 tags.

## Arrange regular care

Beds give names to reusable tile selections and may overlap. Plans and rules
keep the locations selected when they were created, so later changes to a bed
do not redirect existing care.

A care plan begins on a future day and can repeat a finite number of times. For
example, a plan starting on day 5 with interval 3 and four runs is due on days 5,
8, 11 and 14. Scheduled care prepares the garden for that day's growth. Cancel a
pending plan to stop its remaining runs. Failed plans show their error for review;
other plans can still proceed.

Conditional rules respond to moisture, nutrients or vitality after the day's
growth. Choose a tile selection, a threshold and an action. “Below” and “above”
exclude equality. Rules respond to the day's growing conditions consistently,
even when several care actions are needed. Enabling a rule makes it available
for future days; it does not immediately tend the garden.

The daily history includes the results of care. Use [field reports and charts](FIELD_GUIDE.md)
to review a schedule before expanding it to more beds.
