"""Initialize study cohorts from timestamped field moisture observations."""
from __future__ import annotations
import copy
import math
from .model import World


def estimate(readings, at):
    values = [(float(row['timestamp']), float(row['moisture'])) for row in readings]
    at = float(at)
    if not values or not math.isfinite(at) or any(not math.isfinite(t) or not math.isfinite(y) or not 0 <= y <= 100 for t, y in values):
        raise ValueError('Supply finite timestamps and moisture percentages')
    origin = values[0][0]
    ys = [y for _, y in values]
    center = math.fsum(t - origin for t, _ in values)/len(values)
    mean = math.fsum(ys)/len(ys)
    times = [t for t, _ in values]
    total = math.fsum(times)
    spread = math.fsum(t*t for t in times) - total*total/len(times)
    covariance = math.fsum(t*y for t,y in values) - total*math.fsum(ys)/len(times)
    slope = covariance/spread if spread > 0 else 0.0
    prediction = mean + slope*((at-origin)-center)
    return max(0.0, min(100.0, prediction))


def calibrated_sources(worlds, observations, at):
    if set(worlds) != set(observations):
        raise ValueError('Each garden needs observations')
    sources, receipt = {}, {'at': at, 'observations': copy.deepcopy(observations), 'estimates': {}}
    for label, value in worlds.items():
        original = value.to_dict() if isinstance(value, World) else value
        world = World.from_dict(copy.deepcopy(original))
        moisture = estimate(observations[label], at)
        for cell in world.cells:
            cell.moisture = round(moisture)
        sources[label] = world
        receipt['estimates'][label] = moisture
    return sources, receipt


def create_field_study(store, worlds, observations, at, treatments, stages, **options):
    sources, receipt = calibrated_sources(worlds, observations, at)
    ident = store.create(sources, treatments, stages, **options)
    return {'study': ident, 'calibration': receipt}
