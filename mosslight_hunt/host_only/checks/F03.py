from mosslight.engine import create
from mosslight.analysis import census
w=create(3,4,4)
for c in w.cells: c.species=None; c.age=c.vitality=0
for i,s in enumerate(("moss","fern")): w.cells[i].species=s; w.cells[i].vitality=60
assert census(w)["diversity"]==0.6931
