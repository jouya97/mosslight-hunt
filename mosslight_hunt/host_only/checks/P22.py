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
from mosslight.__main__ import main
from mosslight.model import save
import tempfile, contextlib, os
from pathlib import Path
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'garden.json';save(world(),path);before=path.read_bytes()
    alias=str(path.parent/'sub'/ '..'/'garden.json'); (path.parent/'sub').mkdir()
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
        status=main(['forecast',str(path),'--days','1','--output',alias])
    assert status!=0 and path.read_bytes()==before
