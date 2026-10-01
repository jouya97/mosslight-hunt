"""Initialize study cohorts from timestamped field moisture observations."""
from __future__ import annotations
import copy
import math
from .model import World


def estimate(readings, at):
    """Least-squares local trend, evaluated at an absolute observation time."""
    values = [(float(row['timestamp']), float(row['moisture'])) for row in readings]
    at = float(at)
    if not values or not math.isfinite(at) or any(not math.isfinite(t) or not math.isfinite(y) or not 0 <= y <= 100 for t, y in values):
        raise ValueError('Supply finite timestamps and moisture percentages')
    origin = values[0][0]
    xs = [t - origin for t, _ in values]
    ys = [y for _, y in values]
    center = math.fsum(xs)/len(xs)
    mean = math.fsum(ys)/len(ys)
    spread = math.fsum((x-center)**2 for x in xs)
    slope = math.fsum((x-center)*(y-mean) for x,y in zip(xs,ys))/spread if spread else 0.0
    prediction = mean + slope*((at-origin)-center)
    return max(0.0, min(100.0, prediction))


def calibrated_sources(worlds, observations, at):
    """Return independent simulation inputs plus original calibration evidence."""
    if set(worlds) != set(observations):
        raise ValueError('Each garden needs observations')
    sources, receipt = {}, {'at': at, 'observations': copy.deepcopy(observations), 'estimates': {}}
    for label, value in worlds.items():
        original = value.to_dict() if isinstance(value, World) else value
        world = World.from_dict(copy.deepcopy(original))
        moisture = estimate(observations[label], at)
        # The simulator stores whole percentage points; record the estimate too.
        for cell in world.cells:
            cell.moisture = round(moisture)
        sources[label] = world
        receipt['estimates'][label] = moisture
    return sources, receipt


def create_field_study(store, worlds, observations, at, treatments, stages, **options):
    """Create an ordinary staged study and return replayable field provenance."""
    sources, receipt = calibrated_sources(worlds, observations, at)
    ident = store.create(sources, treatments, stages, **options)
    return {'study': ident, 'calibration': receipt}
