import unittest
import xml.etree.ElementTree as ET
from helpers import empty_world
from mosslight.charts import color_scale,render_map,render_history
from mosslight.engine import step
from mosslight.catalog import LAYERS


class ChartTests(unittest.TestCase):
    def test_fixed_color_scale_endpoints(self):
        self.assertEqual(color_scale(0),"#dab76d")
        self.assertEqual(color_scale(100),"#369294")
        self.assertEqual(color_scale(-20),color_scale(0))

    def test_all_layers_valid_xml_and_tile_count(self):
        w=empty_world();w.workbench["title"]='Fern <hollow> & "pond"'
        for layer in LAYERS:
            with self.subTest(layer=layer):
                svg=render_map(w,layer,True)
                ET.fromstring(svg)
                self.assertEqual(svg.count('class="tile"'),16)
                self.assertEqual(svg.count('tabindex="0"'),16)

    def test_history_empty_and_known_points(self):
        w=empty_world()
        self.assertIn("Advance a day",render_history(w))
        step(w,2)
        svg=render_history(w)
        ET.fromstring(svg)
        self.assertIn("Day 1",svg)
        self.assertIn("Day 2",svg)
        self.assertEqual(svg.count('<circle '),2)
        with self.assertRaises(ValueError):render_history(w,"unknown")
