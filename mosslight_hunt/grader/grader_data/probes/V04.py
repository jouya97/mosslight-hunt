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
    ident = store.create(garden(), 2, [{'name': 'Observe', 'events': []}])
    claim = store.claim(ident)
    before = copy.deepcopy(claim['state'])
    computed = store.compute(claim)
    with patch.object(store, '_checkpoint', side_effect=OSError('checkpoint storage unavailable')):
        try:
            store.publish(claim, computed)
        except OSError:
            pass
        else:
            raise AssertionError('expected checkpoint storage failure')
    row = store.db.execute('SELECT state,status FROM branches WHERE campaign=? AND ordinal=0', (ident,)).fetchone()
    _observations.append([json.loads(row['state']), row['status']])
    store.close()
result = _observations
