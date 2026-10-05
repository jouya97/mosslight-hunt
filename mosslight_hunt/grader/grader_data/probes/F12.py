from mosslight.engine import create
from mosslight.notebook import press_specimen
w = create(12, 4, 4)
c = w.cells[0]
c.species = 'moss'
c.moisture = 23
c.nutrients = 47
c.shade = 61
c.age = 8
c.vitality = 60
r = press_specimen(w, 0, 0)
result = {k:r.get(k) for k in ("moisture","nutrients","shade","species","age","vitality")}
