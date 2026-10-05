from mosslight.engine import create
from mosslight.analysis import recommendations
w = create(5, 4, 4)
for c in w.cells:
    c.species = None
    c.age = c.vitality = 0
w.cells[0].species = 'moss'
w.cells[0].vitality = 60
result=[sorted([[r["x"],r["y"]] for r in recommendations(w,"moss",empty_only=empty,limit=1200)], key=lambda p:(p[1],p[0])) for empty in (True,False)]
