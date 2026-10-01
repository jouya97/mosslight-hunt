from mosslight.engine import create
from mosslight.habitat import after_day
w=create(15,4,4); w.day=3
for c in w.cells: c.species=None; c.age=0; c.vitality=0; c.nutrients=50
w.workbench["tiles"][0]["mulch"]=1
after_day(w,0,0)
assert w.cells[0].nutrients == 51 and w.workbench["tiles"][0]["mulch"] == 0
