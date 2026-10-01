from mosslight.engine import create
from mosslight.gardening import transplant
w=create(19,4,4); w.cells[0].species="moss"; w.cells[0].age=3; w.cells[0].vitality=60; w.workbench["tiles"][0]["stress"]=27
transplant(w,0,0,1,0)
assert w.workbench["tiles"][0]["stress"] == 0 and w.workbench["tiles"][1]["stress"] == 27
