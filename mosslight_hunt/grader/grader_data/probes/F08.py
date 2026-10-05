from mosslight.engine import create
from mosslight.analysis import transect
w = create(8, 4, 4)
r = [(p['x'], p['y']) for p in transect(w, 0, 0, 1, 2)]
result = [[(p["x"],p["y"]) for p in transect(w,*ends)] for ends in [(0,0,1,2),(1,2,0,0),(3,0,0,3),(1,1,1,1)]]
