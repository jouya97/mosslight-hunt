from mosslight.engine import create
from mosslight.notebook import add_task, task_list
w = create(13, 4, 4)
add_task(w, 'today', 0)
result = [len(task_list(w,kind)) for kind in ("overdue","due")]
