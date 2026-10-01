from mosslight.engine import create
from mosslight.habitat import after_day
w=create(16,4,4); c=w.cells[0]; c.species="moss"; c.age=1; c.vitality=30; w.workbench["tiles"][0]["stress"]=10
after_day(w,0,0)
assert w.workbench["tiles"][0]["stress"] == 7
