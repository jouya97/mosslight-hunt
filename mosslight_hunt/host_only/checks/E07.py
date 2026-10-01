from mosslight.engine import create, step
import mosslight.engine as engine
w=create(10,4,4); w.day=36; engine.season=lambda day: "Hush"
for c in w.cells: c.species=None; c.age=0; c.vitality=0; c.moisture=72; c.shade=82; c.nutrients=100
w.cells[0].species="glowcap"; w.cells[0].age=0; w.cells[0].vitality=50
engine._weather=lambda world: "clear"
step(w)
assert w.cells[0].vitality == 55
