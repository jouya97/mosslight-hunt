from mosslight.engine import create
from mosslight.gardening import rectangle
w = create(17, 4, 4)
result = [rectangle(w,*p) for p in [(1,1,2,2),(2,2,1,1),(0,0,0,0),(3,0,3,3)]]
