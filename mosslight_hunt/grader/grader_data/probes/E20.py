from mosslight.engine import create
from mosslight.gardening import craft
w = create(23, 4, 4)
w.workbench['inventory']['nectar'] = 2
w.workbench['inventory']['spores'] = 1
before = w.workbench['inventory'].copy()
error = None
try:
    craft(w,"tonic",2)
except Exception as exc:
    error = type(exc).__name__
result = [error,{k:w.workbench["inventory"][k]-v for k,v in before.items()}]
