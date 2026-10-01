from mosslight.engine import create, step
import mosslight.engine as engine
w=create(7,4,4)
for c in w.cells: c.species=None; c.age=0; c.vitality=0; c.nutrients=50; c.shade=100
engine._weather=lambda world: "clear"
step(w)
assert all(c.nutrients == 51 for c in w.cells)
