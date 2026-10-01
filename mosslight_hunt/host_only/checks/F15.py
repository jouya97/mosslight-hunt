from mosslight.engine import create
from mosslight.notebook import add_task,task_list
w=create(15,4,4); a=add_task(w,"later",10); b=add_task(w,"soon",2)
assert [t["text"] for t in task_list(w)]==["soon","later"]
