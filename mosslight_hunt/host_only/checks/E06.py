from mosslight.engine import create, step
import mosslight.engine as engine
w=create(9,4,4)
for c in w.cells: c.species=None; c.age=0; c.vitality=0; c.moisture=72; c.shade=82; c.nutrients=100
w.cells[0].species="glowcap"; w.cells[0].age=75; w.cells[0].vitality=100
engine._weather=lambda world: "clear"
step(w)
assert w.cells[0].species is None
