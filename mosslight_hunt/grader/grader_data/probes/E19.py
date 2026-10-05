from mosslight.engine import create
from mosslight.gardening import harvest
w = create(22, 4, 4)
w.cells[0].species = 'moss'
w.cells[0].age = 8
w.cells[0].vitality = 80
harvest(w, 0, 0)
age_after = w.cells[0].age
error = None
try:
    harvest(w,0,0)
except Exception as exc:
    error = type(exc).__name__
result = [age_after,error]
