import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from mosslight import create, load, render_svg, save, step
from mosslight.server import make_server


class IOTests(unittest.TestCase):
    def test_save_load_and_svg_export(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "garden.json"
            garden = create(88, 5, 4)
            step(garden, 19)
            save(garden, path)
            restored = load(path)
            self.assertEqual(restored.to_dict(), garden.to_dict())
            svg = render_svg(restored)
            self.assertIn('viewBox="0 0', svg)
            self.assertIn('DAY 019', svg)
            self.assertEqual(svg.count('class="tile"'), 20)
            self.assertNotIn('tabindex="0"', svg)
            self.assertIn('tabindex="0"', render_svg(restored, interactive=True))

    def test_http_lifecycle_and_persisted_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "autosave.json"
            server = make_server(create(5, 4, 4), 0, str(path))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            def request(method, route, payload=None):
                body = json.dumps(payload).encode() if payload is not None else None
                conn.request(method, route, body, {"Content-Type": "application/json"} if body else {})
                response = conn.getresponse()
                raw = response.read()
                return response.status, raw
            try:
                code, raw = request("GET", "/api/world")
                self.assertEqual(code, 200)
                initial = json.loads(raw)["world"]
                code, raw = request("POST", "/api/action", {"x": 0, "y": 0, "action": "plant_glowcap", "revision": 0})
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(raw)["world"]["cells"][0]["species"], "glowcap")
                self.assertEqual(load(path).revision, 1)
                code, _ = request("POST", "/api/step", {"days": 1, "revision": 0})
                self.assertEqual(code, 409)
                code, raw = request("POST", "/api/step", {"days": 7, "revision": 1})
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(raw)["world"]["day"], 7)
                code, raw = request("GET", "/api/svg")
                self.assertEqual(code, 200)
                self.assertIn(b'<svg ', raw)
                code, raw = request("POST", "/api/import", {"world": initial})
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(raw)["world"], initial)
                code, _ = request("POST", "/api/import", {"world": {"version": 900}})
                self.assertEqual(code, 400)
                code, raw = request("GET", "/")
                self.assertEqual(code, 200)
                self.assertIn(b"Mosslight", raw)
            finally:
                conn.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
