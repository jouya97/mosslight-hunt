from mosslight.engine import create
from mosslight.analysis import census
w=create(1,4,4)
for c in w.cells: c.species=None; c.age=c.vitality=0
w.cells[0].species='moss'; w.cells[0].vitality=50
assert census(w)['coverage']==6.25
