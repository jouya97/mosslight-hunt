_observations = []
import copy
from mosslight.history import _rebase_events
creator = {'id': 'creator', 'command': {'op': 'note', 'args': {'content': 'target'}}, 'bindings': {}}
edit = {'id': 'edit', 'command': {'op': 'edit_note', 'args': {'ident': {'$ref': 'event:creator:notes'}, 'content': 'same authored content'}}, 'bindings': {'ident': 2}}
base = [creator, edit]
local = copy.deepcopy(base)
local[1]['bindings']['ident'] = 1
target = copy.deepcopy(local)
target[1]['command']['args']['content'] = 'new remote content'
result = _rebase_events(base, local, target)
_observations.append(result)
_observations.append(base[1]['bindings']['ident'])
_observations.append(local[1]['command']['args']['content'])
result = _observations
