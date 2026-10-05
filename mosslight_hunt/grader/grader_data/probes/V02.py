_observations = []
import copy, json, tempfile
from pathlib import Path
from unittest.mock import patch
from mosslight.campaigns import CampaignStore
from mosslight.model import World, Cell
from mosslight.runtime import step_for

def garden():
    return World(7, 4, 4, cells=[Cell(68, 50, 50) for _ in range(16)])

def finish(store, ident):
    while store.work_once(ident):
        pass
    return store.result(ident)
with tempfile.TemporaryDirectory() as temp:
    store = CampaignStore(Path(temp) / 'workspace.sqlite')
    events = [{'offset': 2, 'command': {'op': 'note', 'args': {'content': 'Observed at checkpoint'}}}]
    parent = store.create(garden(), 3, [{'name': 'Observation', 'events': events}])
    finish(store, parent)
    child = store.fork(parent, 1, 2, days=1)
    finish(store, child)
    notes = store.checkpoint(child, 1, 1)['state']['world']['workbench']['notes']
    _observations.append([n['text'] for n in notes])
    store.close()
result = _observations
