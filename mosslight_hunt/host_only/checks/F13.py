from mosslight.engine import create
from mosslight.notebook import add_task,task_list
w=create(13,4,4); add_task(w,"today",0)
assert task_list(w,"overdue")==[] and len(task_list(w,"due"))==1
