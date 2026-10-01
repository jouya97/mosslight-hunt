from mosslight.engine import create
from mosslight.habitat import after_day
w=create(13,4,4)
for c in w.cells: c.species=None; c.age=0; c.vitality=0
for c in w.cells[:3]: c.species="glowcap"; c.age=0; c.vitality=50
after_day(w,0,0)
assert w.workbench["visitors"]["fireflies"] == 1
