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
w=world(); w.journal=[{"day":0,"text":"original"},{"day":0,"text":"second"}]
d=w.to_dict(); d["journal"][0]["text"]="changed"; d["journal"].append({"day":0,"text":"extra"})
result=copy.deepcopy(w.journal)
w.journal[1]["text"]="world changed"
result.append({"export_second":d["journal"][1]["text"]})
