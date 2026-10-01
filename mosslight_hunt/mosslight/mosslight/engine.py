"""The terrarium ecology simulator."""
from __future__ import annotations

import random
from .model import ACTIONS, Cell, SPECIES, World

SEASONS = ("Dawn", "Highsummer", "Ember", "Hush")
PREFERENCES = {
    "moss": (65, 67, 2),
    "fern": (58, 55, 3),
    "clover": (45, 20, 2),
    "glowcap": (72, 82, 3),
}


def clamp(value: int) -> int:
    return max(0, min(100, value))


def season(day: int) -> str:
    return SEASONS[(day // 12 + 1) % 4]


def phase(day: int) -> int:
    return day % 47


def neighbors(world: World, x: int, y: int) -> list[tuple[int, int]]:
    # Orthogonal adjacency gives the garden readable migration patterns.
    return [(a, b) for a, b in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            if 0 <= a < world.width and 0 <= b < world.height]


def log(world: World, message: str) -> None:
    world.journal.append({"day": world.day, "text": message})
    world.journal = world.journal[-100:]


def create(seed: int = 7, width: int = 16, height: int = 11) -> World:
    if type(seed) is not int or type(width) is not int or type(height) is not int:
        raise ValueError("Seed and dimensions must be integers")
    if not (4 <= width <= 40 and 4 <= height <= 30):
        raise ValueError("Terrarium must be between 4×4 and 40×30")
    rng = random.Random(seed)
    cells = []
    for y in range(height):
        for x in range(width):
            # A broad canopy gradient, with irregular pockets of light.
            shade = clamp(48 + int(27 * (y / max(1, height - 1))) - int(21 * (x / max(1, width - 1))) + rng.randrange(-18, 19))
            moisture = clamp(43 + int(19 * (y / max(1, height - 1))) + rng.randrange(-15, 16))
            nutrients = rng.randrange(38, 72)
            species = None
            roll = rng.random()
            if roll < .18:
                species = "moss"
            elif roll < .245:
                species = "fern"
            elif roll < .31:
                species = "clover"
            elif roll < .335 and shade > 55:
                species = "glowcap"
            cells.append(Cell(moisture, nutrients, shade, species, rng.randrange(2, 8) if species else 0, rng.randrange(40, 76) if species else 0))
    world = World(seed, width, height, cells=cells)
    log(world, "A little world wakes beneath the glass.")
    return world


def _weather(world: World) -> str:
    from .weather import weather_on
    return weather_on(world.seed, world.day)["weather"]


def step(world: World, days: int = 1) -> World:
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError("Days must be an integer from 1 to 365")
    if world.day + days > 1_000_000:
        raise ValueError("Garden day exceeds save limit")
    for _ in range(days):
        _one_day(world)
    return world


def _one_day(world: World) -> None:
    world.day += 1
    world.revision += 1
    from .habitat import water_balance, effective_shade, after_day
    from .planning import run_plans, run_rules
    run_plans(world)
    world.weather = _weather(world)
    weather_gain = {"clear": 0, "drizzle": 8, "rain": 18, "storm": 29}[world.weather]
    season_name = season(world.day)
    if world.day % 12 == 0:
        log(world, f"{season_name} settles over the glass.")
    if world.weather == "storm":
        log(world, "Rain drums on the roof; the soil drinks deeply.")

    old = [Cell(**c.to_dict()) for c in world.cells]
    births: list[tuple[int, str]] = []
    losses = 0
    for y in range(world.height):
        for x in range(world.width):
            i = world.index(x, y)
            before, cell = old[i], world.cells[i]
            rng = random.Random(f"{world.seed}:{world.day}:{i}")
            adjacent = [old[world.index(a, b)] for a, b in neighbors(world, x, y)]
            neighbor_mean = sum(world.cells[world.index(a, b)].moisture for a, b in neighbors(world, x, y)) // len(adjacent)
            shade = effective_shade(world, i)
            evaporation = 3 + (3 if season_name == "Highsummer" else 0) + max(0, 50 - shade) // 22
            cell.moisture = water_balance(world, i, before.moisture, neighbor_mean, weather_gain, evaporation)
            cell.nutrients = clamp(before.nutrients)
            if before.species:
                desired_moisture, desired_shade, upkeep = PREFERENCES[before.species]
                comfort = 8 - abs(cell.moisture - desired_moisture) // 9 - abs(cell.shade - desired_shade) // 13
                if season_name == "Hush":
                    comfort -= 2
                if cell.nutrients < upkeep:
                    comfort -= 7
                cell.vitality = clamp(before.vitality + comfort - 3)
                cell.nutrients = clamp(before.nutrients - upkeep + (2 if before.vitality < 25 else 0))
                cell.age = before.age + 1
                if cell.vitality == 0 or cell.age > 105:
                    cell.species, cell.age, cell.vitality = None, 0, 0
                    cell.nutrients = clamp(cell.nutrients + 15)
                    losses += 1
            elif adjacent and cell.nutrients >= 15 and world.workbench["tiles"][i]["terrain"] not in ("pond", "stone"):
                candidates = [n.species for n in adjacent if n.species and n.vitality >= 55]
                if candidates and rng.random() < .075 + .025 * len(candidates):
                    species = rng.choice(candidates)
                    preferred_moisture, preferred_shade, _ = PREFERENCES[species]
                    if abs(cell.moisture - preferred_moisture) < 38 and abs(shade - preferred_shade) < 45:
                        births.append((i, species))
    for i, species in births:
        cell = world.cells[i]
        cell.species, cell.age, cell.vitality = species, 0, 36
        cell.nutrients = clamp(cell.nutrients - 8)
    if births:
        count = len(births)
        log(world, f"{count} new {('sprout' if count == 1 else 'sprouts')} found a foothold.")
    if losses:
        log(world, f"{losses} {('plant returns' if losses == 1 else 'plants return')} to the soil.")
    if world.day % 7 == 0:
        glowing = sum(c.species == "glowcap" and c.vitality > 40 for c in world.cells)
        if glowing:
            log(world, f"At dusk, {glowing} glowcap {('shines' if glowing == 1 else 'shine')} like tiny lanterns.")

    run_rules(world)
    from .nursery import advance_nursery
    advance_nursery(world)
    after_day(world, len(births), losses)


def act(world: World, x: int, y: int, action: str) -> World:
    if action not in ACTIONS:
        raise ValueError("Unknown action")
    cell = world.cell(x, y)
    tile = world.workbench["tiles"][world.index(x, y)]
    if action.startswith("plant_") and tile["terrain"] in ("pond", "stone"):
        raise ValueError("This terrain cannot support plants")
    if action == "water":
        cell.moisture = clamp(cell.moisture + 32)
        message = f"A slow pour reaches tile {x + 1}, {y + 1}."
    elif action == "compost":
        cell.nutrients = clamp(cell.nutrients + 32)
        message = f"Rich compost is folded into tile {x + 1}, {y + 1}."
    elif action == "clear":
        cell.species, cell.age, cell.vitality = None, 0, 0
        cell.nutrients = clamp(cell.nutrients + 7)
        message = f"Tile {x + 1}, {y + 1} is opened to possibility."
    else:
        species = action.removeprefix("plant_")
        cell.species, cell.age, cell.vitality = species, 0, 52
        cell.nutrients = clamp(cell.nutrients - 8)
        message = f"A {species} begins on tile {x + 1}, {y + 1}."
    world.revision += 1
    log(world, message)
    return world


def summary(world: World) -> dict:
    counts = {name: sum(c.species == name for c in world.cells) for name in SPECIES}
    size = len(world.cells)
    return {
        "day": world.day, "season": season(world.day), "weather": world.weather,
        "population": counts, "occupied": sum(counts.values()),
        "average_moisture": round(sum(c.moisture for c in world.cells) / size),
        "average_nutrients": round(sum(c.nutrients for c in world.cells) / size),
    }
