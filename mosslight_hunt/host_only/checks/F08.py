from mosslight.engine import create
from mosslight.analysis import transect
w=create(8,4,4)
r=[(p["x"],p["y"]) for p in transect(w,0,0,1,2)]
assert r==[(0,0),(1,1),(1,2)]
