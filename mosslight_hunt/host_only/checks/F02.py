from mosslight.engine import create
from mosslight.analysis import census
w=create(2,4,4)
for c in w.cells: c.species=None; c.age=c.vitality=0
w.cells[0].species="moss"; w.cells[0].vitality=80
assert census(w)["averages"]["vitality"]==80
