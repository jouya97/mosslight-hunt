from mosslight.engine import create, step
import mosslight.engine as engine
w=create(5,4,4)
for c in w.cells: c.species=None; c.age=0; c.vitality=0; c.moisture=50; c.shade=100
w.cells[0].moisture=0
engine._weather=lambda world: "clear"
engine.season=lambda day: "Dawn"
step(w)
assert w.cells[1].moisture == 42
