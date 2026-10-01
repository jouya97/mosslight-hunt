from mosslight.engine import create
from mosslight.habitat import after_day
w=create(14,4,4)
for c,t in zip(w.cells,w.workbench["tiles"]): c.species=None; c.age=0; c.vitality=0; c.moisture=60; c.nutrients=60; t["terrain"]="stone"
for i in range(4): w.workbench["tiles"][i]["terrain"]="peat"
after_day(w,0,0)
assert w.workbench["visitors"]["worms"] == 1
