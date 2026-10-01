from mosslight.engine import create, step
import mosslight.engine as engine
w=create(6,4,4)
for c in w.cells: c.species=None; c.age=0; c.vitality=0; c.moisture=65; c.shade=50; c.nutrients=50
w.cells[0].species="moss"; w.cells[0].age=0; w.cells[0].vitality=50
w.workbench["tiles"][0]["structure"]="shade_cloth"
engine._weather=lambda world: "clear"
step(w)
assert w.cells[0].vitality == 55
