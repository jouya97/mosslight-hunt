from mosslight.engine import create
from mosslight.gardening import prune
w=create(20,4,4); w.cells[0].species="moss"; w.cells[0].age=2; w.cells[0].vitality=40
prune(w,0,0)
assert w.cells[0].age == 0
