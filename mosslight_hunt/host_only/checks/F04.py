from mosslight.engine import create
from mosslight.analysis import suitability
w=create(4,4,4)
for c in w.cells: c.species=None; c.age=c.vitality=0
for i,c in enumerate(w.cells): c.moisture=65; c.shade=52; c.nutrients=50
w.workbench["tiles"][5]["structure"]="shade_cloth"
r=suitability(w,1,1,"moss")
assert r["effective_shade"]==67 and r["score"]==100
