_observations = []
from mosslight.history import HistoryConflict, HistoryStore
from mosslight.model import World, Cell

def command(op, **args):
    return {'op': op, 'args': args}
store = HistoryStore(':memory:')
world = World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)])
branch = store.create(world)['branch']
source = store.fork(branch)['branch']
planted = store.append(source, command('tend', x=0, y=0, action='plant_moss'))
cleared = store.append(source, command('tend', x=0, y=0, action='clear'))
(a, b) = (planted['events'][0]['id'], cleared['events'][1]['id'])
local = store.cherry_pick(source, branch, [a, b])
target = store.cherry_pick(source, branch, [b])
target = store.cherry_pick(source, target['branch'], [a])
before_count = store.db.execute('SELECT COUNT(*) FROM history_branches').fetchone()[0]
try:
    store.rebase(local['branch'], target['branch'])
except HistoryConflict as error:
    _observations.append(error.details['kind'])
else:
    raise AssertionError('Opposite authored orders must produce an explicit order conflict')
_observations.append(store.db.execute('SELECT COUNT(*) FROM history_branches').fetchone()[0] - before_count)
authored = store.append(source, command('tend', x=2, y=0, action='water'))
c = authored['events'][-1]['id']
right = store.cherry_pick(source, branch, [b, c])
store.db.execute('DELETE FROM history_checkpoints')
merged = store.rebase(local['branch'], right['branch'])
_observations.append([event['command']['args']['action'] for event in merged['events']])
_observations.append(merged['world']['cells'][0]['species'])
_observations.append(merged['world']['cells'][2]['moisture'])
store.close()
result = _observations
