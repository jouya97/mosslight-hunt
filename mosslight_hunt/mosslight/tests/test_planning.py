import unittest
from helpers import empty_world,plant
from mosslight import planning as p
from mosslight.engine import step
from mosslight.habitat import set_terrain


class PlanningTests(unittest.TestCase):
    def setUp(self):self.w=empty_world()

    def test_bed_deduplication_unique_names_and_deletion(self):
        bed=p.add_bed(self.w,"Hollow",[[0,0],[0,0],[1,0]])
        self.assertEqual(p.bed_tiles(self.w,bed["id"]),[[0,0],[1,0]])
        with self.assertRaises(ValueError):p.add_bed(self.w,"hollow",[[2,0]])
        p.delete_bed(self.w,bed["id"])
        self.assertEqual(self.w.workbench["beds"],[])

    def test_schedule_runs_before_ecology(self):
        p.schedule(self.w,"Plant",1,[[0,0]],"plant_moss")
        step(self.w)
        self.assertEqual(self.w.cell(0,0).age,1)
        self.assertEqual(self.w.workbench["plans"][0]["status"],"done")

    def test_finite_repeat_calendar(self):
        p.schedule(self.w,"Compost",2,[[0,0]],"compost",repeat=3,runs=2)
        step(self.w,2)
        plan=self.w.workbench["plans"][0]
        self.assertEqual((plan["day"],plan["remaining"],plan["status"]),(5,1,"pending"))
        step(self.w,3)
        self.assertEqual(self.w.workbench["plans"][0]["status"],"done")
        self.assertEqual(self.w.workbench["plans"][0]["remaining"],0)

    def test_failed_plan_does_not_partially_plant(self):
        set_terrain(self.w,1,0,"pond")
        p.schedule(self.w,"Impossible",1,[[0,0],[1,0]],"plant_moss")
        step(self.w)
        self.assertIsNone(self.w.cell(0,0).species)
        self.assertEqual(self.w.workbench["plans"][0]["status"],"failed")
        self.assertIn("terrain",self.w.workbench["plans"][0]["last_error"])

    def test_cancel_prevents_execution(self):
        plan=p.schedule(self.w,"Cancelled",1,[[0,0]],"plant_moss")
        p.cancel_plan(self.w,plan["id"]);step(self.w)
        self.assertIsNone(self.w.cells[0].species)
        with self.assertRaises(ValueError):p.cancel_plan(self.w,plan["id"])

    def test_reject_bad_schedule(self):
        for args in ((0,0,1),(1,0,2),(1,-1,1)):
            day,repeat,runs=args
            with self.assertRaises(ValueError):p.schedule(self.w,"bad",day,[[0,0]],"water",repeat,runs)

    def test_rule_strict_threshold_and_snapshot_conditions(self):
        self.w.cells[0].moisture=20
        p.add_rule(self.w,"first",[[0,0]],"moisture","below",30,"water")
        p.add_rule(self.w,"second",[[0,0]],"moisture","below",30,"water")
        p.run_rules(self.w)
        self.assertEqual(self.w.cells[0].moisture,84)
        self.w.cells[0].moisture=30;p.run_rules(self.w)
        self.assertEqual(self.w.cells[0].moisture,30)

    def test_disabled_rule_and_deletion(self):
        rule=p.add_rule(self.w,"off",[[0,0]],"moisture","above",0,"water")
        p.enable_rule(self.w,rule["id"],False);p.run_rules(self.w)
        self.assertEqual(self.w.cells[0].moisture,50)
        p.delete_rule(self.w,rule["id"])
        self.assertEqual(self.w.workbench["rules"],[])
