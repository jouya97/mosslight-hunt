"""Seeded weather almanac and a 48-day garden calendar."""
from __future__ import annotations
from .validation import integer

RAINFALL = {"clear":0,"drizzle":8,"rain":18,"storm":29}


def calendar_day(day):
    from .engine import season
    integer(day,"Day")
    return {"day":day,"year":day//48+1,"season":season(day),"season_day":day%12+1,
            "year_day":day%48+1,"days_until_season":12-day%12,"days_until_year":48-day%48}


def weather_on(seed,day):
    import random
    if type(seed) is not int:
        raise ValueError("Seed must be an integer")
    integer(day,"Day")
    rng = random.Random(f"{seed}:weather:{day}")
    wetness = (0.46,0.20,0.31,0.37)[(day//12)%4]
    roll = rng.random()
    weather = "storm" if roll < wetness*.12 else "rain" if roll < wetness*.55 else "drizzle" if roll < wetness else "clear"
    return {**calendar_day(day),"weather":weather,"rainfall":RAINFALL[weather]}


def almanac(world,days=12,start=None):
    integer(days,"Almanac days",1,365)
    start = world.day+1 if start is None else integer(start,"Start day")
    if start+days-1 > 1_000_000:
        raise ValueError("Almanac extends beyond the garden calendar")
    entries = [weather_on(world.seed,day) for day in range(start,start+days)]
    totals = {name:sum(e["weather"]==name for e in entries) for name in RAINFALL}
    longest,current = 0,0
    for entry in entries:
        current = current+1 if entry["rainfall"] == 0 else 0
        longest = max(longest,current)
    return {"start":start,"end":start+days-1,"days":entries,"weather_days":totals,
            "total_rainfall":sum(e["rainfall"] for e in entries),"longest_dry_spell":longest}


def next_weather(world,kind,within=48):
    from .validation import choice
    choice(kind,RAINFALL,"weather")
    for entry in almanac(world,within)["days"]:
        if entry["weather"] == kind:
            return entry
    return None


def calendar(world,days=12):
    """Dated notebook tasks and future care plan occurrences, inclusive of today."""
    integer(days,"Calendar days",1,365)
    if world.day+days-1 > 1_000_000:
        raise ValueError("Calendar extends beyond save limit")
    result = []
    for day in range(world.day,world.day+days):
        plans = []
        for plan in world.workbench["plans"]:
            if plan["status"] != "pending":
                continue
            gap = day-plan["day"]
            occurs = gap == 0 or (gap > 0 and plan["repeat"] > 0 and gap%plan["repeat"] == 0 and gap//plan["repeat"] < plan["remaining"])
            if occurs:
                plans.append({"id":plan["id"],"name":plan["name"],"action":plan["action"]})
        result.append({**weather_on(world.seed,day),
                       "tasks":[dict(t) for t in world.workbench["tasks"] if t["due"] == day and not t["done"]],
                       "plans":plans})
    return result
