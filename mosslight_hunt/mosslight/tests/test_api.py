import copy
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from helpers import empty_world
from mosslight.model import load
from mosslight.server import make_server


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"garden.json"
        self.server=make_server(empty_world(),0,str(self.path))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)

    def tearDown(self):
        self.conn.close();self.server.shutdown();self.server.server_close();self.thread.join(5);self.tmp.cleanup()

    def request(self,path,body=None):
        self.conn.request("GET" if body is None else "POST",path,None if body is None else json.dumps(body),{"Content-Type":"application/json"})
        response=self.conn.getresponse();raw=response.read()
        mime=response.getheader("Content-Type")
        return response.status,json.loads(raw) if "application/json" in mime else raw.decode()

    def command(self,op,args,revision=None):
        body={"command":{"op":op,"args":args}}
        if revision is not None:body["revision"]=revision
        return self.request("/api/command",body)

    def test_command_persists_and_stale_revision_conflicts(self):
        code,data=self.command("terrain",{"x":0,"y":0,"terrain":"pond"},0)
        self.assertEqual(code,200)
        self.assertEqual(data["world"]["cells"][0]["moisture"],100)
        self.assertEqual(load(self.path).workbench["tiles"][0]["terrain"],"pond")
        code,_=self.command("grow",{"days":1},0)
        self.assertEqual(code,409)

    def test_undo_redo_restore_and_revision_is_monotonic(self):
        self.command("tend",{"x":0,"y":0,"action":"water"})
        code,data=self.request("/api/undo",{"revision":1})
        self.assertEqual((code,data["world"]["cells"][0]["moisture"],data["world"]["revision"]),(200,50,2))
        code,data=self.request("/api/redo",{"revision":2})
        self.assertEqual((code,data["world"]["cells"][0]["moisture"],data["world"]["revision"]),(200,82,3))
        self.assertEqual(load(self.path).revision,3)

    def test_new_edit_clears_redo(self):
        self.command("grow",{"days":1});self.request("/api/undo",{})
        self.command("rename",{"title":"New path"})
        code,_=self.request("/api/redo",{})
        self.assertEqual(code,400)

    def test_failed_persistence_preserves_memory_and_history(self):
        before=copy.deepcopy(self.server.world.to_dict())
        with patch("mosslight.server.save",side_effect=OSError("disk full")):
            code,data=self.command("grow",{"days":1})
        self.assertEqual(code,500)
        self.assertIn("disk full",data["error"])
        self.assertEqual(self.server.world.to_dict(),before)
        self.assertEqual(self.server.undo_stack,[])

    def test_forecast_is_read_only(self):
        code,data=self.request("/api/forecast?days=2&every=2")
        self.assertEqual(code,200)
        self.assertEqual([p["day"] for p in data["timeline"]],[0,2])
        self.assertEqual(self.server.world.day,0)
        self.assertEqual(self.server.undo_stack,[])

    def test_reports_catalog_and_exports(self):
        for path,fragment in (("/api/catalog","species"),("/api/report","census"),("/api/survey.csv","x,y,species"),("/api/notebook.md","# A world"),("/api/history.svg","<svg"),("/api/svg?layer=terrain","TERRAIN")):
            with self.subTest(path=path):
                code,data=self.request(path)
                self.assertEqual(code,200)
                self.assertIn(fragment,data)

    def test_invalid_queries_return_400(self):
        for path in ("/api/forecast?days=0","/api/svg?layer=bad","/api/blueprint","/api/recommend?species=dragon","/api/history.svg?metric=bad"):
            with self.subTest(path=path):self.assertEqual(self.request(path)[0],400)

    def test_note_search_and_transect(self):
        self.command("note",{"content":"Wet moss","labels":["rain"]})
        code,data=self.request("/api/notes?q=wet&tag=rain")
        self.assertEqual((code,len(data)),(200,1))
        code,data=self.request("/api/transect?x1=0&y1=0&x2=1&y2=0")
        self.assertEqual([p["x"] for p in data],[0,1])

    def test_replay_failure_is_atomic(self):
        code,_=self.request("/api/replay",{"commands":[{"op":"grow","args":{"days":1}},{"op":"bad"}]})
        self.assertEqual(code,400)
        self.assertEqual(self.server.world.day,0)

    def test_import_revision_checked_and_undoable(self):
        data=empty_world().to_dict();data["seed"]=99
        code,result=self.request("/api/import",{"world":data,"revision":0})
        self.assertEqual((code,result["world"]["seed"],result["world"]["revision"]),(200,99,1))
        self.assertEqual(self.request("/api/import",{"world":data,"revision":0})[0],409)
        _,result=self.request("/api/undo",{})
        self.assertEqual(result["world"]["seed"],7)

    def test_weather_calendar_and_nursery_routes(self):
        code,data=self.request("/api/almanac?days=3")
        self.assertEqual((code,data["start"],data["end"]),(200,1,3))
        code,data=self.request("/api/calendar?days=2")
        self.assertEqual([d["day"] for d in data],[0,1])
        self.assertEqual(self.request("/api/nursery"),(200,[]))

    def test_experiment_route_is_read_only(self):
        code,data=self.request("/api/experiment",{"days":2,"treatments":[{"name":"Shelter","events":[{"offset":0,"command":{"op":"structure","args":{"x":0,"y":0,"structure":"shade_cloth"}}}]}]})
        self.assertEqual(code,200)
        self.assertEqual([b["name"] for b in data["branches"]],["control","Shelter"])
        self.assertEqual(self.server.world.workbench["tiles"][0]["structure"],"none")
        self.assertEqual(self.server.undo_stack,[])
