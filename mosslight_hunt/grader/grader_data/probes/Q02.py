_observations = []
import copy, json, tempfile
from pathlib import Path
from mosslight.studies import StudyStore
from mosslight.model import World, Cell

def garden(seed=7):
    return World(seed, 4, 4, cells=[Cell(40, 50, 50) for _ in range(16)])

def note(content):
    return {'offset': 0, 'command': {'op': 'note', 'args': {'content': content}}}

def treatments():
    return [{'name': 'Moist shelter', 'events': [note('Moist shelter')]}, {'name': 'Fern edge', 'events': [note('Fern edge')]}]

def finish(store, ident):
    for _ in range(1000):
        if store.work_once(ident, offsets=4) is None:
            return store.status(ident)
    raise AssertionError('study did not quiesce')
with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / 'workspace.sqlite'
    store = StudyStore(path)
    ident = store.create({'bed': garden()}, treatments(), [{'until': 1, 'keep': 2}, {'until': 3, 'keep': 1}], metric='moisture')
    _observations.append(finish(store, ident)['status'])
    first = store.report(ident, 0)
    store.close()
    store = StudyStore(path)
    for name in ('control', 'Moist shelter', 'Fern edge'):
        original = store.checkpoint(ident, 0, 'bed', name)
        descendant = store.checkpoint(ident, 1, 'bed', name)
        expected = {key: original[key] for key in ('study', 'stage', 'replicate', 'treatment', 'digest')}
        _observations.append({key: descendant['parent'][key] for key in ('stage', 'replicate', 'treatment')})
        before = original['state']['world']['workbench']['notes']
        after = descendant['state']['world']['workbench']['notes']
        _observations.append([before, after])
    _observations.append(store.report(ident, 0)['decision'])
    store.close()
result = _observations
