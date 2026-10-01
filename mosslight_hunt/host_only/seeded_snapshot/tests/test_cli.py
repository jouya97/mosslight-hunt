import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from mosslight.__main__ import main
from mosslight.model import load


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=str(Path(self.tmp.name)/"garden.json")
        self.run_cli("new",self.path,"--seed","42","--width","4","--height","4")

    def run_cli(self,*args,expected=0):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            result=main(list(args))
        self.assertEqual(result,expected,err.getvalue())
        return out.getvalue(),err.getvalue()

    def test_new_grow_inspect(self):
        self.run_cli("grow",self.path,"--days","3")
        result,_=self.run_cli("inspect",self.path)
        self.assertEqual(json.loads(result)["day"],3)

    def test_command_and_report(self):
        self.run_cli("command",self.path,json.dumps({"op":"rename","args":{"title":"Wet hollow"}}))
        output,_=self.run_cli("report",self.path)
        self.assertEqual(json.loads(output)["title"],"Wet hollow")

    def test_command_failure_does_not_write_file(self):
        before=Path(self.path).read_bytes()
        self.run_cli("command",self.path,'{"op":"grow","args":{"days":0}}',expected=2)
        self.assertEqual(Path(self.path).read_bytes(),before)

    def test_forecast_output_is_separate_and_compare(self):
        other=str(Path(self.tmp.name)/"future.json")
        self.run_cli("forecast",self.path,"--days","2","-o",other)
        self.assertEqual(load(self.path).day,0)
        self.assertEqual(load(other).day,2)
        out,_=self.run_cli("compare",self.path,other)
        self.assertEqual(json.loads(out)["days"],2)
        self.run_cli("forecast",self.path,"-o",self.path,expected=2)
        self.assertEqual(load(self.path).day,0)

    def test_exports_and_map(self):
        for format in ("csv","markdown","history"):
            target=str(Path(self.tmp.name)/format)
            self.run_cli("export",self.path,format,"-o",target)
            self.assertGreater(Path(target).stat().st_size,30)
        svg=str(Path(self.tmp.name)/"map.svg")
        self.run_cli("render",self.path,"--layer","moisture","-o",svg)
        self.assertIn("MOISTURE",Path(svg).read_text())

    def test_replay_writes_output_and_keeps_source(self):
        script=Path(self.tmp.name)/"script.json"
        script.write_text('[{"op":"grow","args":{"days":3}}]')
        target=str(Path(self.tmp.name)/"replayed.json")
        self.run_cli("replay",self.path,str(script),"-o",target)
        self.assertEqual(load(target).day,3)
        self.assertEqual(load(self.path).day,0)

    def test_blueprint_and_guide(self):
        output=str(Path(self.tmp.name)/"pattern.json")
        self.run_cli("blueprint",self.path,"--rect","0","0","2","1","--turns","1","-o",output)
        data=json.loads(Path(output).read_text())
        self.assertEqual((data["width"],data["height"]),(2,3))
        out,_=self.run_cli("guide")
        self.assertIn("commands",json.loads(out))

    def test_missing_file_error(self):
        _,err=self.run_cli("inspect",str(Path(self.tmp.name)/"missing"),expected=2)
        self.assertIn("mosslight:",err)
