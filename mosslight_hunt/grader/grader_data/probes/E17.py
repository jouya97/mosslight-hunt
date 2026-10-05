from mosslight.engine import create
from mosslight.gardening import prune
result=[]
for value in [0, 2, 5, 8]:
    w=create(20,4,4)
    w.cells[0].species="moss"; w.cells[0].age=8; w.cells[0].vitality=50
    setattr(w.cells[0],'age',value)
    prune(w,0,0)
    result.append(getattr(w.cells[0],'age'))
