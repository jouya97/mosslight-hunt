from mosslight.engine import create
from mosslight.analysis import patches
w = create(7, 4, 4)
for c in w.cells:
    c.species = None
    c.age = c.vitality = 0
for i in (0, 15, 14, 13):
    w.cells[i].species = 'moss'
    w.cells[i].vitality = 60
r = patches(w)
result = [[p["size"],p["tiles"]] for p in r]
