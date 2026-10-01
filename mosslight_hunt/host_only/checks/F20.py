from mosslight.engine import create
from mosslight.weather import calendar
w=create(3,4,4); w.workbench["plans"]=[{"id":1,"name":"twice","action":{"op":"water","args":{}},"status":"pending","day":1,"repeat":2,"remaining":2}]
r=calendar(w,6)
assert sum(any(p["id"]==1 for p in d["plans"]) for d in r)==2
