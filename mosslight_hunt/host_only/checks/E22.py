from mosslight.engine import create
from mosslight.nursery import _batch, advance_nursery
w=create(25,4,4); _batch(w,"moss",1,"seed"); w.workbench["nursery"][0]["status"]="ready"; advance_nursery(w)
assert w.workbench["nursery"][0]["vitality"] == 63
