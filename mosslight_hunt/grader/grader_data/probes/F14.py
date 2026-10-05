from mosslight.engine import create
from mosslight.notebook import add_task, complete_task, task_list
w = create(14, 4, 4)
t = add_task(w, 'inspect', 4)
complete_task(w, t['id'])
complete_task(w, t['id'], False)
result = len(task_list(w,"open"))
