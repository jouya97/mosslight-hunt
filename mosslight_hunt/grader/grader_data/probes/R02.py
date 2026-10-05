_observations = []
import copy, json, tempfile
from pathlib import Path
from mosslight.ensembles import EnsembleStore
from mosslight.model import World, Cell
from mosslight.analysis import census
from mosslight.runtime import execute_for, step_for
from mosslight.ensemble_compute import digest

def garden(seed=7, moisture=40, width=4):
    return World(seed, width, 4, cells=[Cell(moisture, 50, 50) for _ in range(width * 4)])

def event(action='water', x=0, offset=0):
    return {'offset': offset, 'command': {'op': 'tend', 'args': {'x': x, 'y': 0, 'action': action}}}

def finish(store, ident):
    for _ in range(1000):
        if store.work_once(ident) is None:
            return store.report(ident)
    raise AssertionError('ensemble did not quiesce')

def numerical(result):
    return {'comparisons': result['comparisons'], 'outcomes': [{'identity': r['identity'], 'selected_plan': r['selected_plan'], 'cells': [[c['moisture'], c['nutrients'], c['species'], c['vitality']] for c in r['payload']['world']['cells']], 'samples': [[s['offset'], s['averages']] for s in r['payload']['samples']]} for r in result['outcomes']]}
with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / 'workspace.sqlite'
    store = EnsembleStore(path)
    ident = store.create({'bed': garden()}, 2, {'care': {'events': [event('water')]}}, {'care': {'plan': 'care'}}, [{'name': 'Care', 'route': 'care'}])
    original = finish(store, ident)
    store.edit(ident, {'plan:care': {'events': [event('plant_moss')]}})
    current = finish(store, ident)
    _observations.append([[r['identity'], r['payload']['world']['cells'][0]] for r in current['result']['outcomes']])
    store.close()
    store = EnsembleStore(path)
    archived = store.report(ident, 0)
    _observations.append([[r['identity'], r['payload']['world']['cells'][0]] for r in archived['result']['outcomes']])
    _observations.append(archived['revision'])
    store.close()
result = {'original': numerical(original['result']), 'archived': numerical(archived['result']), 'current': numerical(current['result']), 'revision': archived['revision']}
