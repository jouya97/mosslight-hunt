# Behavior reference

These rules describe the application, including boundary conditions. Percentages are integer 0–100 unless explicitly reported as averages. API/CLI coordinates are zero based. Examples below assume ordinary soil and no extra structures unless stated.

## Core ecology

1. Creation accepts integer seeds, widths 4–40 and heights 4–30. Booleans are not integers for application input.
2. Cell indexing is row major: `y * width + x`. Coordinates must be integers inside the garden.
3. A year is 48 days, split into Dawn, Highsummer, Ember and Hush, each lasting 12 days. Day 0 is Dawn day 1; day 12 is Highsummer day 1.
4. Weather depends only on seed and day. Rainfall is 0 for clear, 8 for drizzle, 18 for rain and 29 for storm.
5. Daily weather wetness probabilities are .46, .20, .31 and .37 by season. The storm threshold is wetness × .12; rain is wetness × .55; drizzle is wetness; remaining days are clear.
6. Daily moisture first moves by `floor((orthogonal_neighbor_mean - old_moisture) / 4)`. Neighbor mean uses integer floor and the old grid.
7. Base evaporation is 3, plus 3 in Highsummer, plus `max(0, 50-effective_shade)//22`.
8. Empty tiles gain one nutrient daily before habitat aftercare. Plants consume species upkeep: moss/clover 2, fern/glowcap 3.
9. Preferred moisture/shade is moss 65/67, fern 58/55, clover 45/20 and glowcap 72/82.
10. Comfort is `8 - abs(moisture-preferred)//9 - abs(effective_shade-preferred)//13`. Hush subtracts 2 for all species except glowcap; insufficient nutrients subtracts 7.
11. Vitality changes by comfort minus 3. A plant with resulting vitality below 25 recovers 2 nutrients after upkeep.
12. Every existing plant ages once daily. Zero vitality or age greater than 105 kills ordinary plants; glowcap's limit is 75. Death clears species, age and vitality, and returns 15 nutrients.
13. A bare plantable tile with at least 15 nutrients can receive neighboring seeds. Parents must have old vitality at least 55. Chance is .075 plus .025 per eligible neighbor.
14. A candidate species must be less than 38 moisture points and 45 effective shade points from its preferences. Birth costs 8 nutrients and starts age 0, vitality 36.
15. Births are applied after the grid is processed. They cannot create propagation chains on that day.
16. `step` accepts 1–365 days and rejects a result beyond day 1,000,000 before changing the garden.
17. Basic water adds 32 moisture; basic compost adds 32 nutrients; clear removes plant fields and adds 7 nutrients. These tools are free and quantities clamp to 0–100.
18. Basic planting replaces the current species, costs 8 nutrients, and starts age 0, vitality 52. Pond and stone reject planting.
19. Season changes, storms, births, deaths and weekly healthy glowcaps create journal events. The newest 100 events are retained.

## Habitat

20. Soil has neutral terrain modifiers. Sand increases evaporation by 3 and reduces nonzero rainfall by 2. Peat reduces evaporation by 1 and increases nonzero rainfall by 3.
21. Daily evaporation cannot become negative. Rain bonuses do not apply on clear days.
22. A pond's daily moisture is exactly 100; a stone's is exactly 0. Changing to either immediately sets that moisture and clears plants, stress and mulch.
23. Each orthogonally adjacent pond adds 2 moisture to plantable ground. Diagonal ponds do not contribute.
24. Every 20 mulch points reduce evaporation by one. Mulch decays by one each day; a tile that had mulch at the start of aftercare gains one nutrient on days divisible by 3.
25. Shade cloth adds 15 effective shade on its tile and four orthogonal neighbors. Multiple cloths add together and effective shade caps at 100. Base shade is preserved.
26. A rain barrel adds 6 moisture on any day with rainfall, on its own tile only.
27. A log returns 2 nutrients on its tile every day during aftercare.
28. Bee houses affect the bee census; they do not consume resources or modify plant vitality.
29. Plant stress rises by 5 when final vitality is below 30, otherwise falls by 3. It is bounded 0–100. Empty tiles have zero stress after a day.
30. Outside Hush, bees equal `healthy_clover//3 + min(bee_houses, healthy_clover)`. Healthy means vitality at least 50. Hush has zero bees.
31. Fireflies equal the number of glowcaps with vitality at least 40 divided by two, rounded down.
32. Worms equal the count of soil/peat cells with moisture at least 45 and nutrients at least 40 divided by four, rounded down.
33. Visitors are recomputed daily. Tools do not immediately recompute them; reports show the last census.

