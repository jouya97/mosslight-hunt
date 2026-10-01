from mosslight.engine import create
from mosslight.gardening import harvest
w=create(22,4,4); w.cells[0].species="moss"; w.cells[0].age=8; w.cells[0].vitality=80
harvest(w,0,0)
assert w.cells[0].age == 0
try: harvest(w,0,0)
except ValueError: pass
else: raise AssertionError("immediate repeat harvest succeeded")
