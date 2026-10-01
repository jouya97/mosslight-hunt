from mosslight.engine import create
from mosslight.gardening import rectangle
w=create(17,4,4)
assert rectangle(w,1,1,2,2) == [(1,1),(2,1),(1,2),(2,2)]