## Garden tools and materials

34. Rectangle selection includes both corners and accepts corners in either order; output follows row order.
35. Diamond brushes use Manhattan distance, circle brushes use squared Euclidean distance, and square brushes use the bounding square. All are clipped at garden edges; radius zero selects one tile.
36. Batch tending deduplicates coordinates, validates the entire batch, commits once, and rolls back all earlier tiles on any failure.
37. Transplant requires a living source and a different empty, plantable destination. Age is retained, vitality loses 10 with minimum 1, and soil measurements stay at their locations.
38. Transplant moves the source's stress to the destination and clears source stress. The source becomes an empty plant record.
39. Pruning requires a plant; it removes up to five days of age and adds eight vitality, capped at 100.
40. Harvest requires vitality at least 40 and species maturity: moss 8 days, fern 12, clover 6, glowcap 10.
41. Moss yields 2 fiber, fern 3 fiber, clover 2 nectar, glowcap 2 spores. Vitality at least 80 adds one unit.
42. Harvest resets age to zero and reduces vitality by 15 with minimum 1. Repeated immediate harvesting is rejected.
43. Seed collection requires age at least 5 and vitality at least 50. It stores one species seed, resets age and subtracts 5 vitality.
44. Sowing a stored seed requires empty, plantable ground and one matching seed. It uses ordinary planting values and consumes the seed only after successful planting.
45. Crafting compost consumes 3 fiber and produces 2 compost. Mulch consumes 2 fiber and produces 3 mulch. Tonic consumes 2 nectar and 1 spore and produces 1 tonic.
46. Craft amount is 1–1,000 whole batches. All inputs and capacity are checked before any resource is changed. Inventory values cannot exceed 1,000,000.
47. Applying one crafted compost adds 40 nutrients. Applying one mulch adds 30 mulch. Both require plantable ground.
48. Applying one tonic requires a living plant, adds 25 vitality and removes up to 20 stress. All applications consume one matching material and clamp percentages.
49. Failed harvests, seed collection, sowing and material use do not consume resources.

## Propagation bench

50. Seed batches consume 1–20 matching stored seeds and reserve no grid tiles. A cutting requires source age 5 and vitality 60 and costs 12 source vitality.
51. Each new batch starts age 0, hydration 3, vitality 60 and status growing. A cutting contains one plant.
52. Watering a growing or ready batch restores hydration to 3. Closed or failed batches cannot be watered.
53. A hydrated day consumes one hydration, adds one age and adds three vitality. A dry day adds no age and removes 20 vitality.
54. Nursery maturity is moss 3, fern 4, clover 2 and glowcap 5 hydrated days. A mature living batch becomes ready.
55. Ready batches still need water. At zero vitality any living batch fails and stops advancing.
56. Planting out requires a ready batch, positive count and empty plantable ground. The new plant has age zero, the batch's current vitality and a 4-nutrient planting cost.
57. Each planting consumes one batch member. The final member changes status to planted. Earlier plantings leave the rest ready.
58. Discarding an open/failed batch sets count zero and status discarded. Discarded/planted batches cannot be discarded again.
59. Nursery reports return days to maturity and a water-needed flag without changing a batch.

## Notebook

