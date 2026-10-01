import copy
import unittest
from helpers import empty_world,plant
from mosslight import exchange as e
from mosslight.notebook import add_note,add_task,press_specimen


class ExchangeTests(unittest.TestCase):
    def setUp(self):self.w=empty_world()

    def test_csv_expected_header_values_and_roundtrip(self):
        plant(self.w)
        data=e.export_csv(self.w)
        self.assertEqual(data.splitlines()[0],",".join(e.CSV_FIELDS))
        self.assertEqual(data.splitlines()[1],"0,0,moss,10,80,50,50,50,soil,0,none,0")
        other=empty_world();e.import_csv(other,data)
        self.assertEqual(other.cells[0].species,"moss")
        self.assertEqual(other.revision,1)

    def test_csv_missing_duplicate_and_invalid_rows_are_atomic(self):
        data=e.export_csv(self.w);lines=data.splitlines()
        for broken in ("\n".join(lines[:-1]),"\n".join(lines+[lines[1]]),data.replace(",50,50,50,",",500,50,50,",1)):
            before=copy.deepcopy(self.w.to_dict())
            with self.assertRaises(ValueError):e.import_csv(self.w,broken)
            self.assertEqual(self.w.to_dict(),before)

    def test_blueprint_local_coordinates_and_rotation(self):
        plant(self.w,1,1)
        data=e.blueprint(self.w,1,1,2,1)
        self.assertEqual((data["width"],data["height"]),(2,1))
        turned=e.transform_blueprint(data,1)
        self.assertEqual((turned["width"],turned["height"]),(1,2))
        self.assertEqual((turned["tiles"][0]["x"],turned["tiles"][0]["y"],turned["tiles"][0]["species"]),(0,0,"moss"))
        mirrored=e.transform_blueprint(data,mirror=True)
        self.assertIsNone(mirrored["tiles"][0]["species"])
        self.assertEqual(mirrored["tiles"][1]["species"],"moss")

    def test_blueprint_application_and_collision(self):
        plant(self.w,0,0)
        data=e.blueprint(self.w,0,0,1,0)
        e.apply_blueprint(self.w,data,2,1)
        self.assertEqual(self.w.cell(2,1).species,"moss")
        self.assertEqual(self.w.cell(2,1).age,0)
        before=copy.deepcopy(self.w.to_dict())
        with self.assertRaises(ValueError):e.apply_blueprint(self.w,data,2,1)
        self.assertEqual(self.w.to_dict(),before)
        e.apply_blueprint(self.w,data,2,1,True)

    def test_blueprint_rejects_duplicate_tiles_and_bad_dimensions(self):
        data=e.blueprint(self.w,0,0,1,0)
        data["tiles"][1]["x"]=0
        with self.assertRaises(ValueError):e.validate_blueprint(data)
        data["width"]=True
        with self.assertRaises(ValueError):e.validate_blueprint(data)

    def test_markdown_observations_tasks_and_specimens(self):
        add_note(self.w,"A damp morning",["rain"],[0,0]);add_task(self.w,"Water fern",3)
        plant(self.w);press_specimen(self.w,0,0,"First moss")
        text=e.export_markdown(self.w)
        self.assertIn("### Day 0 · tile 0, 0",text)
        self.assertIn("- [ ] Day 3: Water fern",text)
        self.assertIn("First moss (moss)",text)

    def test_replay_expected_effects_and_source_unchanged(self):
        before=copy.deepcopy(self.w.to_dict())
        other,results=e.replay(self.w,[{"op":"tend","args":{"x":0,"y":0,"action":"water"}},{"op":"terrain","args":{"x":1,"y":0,"terrain":"pond"}}])
        self.assertEqual((other.cells[0].moisture,other.cells[1].moisture),(82,100))
        self.assertEqual(other.revision,2)
        self.assertEqual(self.w.to_dict(),before)
        self.assertEqual(results,[None,None])
