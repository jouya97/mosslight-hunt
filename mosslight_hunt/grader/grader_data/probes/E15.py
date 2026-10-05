from mosslight.engine import create
from mosslight.gardening import brush
w = create(18, 8, 8)
result = [brush(w,2,2,radius=r,shape="circle") for r in (0,1,3)]
