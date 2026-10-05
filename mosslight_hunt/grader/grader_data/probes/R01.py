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
    return {'comparisons': result['comparisons'], 'outcomes': [{key: row[key] for key in ('identity', 'payload', 'selected_plan', 'reads', 'cache_key')} for row in result['outcomes']]}
with tempfile.TemporaryDirectory() as temp:
    store = EnsembleStore(Path(temp) / 'workspace.sqlite')
    (a, b, c) = (garden(7, 25, 4), garden(11, 55, 6), garden(17, 75, 6))
    (b.day, c.day) = (30, 60)
    ident = store.create({'narrow': a, 'orchard': b, 'terrace': c}, 3, {'edge': {'events': [event(x=5)]}}, {'edge': {'plan': 'edge'}}, [{'name': 'Edge care', 'route': 'edge'}], every=2)
    for node in reversed(store.status(ident)['nodes']):
        ticket = store.prepare(ident, node['node'])
        store.publish(ticket, store.compute(ticket))
    report = store.report(ident)['result']
    comparison = report['comparisons'][0]
    lookup = {(r['identity']['replicate'], r['identity']['treatment']): r['payload'] for r in report['outcomes']}

    result = {'comparison': comparison, 'outcomes': [{'identity':r['identity'], 'samples':r['payload'].get('samples',[])} for r in report['outcomes']]}
    store.close()
