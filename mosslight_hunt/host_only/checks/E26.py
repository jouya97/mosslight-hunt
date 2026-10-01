from mosslight.engine import create
from mosslight.planning import schedule
w=create(29,4,4)
p=schedule(w,"Tomorrow",1,[[0,0]],"water")
assert p["day"] == 1
