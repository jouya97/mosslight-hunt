import copy
import unittest
from helpers import empty_world,plant
from mosslight import analysis as a
from mosslight.habitat import set_terrain


class AnalysisTests(unittest.TestCase):
    def setUp(self):self.w=empty_world()

    def test_census_empty_and_living_denominators(self):
        self.assertEqual(a.census(self.w)["averages"]["vitality"],0)
        plant(self.w,vitality=80);plant(self.w,1,0,"fern",vitality=40)
        result=a.census(self.w)
        self.assertEqual((result["occupied"],result["coverage"],result["richness"]),(2,12.5,2))
        self.assertEqual(result["averages"]["vitality"],60)
        self.assertEqual(result["diversity"],0.6931)
        self.assertEqual(a.census(self.w,[[0,0]])["coverage"],100)

    def test_suitability_exact_and_unplantable(self):
        self.w.cells[0].moisture=65;self.w.cells[0].shade=67
        self.assertEqual(a.suitability(self.w,0,0,"moss")["score"],100)
        self.w.cells[0].nutrients=10
        self.assertEqual(a.suitability(self.w,0,0,"moss")["score"],80)
        set_terrain(self.w,0,0,"stone")
        self.assertEqual(a.suitability(self.w,0,0,"moss")["score"],0)

    def test_recommendation_tie_order_and_empty_filter(self):
        plant(self.w,0,0)
        result=a.recommendations(self.w,"moss",2)
        self.assertEqual([(r["x"],r["y"]) for r in result],[(1,0),(2,0)])
        self.assertEqual(a.recommendations(self.w,"moss",1,False)[0]["x"],0)

    def test_patches_orthogonal_perimeter_bounds(self):
        plant(self.w,0,0);plant(self.w,1,0,"fern");plant(self.w,3,3)
        result=a.patches(self.w)
        self.assertEqual([p["size"] for p in result],[2,1])
        self.assertEqual(result[0]["perimeter"],6)
        self.assertEqual(result[0]["bounds"],[0,0,1,0])
        self.assertEqual(len(a.patches(self.w,"moss")),2)

    def test_transect_endpoint_and_reverse_order(self):
        self.assertEqual([(r["x"],r["y"]) for r in a.transect(self.w,0,0,3,3)],[(0,0),(1,1),(2,2),(3,3)])
        self.assertEqual([(r["x"],r["y"]) for r in a.transect(self.w,2,0,0,0)],[(2,0),(1,0),(0,0)])
        self.assertEqual(len(a.transect(self.w,1,1,1,1)),1)

    def test_forecast_samples_final_day_and_preserves_source(self):
        before=copy.deepcopy(self.w.to_dict())
        result=a.forecast(self.w,5,2)
        self.assertEqual([r["day"] for r in result["timeline"]],[0,2,4,5])
        self.assertEqual(result["world"]["day"],5)
        self.assertEqual(self.w.to_dict(),before)

    def test_comparison_changed_cells_and_population(self):
        other=copy.deepcopy(self.w);plant(other)
        result=a.compare(self.w,other)
        self.assertEqual(result["changed_tiles"],1)
        self.assertEqual(result["population_delta"]["moss"],1)
        self.assertEqual(result["coverage_delta"],6.25)
        self.assertIn("species",result["changes"][0]["fields"])

    def test_alerts_and_report(self):
        c=plant(self.w,vitality=10);c.moisture=5;c.nutrients=0
        self.assertEqual(a.alerts(self.w)[0]["issues"],["low vitality","dry soil","hungry soil"])
        self.assertEqual(a.report(self.w)["census"]["endangered"],1)
