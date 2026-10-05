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
for initial_day,new_day in [(0,1),(4,9)]:
    s=server(); s.world.day=initial_day; s.save_path="unused.json"; original=s.world
    trial=world(); trial.day=new_day
    with patch("mosslight.server.save",side_effect=OSError("disk full")):
        observed=outcome(lambda:s.publish(trial))
    result.append([observed,s.world.day,s.world is original,[d["day"] for d in s.undo_stack]])
