"""Small checks for the everyday local studio workflow."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from mosslight import create, load, render_svg, save, step


class StudioSmokeTests(unittest.TestCase):
    def test_garden_save_and_artwork(self):
        garden = create(34, 8, 6)
        step(garden, 2)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "garden.json"
            save(garden, path)
            restored = load(path)
            self.assertEqual(restored.to_dict(), garden.to_dict())
            drawing = ET.fromstring(render_svg(restored))
            self.assertTrue(drawing.tag.endswith("svg"))

    def test_command_line_workflow(self):
        def run(*args):
            result = subprocess.run([sys.executable, "-B", "-m", "mosslight", *map(str, args)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

        with tempfile.TemporaryDirectory() as folder:
            path, drawing = Path(folder) / "garden.json", Path(folder) / "garden.svg"
            run("new", path, "--seed", 34, "--width", 8, "--height", 6)
            run("grow", path, "--days", 2)
            self.assertIsInstance(json.loads(run("inspect", path)), dict)
            run("render", path, "-o", drawing)
            self.assertTrue(ET.parse(drawing).getroot().tag.endswith("svg"))
            self.assertTrue(run("guide").strip())


if __name__ == "__main__":
    unittest.main()
