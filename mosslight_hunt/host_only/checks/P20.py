import copy, io, json, threading, types
from mosslight.model import World, Cell
from mosslight.server import GardenServer, GardenHandler
from unittest.mock import patch
def world():
    return World(7,4,4,cells=[Cell(50,50,50) for _ in range(16)])
def rejects(fn):
    try: fn()
    except ValueError: return
    raise AssertionError('Expected ValueError')
def server():
    s=object.__new__(GardenServer)
    s.world=world(); s.save_path=None; s.lock=threading.RLock(); s.undo_stack=[]; s.redo_stack=[]
    return s
def post(s,path,body):
    raw=json.dumps(body).encode()
    h=object.__new__(GardenHandler);h.server=s;h.path=path;h.headers={'Content-Length':str(len(raw))};h.rfile=io.BytesIO(raw)
    h._json=lambda status,data: (status,data)
    return h.do_POST()
s=server(); s.world.revision=8; d=world().to_dict(); d["revision"]=2; s.undo_stack=[d]; code,data=post(s,"/api/undo",{}); assert code==200 and data["world"]["revision"]==9
