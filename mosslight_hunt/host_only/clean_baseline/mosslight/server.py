"""Loopback studio API. Writes publish only after validation and persistence."""
from __future__ import annotations
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlsplit
from .engine import create, summary
from .model import World, save
from .commands import execute, command_catalog
from .analysis import report, forecast, recommendations, transect
from .charts import render_map, render_history
from .catalog import field_guide
from .exchange import export_csv, export_markdown, blueprint, replay
from .notebook import search_notes
from .weather import almanac, calendar
from .experiments import experiment
from .nursery import nursery_report

STATIC = Path(__file__).parent / "static"


class GardenServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, world, save_path=None):
        super().__init__(address, GardenHandler)
        self.world = world
        self.save_path = save_path
        self.lock = threading.RLock()
        self.undo_stack = []
        self.redo_stack = []

    def persist(self):
        if self.save_path:
            save(self.world, self.save_path)

    def publish(self, trial, *, history=True):
        if self.save_path:
            save(trial, self.save_path)
        if history:
            self.undo_stack.append(copy.deepcopy(self.world.to_dict()))
            self.undo_stack = self.undo_stack[-30:]
            self.redo_stack.clear()
        self.world = trial


class GardenHandler(BaseHTTPRequestHandler):
    server: GardenServer

    def log_message(self, format, *args):
        return

    def _respond(self, status, content, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status, data):
        self._respond(status,json.dumps(data).encode(),"application/json; charset=utf-8")

    def _state(self):
        return {"world":self.server.world.to_dict(),"summary":summary(self.server.world),
                "undo":len(self.server.undo_stack),"redo":len(self.server.redo_stack)}

    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        query = {k:v[-1] for k,v in parse_qs(url.query).items()}
        if path in ("/","/app.js","/app.css"):
            name = "index.html" if path == "/" else path[1:]
            mime = {"index.html":"text/html","app.js":"text/javascript","app.css":"text/css"}[name]
            return self._respond(200,(STATIC/name).read_bytes(),mime+"; charset=utf-8")
        try:
            with self.server.lock:
                world = self.server.world
                if path == "/api/world":
                    return self._json(200,self._state())
                if path == "/api/catalog":
                    return self._json(200,{**field_guide(),"commands":command_catalog()})
                if path == "/api/almanac":
                    return self._json(200,almanac(world,int(query.get("days",12))))
                if path == "/api/calendar":
                    return self._json(200,calendar(world,int(query.get("days",12))))
                if path == "/api/nursery":
                    return self._json(200,nursery_report(world))
                if path == "/api/report":
                    return self._json(200,report(world))
                if path == "/api/forecast":
                    return self._json(200,forecast(world,int(query.get("days",7)),int(query.get("every",1))))
                if path == "/api/recommend":
                    return self._json(200,recommendations(world,query.get("species","moss"),int(query.get("limit",10))))
                if path == "/api/notes":
                    return self._json(200,search_notes(world,query.get("q",""),query.get("tag")))
                if path == "/api/blueprint":
                    return self._json(200,blueprint(world,*(int(query[k]) for k in ("x1","y1","x2","y2"))))
                if path == "/api/transect":
                    return self._json(200,transect(world,*(int(query[k]) for k in ("x1","y1","x2","y2"))))
                if path == "/api/svg":
                    return self._respond(200,render_map(world,query.get("layer","art"),True).encode(),"image/svg+xml; charset=utf-8")
                if path == "/api/history.svg":
                    return self._respond(200,render_history(world,query.get("metric","moisture")).encode(),"image/svg+xml; charset=utf-8")
                if path == "/api/survey.csv":
                    return self._respond(200,export_csv(world).encode(),"text/csv; charset=utf-8")
                if path == "/api/notebook.md":
                    return self._respond(200,export_markdown(world).encode(),"text/markdown; charset=utf-8")
            self._json(404,{"error":"Unknown route"})
        except (ValueError,TypeError,KeyError) as exc:
            self._json(400,{"error":str(exc)})

    def do_POST(self):
        path = urlsplit(self.path).path
        routes = ("/api/step","/api/action","/api/new","/api/import","/api/command","/api/replay","/api/undo","/api/redo","/api/experiment")
        if path not in routes:
            return self._json(404,{"error":"Unknown route"})
        try:
            size = int(self.headers.get("Content-Length","0"))
            if not 0 <= size <= 4_000_000:
                raise ValueError("Request is too large")
            body = json.loads(self.rfile.read(size)) if size else {}
            if not isinstance(body,dict):
                raise ValueError("Expected a JSON object")
            with self.server.lock:
                if "revision" in body and (type(body["revision"]) is not int or body["revision"] != self.server.world.revision):
                    return self._json(409,{"error":"The garden changed; refresh and try again"})
                if path == "/api/experiment":
                    return self._json(200,experiment(self.server.world,body.get("days",7),body.get("treatments"),body.get("every",1)))
                trial = World.from_dict(copy.deepcopy(self.server.world.to_dict()))
                result = None
                if path == "/api/step":
                    execute(trial,{"op":"grow","args":{"days":body.get("days",1)}})
                elif path == "/api/action":
                    execute(trial,{"op":"tend","args":{k:body.get(k) for k in ("x","y","action")}})
                elif path == "/api/command":
                    result = execute(trial,body.get("command"))
                elif path == "/api/replay":
                    trial,result = replay(trial,body.get("commands"))
                elif path == "/api/new":
                    trial = create(body.get("seed",7),body.get("width",16),body.get("height",11))
                    trial.revision = self.server.world.revision+1
                elif path == "/api/import":
                    trial = World.from_dict(body.get("world"))
                    # Unconditional legacy imports preserve their saved revision.
                    if "revision" in body:
                        trial.revision = self.server.world.revision+1
                elif path in ("/api/undo","/api/redo"):
                    source = self.server.undo_stack if path == "/api/undo" else self.server.redo_stack
                    target = self.server.redo_stack if path == "/api/undo" else self.server.undo_stack
                    if not source:
                        raise ValueError("No change to undo or redo")
                    trial = World.from_dict(copy.deepcopy(source[-1]))
                    trial.revision = self.server.world.revision+1
                    previous = copy.deepcopy(self.server.world.to_dict())
                    self.server.publish(trial,history=False)
                    source.pop()
                    target.append(previous)
                    return self._json(200,self._state())
                self.server.publish(trial)
                return self._json(200,{**self._state(),"result":result})
        except (ValueError,TypeError,KeyError) as exc:
            self._json(400,{"error":str(exc)})
        except OSError as exc:
            self._json(500,{"error":f"Garden could not be saved: {exc}"})


def make_server(world, port=8765, save_path=None):
    return GardenServer(("127.0.0.1",port),world,save_path)
