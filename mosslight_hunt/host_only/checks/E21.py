from mosslight.engine import create
from mosslight.nursery import _batch, water_batch
w=create(24,4,4); b=_batch(w,"moss",1,"seed"); w.workbench["nursery"][0]["hydration"]=0; water_batch(w,b["id"])
assert w.workbench["nursery"][0]["hydration"] == 3
