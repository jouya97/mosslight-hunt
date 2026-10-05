_observations = []
from mosslight.history import HistoryConflict, HistoryStore
from mosslight.model import World, Cell

def command(op, **args):
    return {'op': op, 'args': args}
store = HistoryStore(':memory:')
world = World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)])
branch = store.create(world)['branch']
store.append(branch, command('note', content='observed'))
edited = store.append(branch, command('edit_note', ident=1, content='first revision'))
edit_id = edited['events'][-1]['id']
source = store.append(branch, command('delete_entry', collection='notes', ident=1))
corrected = store.correct(branch, {edit_id: command('edit_note', ident=1, content='historical correction')})
_observations.append(corrected['status'])
_observations.append(corrected['world']['workbench']['notes'])
_observations.append(corrected['events'][1]['command']['args']['content'])
_observations.append(list(corrected['events'][1]['command']['args']['ident']))
_observations.append(store.snapshot(branch)['world']['workbench']['notes'])
store.close()
result = _observations
