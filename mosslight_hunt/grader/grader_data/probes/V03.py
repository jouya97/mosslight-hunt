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
    parent = store.create(garden(), 4, [{'name': 'Observe', 'events': []}])
    finish(store, parent)
    child = store.fork(parent, 1, 2, days=1)
    store.compact(parent, keep_every=4)
    chain = store.provenance(child)
    _observations.append(len(chain))
    store.close()
result = _observations
