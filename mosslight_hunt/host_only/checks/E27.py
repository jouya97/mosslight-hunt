from mosslight.engine import create, step
from mosslight.planning import schedule
w=create(30,4,4)
p=schedule(w,"Water once",2,[[0,0]],"water"); w.day=1
step(w)
assert w.workbench["plans"][0]["status"] == "done" and w.workbench["plans"][0]["remaining"] == 0
