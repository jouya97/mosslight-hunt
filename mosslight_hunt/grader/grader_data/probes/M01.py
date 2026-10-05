_observations = []
import copy
from mosslight.model import Cell, World
from mosslight.save_merge import reconcile, verify_receipt
base = World(7, 4, 4, cells=[Cell(50, 50, 50) for _ in range(16)]).to_dict()
(left, right) = (copy.deepcopy(base), copy.deepcopy(base))
for save in (left, right):
    save['workbench']['notes'] = [{'id': 1, 'day': 0, 'text': 'same field observation', 'tags': [], 'tile': None}]
    save['workbench']['next_id'] = 2
result = reconcile(base, left, right, left_origin='desk', right_origin='field')
_observations.append(result['status'])
notes = result['world']['workbench']['notes']
_observations.append(notes)
_observations.append(len({note['id'] for note in notes}))
expected_origins = {('desk', 1), ('field', 1)}
import json
_observations.append(sorted([json.loads(k) for k in result['receipt']['allocation']]))
_observations.append(result['world']['workbench']['next_id'])
result = _observations
