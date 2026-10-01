from mosslight.engine import create
from mosslight.gardening import brush
w=create(18,8,8)
assert (4,4) in brush(w,2,2,radius=3,shape="circle")
