from mosslight.engine import create
from mosslight.gardening import craft
w=create(23,4,4); w.workbench["inventory"]["nectar"]=2; w.workbench["inventory"]["spores"]=1
before=w.workbench["inventory"].copy()
try: craft(w,"tonic",2)
except ValueError: pass
else: raise AssertionError("craft should reject insufficient two-batch inputs")
assert w.workbench["inventory"] == before
