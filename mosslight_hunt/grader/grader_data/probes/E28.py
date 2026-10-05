from mosslight.engine import create
from mosslight.planning import run_plans
w = create(31, 4, 4)
w.day = 1
w.cells[0].moisture = 20
w.workbench['plans'] = [{'id': 1, 'name': 'Late', 'day': 0, 'action': 'water', 'tiles': [[0, 0]], 'repeat': 0, 'remaining': 1, 'status': 'pending', 'last_error': ''}]
w.workbench['next_id'] = 2
run_plans(w)
result = w.cells[0].moisture
