_observations = []
import copy, json, tempfile
from pathlib import Path
from unittest.mock import patch
from mosslight.campaigns import CampaignStore
import mosslight.campaigns as campaigns
_releases=[]
_step=campaigns.step_for
def observed_step(version,world,*args):
    _releases.append(version)
    return _step(version,world,*args)
campaigns.step_for=observed_step
from mosslight.model import World, Cell
from mosslight.runtime import step_for

def garden():
    return World(7, 4, 4, cells=[Cell(68, 50, 50) for _ in range(16)])

def finish(store, ident):
    while store.work_once(ident):
        pass
    return store.result(ident)
with tempfile.TemporaryDirectory() as temp:
    w = garden()
    for tile in w.workbench['tiles']:
        tile['structure'] = 'rain_barrel'
    store = CampaignStore(Path(temp) / 'workspace.sqlite')
    ident = store.create(w, 1, [{'name': 'Observe', 'events': []}], version='classic-1')
    store.work_once(ident)
    finish(store, ident)
    actual = store.checkpoint(ident, 0, 1)['state']['world']
    _observations.append(_releases)
    _observations.append(store.report(ident)['runtime']['id'])
    store.close()
result = _observations
