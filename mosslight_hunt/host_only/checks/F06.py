from mosslight.engine import create
from mosslight.analysis import alerts
w=create(6,4,4)
for c in w.cells: c.species=None; c.age=c.vitality=0
w.cells[0].species="moss"; w.cells[0].vitality=50; w.workbench["tiles"][0]["stress"]=50
assert "prolonged stress" in alerts(w)[0]["issues"]
