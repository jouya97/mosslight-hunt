import copy, io, json, threading
from unittest.mock import patch
from mosslight.model import World, Cell
from mosslight.server import GardenServer, GardenHandler
def world():
    return World(7,4,4,cells=[Cell(50,50,50) for _ in range(16)])
def outcome(fn):
    try:
        value=fn()
        return {"value":value} if isinstance(value,(str,int,float,bool,list,dict,type(None))) else {"returned_type":type(value).__name__}
    except Exception as exc:
        return {"exception":type(exc).__name__}
def server():
    s=object.__new__(GardenServer)
    s.world=world(); s.save_path=None; s.lock=threading.RLock(); s.undo_stack=[]; s.redo_stack=[]
    return s
def post(s,path,body):
    raw=json.dumps(body).encode()
    h=object.__new__(GardenHandler); h.server=s; h.path=path; h.headers={"Content-Length":str(len(raw))}; h.rfile=io.BytesIO(raw)
    h._json=lambda status,data:(status,data)
    return h.do_POST()
result=[]
for current,revision in [(0,False),(1,True)]:
    s=server(); s.world.revision=current
    code,data=post(s,"/api/import",{"world":world().to_dict(),"revision":revision})
    result.append([code,s.world.revision])