60. Notes contain 1–2,000 characters after the nonblank check, with at most 12 tags. Text is trimmed at creation/edit.
61. Tags are trimmed, case folded, deduplicated and alphabetically sorted; each is 1–32 characters. Search uses case-insensitive text substring and an optional exact normalized tag.
62. Notes can refer to one valid tile or no location. Editing preserves the original observation day and ID.
63. Date search includes both endpoints; end cannot precede start. Search results are independent copies.
64. Specimens require a living plant and record all six cell fields, coordinates, label and day. Recording does not remove or alter the plant; later garden changes do not alter specimens.
65. Tasks store text, creation day, due day and completion state. Due days can be in the past; they are reminders, not automatic commands.
66. Open tasks exclude completed tasks. Due means due day ≤ current day; overdue means due day < current day. Lists sort by due day then ID.
67. Completion can be toggled back to open. Deleted entries are removed and their IDs are never reused.
68. Garden titles accept 1–100 characters and trim surrounding spaces.
69. Notes, tasks, specimens, beds, plans, rules and nursery batches share monotonically increasing integer IDs and each collection holds at most 500 entries.

## Plans and rules

70. Bed names are unique without regard to case. A bed stores at least one unique valid coordinate. Beds may overlap.
71. Care plans copy their coordinate list and do not reference a mutable bed. First day must be later than the current day.
72. Plans accept 1–1,000 runs and repeat intervals 0–365. More than one run requires a nonzero interval. The last occurrence must fit the calendar limit.
73. Due pending plans execute by ascending ID before weather/ecology. A late imported plan executes when next stepped rather than disappearing.
74. One successful occurrence decreases remaining runs by one. Repeating plans move their due day forward by the repeat interval; the last run becomes done.
75. A failed occurrence changes status to failed, records the error, and does not retry. Its tile edits are atomic. Other due plans still run.
76. Only pending plans can be cancelled. Cancellation leaves the plan visible and prevents future execution.
77. Rules compare moisture, nutrients or vitality with a threshold 0–100 using strict `below` or `above`; equality never matches.
78. All rule conditions use the same post-ecology snapshot. Multiple matching rules can therefore act on the same cell even if the first action would change a later condition.
79. Rule actions execute in rule ID order and stored tile order. Unsuitable planting locations are skipped and a journal event records each affected rule.
80. Disabled rules do not evaluate. Enabling, disabling and deleting do not perform their care action immediately.
81. Daily history is recorded after rules, nursery and habitat aftercare; it retains the last 240 day records.

## Field measurements

82. Coverage is occupied tiles divided by selected tiles ×100. Population counts are always provided for all four species, including zeros.
83. Moisture, nutrients and base shade averages include empty ground. Average vitality includes living plants only, with zero for an empty selection of life.
84. Richness counts present species. Diversity is natural-log Shannon entropy, rounded to four decimal places. Equal counts of two species give .6931.
85. Endangered census counts living plants with vitality below 25; oldest is the maximum living age, or zero when empty.
86. Suitability is `max(0,100-|moisture-preferred|-|effective_shade-preferred|-2*max(0,20-nutrients))`. Unplantable terrain scores zero.
87. Habitat advice identifies moisture/shade gaps greater than 20 and nutrients below 20. Recommendations omit unplantable cells and, by default, occupied cells.
88. Recommendation ties sort by y then x. Limit is 1–1,200.
89. Plant patches use four-neighbor connectivity. With no species filter, different neighboring species join a patch. Diagonals do not join.
90. Patch perimeter counts exposed unit cell edges, including outside the garden. A pair of adjacent cells has perimeter 6. Patch output sorts largest first, then topmost/leftmost tile.
91. Transects use the integer Bresenham line algorithm, include both endpoints and retain travel order. A point transect contains one sample.
92. Alerts include vitality below 25, moisture below 20, nutrients below species upkeep and stress at least 50. Empty ground does not trigger plant alerts.
93. Comparisons require equal dimensions and report cell/terrain changes, population differences and coverage difference. They can compare different seeds or days.
94. Forecasts include the initial sample, each chosen interval and the final day even when it is not an interval multiple. Days and interval are 1–365. The original world is unchanged.

## Calendar and experiments

