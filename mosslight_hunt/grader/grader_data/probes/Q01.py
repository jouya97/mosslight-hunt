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
for (first, reopen) in (('north', False), ('south', False), ('north', True)):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'workspace.sqlite'
        store = StudyStore(path, clock=lambda : 100)
        ident = store.create({'north': garden(7), 'south': garden(11)}, treatments(), [{'until': 2, 'keep': 1}], metric='moisture')
        claims = []
        while (claim := store.claim(ident, lease_seconds=30)) is not None:
            claims.append(claim)
        _observations.append(len(claims))
        for claim in reversed(claims):
            if claim['replicate'] == first:
                _observations.append(store.publish(claim, store.compute(claim, offsets=3)))
        if reopen:
            store.close()
            store = StudyStore(path, clock=lambda : 100)
        preview = store.preview(ident)
        _observations.append([preview['common'], preview['terminal']])
        _observations.append(store.status(ident)['status'])
        try:
            store.report(ident, 0)
        except ValueError:
            pass
        else:
            raise AssertionError('partial cohort acquired an immutable stage report')
        for claim in claims:
            if claim['replicate'] != first:
                _observations.append(store.publish(claim, store.compute(claim, offsets=3)))
        report = store.report(ident, 0)
        _observations.append([report['decision']['terminal'], report['decision']['pending']])
        _observations.append(report['decision']['common'])
        _observations.append([row['status'] for row in report['outcomes']])
        store.close()
result = _observations
