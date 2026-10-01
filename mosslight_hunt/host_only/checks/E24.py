from mosslight.engine import create
from mosslight.nursery import plant_out
w=create(27,4,4); w.cells[0].nutrients=50; w.workbench["nursery"]=[{"id":5,"species":"fern","count":2,"source":"seed","day":0,"age":4,"hydration":0,"vitality":72,"status":"ready"}]
plant_out(w,5,0,0)
assert w.cells[0].nutrients == 46
