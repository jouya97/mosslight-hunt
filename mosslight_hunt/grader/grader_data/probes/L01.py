_observations=[]
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
    return {'comparisons': result['comparisons'], 'outcomes': [{key: row[key] for key in ('identity', 'payload', 'selected_plan', 'reads', 'cache_key')} for row in result['outcomes']]}

def observe_visible(store, ident):
    try:
        report = store.report(ident)
    except ValueError:
        return
    _observations.append([report['revision'], [[row['identity'], row['selected_plan'], row['payload']['world']['cells'][0]['species']] for row in report['result']['outcomes']]])
for placement in ('before_prepare', 'after_prepare', 'after_compute', 'after_publish', 'after_reopen'):
    for (seed, label) in ((7, 'north bed'), (19, 'ridge')):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'workspace.sqlite'
            (store, editor) = (EnsembleStore(path), EnsembleStore(path))
            plans = {'routine': {'events': [event('compost')]}, 'dry care': {'events': [event('water')]}}
            ident = store.create({label: garden(seed)}, 2, plans, {'adaptive': {'plan': 'routine'}}, [{'name': 'Care', 'route': 'adaptive'}])
            finish(store, ident)
            store.edit(ident, {'route:adaptive': {'plan': 'routine', 'when': {'metric': 'moisture', 'below': 55, 'plan': 'dry care'}}})
            change = {'plan:dry care': {'events': [event('plant_moss')]}}
            if placement == 'before_prepare':
                editor.edit(ident, change)
            ticket = store.prepare(ident)
            if placement == 'after_prepare':
                editor.edit(ident, change)
            computed = store.compute(ticket)
            if placement in ('after_compute', 'after_reopen'):
                editor.edit(ident, change)
            if placement == 'after_reopen':
                store.close()
                store = EnsembleStore(path)
            store.publish(ticket, computed)
            observe_visible(store, ident)
            if placement == 'after_publish':
                editor.edit(ident, change)
                observe_visible(store, ident)
            finish(store, ident)
            observe_visible(store, ident)
            editor.close()
            store.close()
result=_observations
