from mosslight.engine import create
from mosslight.analysis import recommendations
w=create(5,4,4)
for c in w.cells: c.species=None; c.age=c.vitality=0
w.cells[0].species="moss"; w.cells[0].vitality=60
assert any((r["x"],r["y"])==(0,0) for r in recommendations(w,"moss",empty_only=False))
