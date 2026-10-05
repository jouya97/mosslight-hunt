from mosslight.engine import create
from mosslight.gardening import prune
result=[]
for value in [1, 50, 92, 97, 100]:
    w=create(20,4,4)
    w.cells[0].species="moss"; w.cells[0].age=8; w.cells[0].vitality=50
    setattr(w.cells[0],'vitality',value)
    prune(w,0,0)
    result.append(getattr(w.cells[0],'vitality'))
