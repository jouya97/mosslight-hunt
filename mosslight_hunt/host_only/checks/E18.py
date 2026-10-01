from mosslight.engine import create
from mosslight.gardening import prune
w=create(21,4,4); w.cells[0].species="moss"; w.cells[0].age=8; w.cells[0].vitality=97
prune(w,0,0)
assert w.cells[0].vitality == 100