95. Almanacs default to tomorrow, cover 1–365 days, total rainfall and weather counts, and report the longest consecutive clear stretch within that interval.
96. Calendar views include today. They attach open tasks on their exact due day and expand the remaining finite occurrences of pending plans.
97. `next_weather` returns the first matching future day in its search window, or null when no day matches.
98. Experiments accept 1–8 uniquely named treatments, reserve the name control, and run 1–120 days on independent copies of the same save.
99. Each treatment holds at most 100 ordered events with offsets 0–experiment days. Offset zero happens before the initial sample; positive offsets happen before the corresponding daily step. Same-offset events preserve input order.
100. Experiment events may use garden commands except grow. The experiment owns time advancement. Invalid treatment execution cannot mutate the source garden.
101. Experiment results contain control and treatment samples, final censuses and final differences against control. Sampling always includes initial and final days.
102. Experiment ranking accepts coverage, richness, diversity or mean vitality, sorts descending and preserves branch order for ties.

## Interchange and artwork

103. Survey CSV has the exact header `x,y,species,age,vitality,moisture,nutrients,shade,terrain,mulch,structure,stress`, one row per tile, and empty species fields for bare ground.
104. CSV import requires every coordinate exactly once, all expected columns and valid model values. A failed row leaves the entire garden unchanged. Notebook and planning state survive the tile replacement.
105. Blueprints contain local coordinates, dimensions, terrain, structure and species. They deliberately omit soil measurements, age, vitality, mulch and stress.
106. Blueprint rectangles normalize corner order. Rotations are 0–3 clockwise quarter turns; mirroring reflects horizontally before rotation. Output tiles sort in row order.
107. Blueprint dimensions can reach 40 in either direction after rotation, but placement must fit the target garden's actual dimensions.
108. Placement requires explicit overwrite when any target tile contains a plant. All collisions and bounds are checked on a copy. Placement plants at ordinary age/vitality and commits once.
109. Markdown export includes authored note text, observation dates/locations/tags, task checkboxes in due order and specimen labels. It ends with a newline.
110. Replay applies at most 1,000 ordered commands to an independent copy. Failure prevents publication of the whole script. Successful commands preserve normal revision semantics.
111. Art SVG includes exactly one tile group per grid cell. Interactive exports give each group keyboard focus and a title; plain CLI artwork has no interactive tabindex.
112. Percentage maps share fixed endpoint colors: zero `#dab76d`, 100 `#369294`. Intermediate channels interpolate with rounding. Terrain maps use categorical colors.
113. Shade maps show effective shade; census averages report base shade. Titles are XML escaped.
114. History charts use actual day spacing, percentage axes 0–100, and tile-count axes 0–grid size. Empty history displays guidance; a single observation renders as a point.

## Application transactions and persistence

115. Saves accept versions 1 and 2. Unsupported versions, invalid grid sizes, invalid species, inconsistent empty plants, invalid collection IDs and invalid coordinates are rejected.
116. A version 1 migration adds neutral workbench defaults. Missing optional workbench fields in version 2 also receive defaults. Unknown workbench fields are rejected.
117. Save/load and `to_dict` produce independent nested state; callers cannot mutate a world through a returned save dictionary.
118. A command accepts only `op` and `args`, validates its complete result, and publishes one revision regardless of internal work. A failed command leaves all original state intact.
119. CLI mutation commands save only after success. Forecast output must differ from its input path. Errors print to stderr and return exit code 2.
120. HTTP mutations serialize, optionally check the current integer revision, and persist before publishing. Stale revisions return 409. Persistence failure leaves memory and history unchanged.
121. Undo/redo restore snapshots with a new revision. A new edit after undo clears the redo branch. The server keeps 30 prior edits, and restart clears this session-only history.
122. HTTP read operations, forecasts, almanacs and experiments neither save nor create undo entries. Imports with a supplied revision are checked like other edits; the legacy unconditional import preserves the saved revision.
123. The browser escapes authored content through DOM text nodes and sends revisions on normal mutations and imports. JSON saves include all portable state; browser SVG and text downloads use local Blob objects.
