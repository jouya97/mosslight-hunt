# Growing a terrarium

A Mosslight garden develops one day at a time. Its seed, starting conditions and
care determine its future, so a saved garden is also a repeatable starting point
for an experiment. Begin in the studio or create one from the command line:

```sh
python3 -B -m mosslight new garden.json --seed 34 --width 16 --height 11
python3 -B -m mosslight grow garden.json --days 12
python3 -B -m mosslight report garden.json
```

Coordinates start at zero. Gardens can be 4–40 tiles wide and 4–30 tiles high.
Moisture, nutrients, shade, vitality, mulch and stress are whole percentages from
0 to 100; reports can average these measurements into fractional values.

## Seasons and water

The 48-day year begins with Dawn, followed by Highsummer, Ember and Hush. Each
season lasts 12 days. Day zero is the first day of Dawn. Highsummer is hotter and
drier; Hush slows most plants, while glowcaps remain suited to the season.
Weather is repeatable for a given seed and day. The almanac lets you plan around
coming rain without advancing the garden.

Water moves between neighboring ground, rain replenishes it and evaporation
removes it. Neighboring tiles share edges; diagonal contact does not count as
adjacency. A day's development represents the whole garden growing together.
Sand drains quickly, peat retains water, and ordinary soil lies between them.
Ponds stay at 100 moisture and stones at zero. Neither supports plants. A pond
also moistens adjoining ground.

Use structures to shape a habitat. Shade cloth shelters its own tile and adjoining
tiles; overlapping shelters can provide deeper shade. This affects growing
conditions without changing the ground's base shade measurement. Rain barrels
collect water on rainy days. Logs enrich their tiles, and bee houses encourage
visitors where clover can support them. Mulch slows evaporation and gradually
returns nutrients as it decomposes.

## Choosing plants

```sh
python3 -B -m mosslight guide
python3 -B -m mosslight recommend garden.json glowcap --limit 5
```

The guide lists each species' preferred moisture and shade, nutrient upkeep,
lifespan and harvest traits. Moss and ferns favor shaded damp ground, clover
prefers brighter clearings, and glowcaps thrive in deep wet shade. Compare those
traits with a tile's measurements or use planting recommendations to find a site.

Well-sited, well-fed plants build vitality. Poor conditions and depleted soil
weaken them; old or exhausted plants eventually return nutrients to the ground.
Bare ground slowly recovers one nutrient point a day. Plants under severe strain
can also return a small amount of nutrients. Stress records sustained low vigor:
vitality below 30 increases stress, while healthier plants recover from it.

Healthy plants may spread into nearby bare, plantable ground. New seedlings begin
young and must develop before spreading themselves. Growth, losses and seasonal
changes appear in the garden journal. The last 100 events and 240 daily census
records remain in the save.

## Tending and observing

Water and compost are freely available. Planting, clearing, changing terrain and
adding structures let you reshape a garden at any point. Use the [workbench](WORKBENCH.md)
for materials, propagation and regular care, and the [field station](FIELD_GUIDE.md)
to compare the effects over time.

Visitors are observations of the day's habitat. Healthy clover supports bees
outside Hush, glowcaps attract fireflies, and moist, rich soil or peat supports
worms. Visitor counts update when the garden advances; using a tool between days
does not create a new census.

Advance 1–365 days at a time. The save calendar supports days through 1,000,000;
a request beyond it leaves the garden at its previous date.
