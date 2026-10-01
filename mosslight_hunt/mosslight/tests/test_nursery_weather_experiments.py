import copy
import unittest
from helpers import empty_world,plant
from mosslight import nursery as n
from mosslight.engine import step
from mosslight.experiments import experiment,rank_experiment
from mosslight.weather import calendar_day,weather_on,almanac,calendar,next_weather
from mosslight.planning import schedule
from mosslight.notebook import add_task


class NurseryTests(unittest.TestCase):
    def setUp(self):self.w=empty_world()

    def test_cutting_cost_and_initial_batch(self):
        cell=plant(self.w);batch=n.take_cutting(self.w,0,0)
        self.assertEqual(cell.vitality,68)
        self.assertEqual((batch["hydration"],batch["vitality"],batch["count"]),(3,60,1))

    def test_seeds_are_consumed_only_on_success(self):
        self.w.workbench["seeds"]["moss"]=2
        with self.assertRaises(ValueError):n.start_seeds(self.w,"moss",3)
        self.assertEqual(self.w.workbench["seeds"]["moss"],2)
        n.start_seeds(self.w,"moss",2)
        self.assertEqual(self.w.workbench["seeds"]["moss"],0)

    def test_maturity_water_and_planting(self):
        self.w.workbench["seeds"]["clover"]=2
        batch=n.start_seeds(self.w,"clover",2)
        step(self.w,2)
        state=self.w.workbench["nursery"][0]
        self.assertEqual((state["status"],state["vitality"],state["hydration"]),("ready",66,1))
        n.plant_out(self.w,batch["id"],0,0)
        self.assertEqual((self.w.cells[0].species,self.w.cells[0].vitality),("clover",66))
        self.assertEqual(state["count"],1)
        n.plant_out(self.w,batch["id"],1,0)
        self.assertEqual(state["status"],"planted")

    def test_drying_stops_age_then_fails(self):
        plant(self.w,species="fern");n.take_cutting(self.w,0,0)
        step(self.w,4)
        batch=self.w.workbench["nursery"][0]
        self.assertEqual((batch["age"],batch["vitality"],batch["status"]),(3,49,"growing"))
        step(self.w,3)
        self.assertEqual(batch["status"],"failed")
        with self.assertRaises(ValueError):n.water_batch(self.w,batch["id"])

    def test_water_restores_three_days_and_report(self):
        plant(self.w,species="fern");batch=n.take_cutting(self.w,0,0)
        step(self.w,3)
        self.assertTrue(n.nursery_report(self.w)[0]["needs_water"])
        n.water_batch(self.w,batch["id"]);step(self.w)
        self.assertEqual(n.nursery_report(self.w)[0]["days_to_ready"],0)
        self.assertEqual(self.w.workbench["nursery"][0]["status"],"ready")

    def test_discard_closes_batch(self):
        plant(self.w);batch=n.take_cutting(self.w,0,0);n.discard_batch(self.w,batch["id"])
        self.assertEqual(self.w.workbench["nursery"][0]["count"],0)
        with self.assertRaises(ValueError):n.discard_batch(self.w,batch["id"])


class WeatherExperimentTests(unittest.TestCase):
    def test_calendar_boundaries(self):
        self.assertEqual(calendar_day(0)["season_day"],1)
        self.assertEqual(calendar_day(11)["days_until_season"],1)
        self.assertEqual(calendar_day(12)["season"],"Highsummer")
        self.assertEqual((calendar_day(48)["year"],calendar_day(48)["year_day"]),(2,1))

    def test_fixed_seed_weather_sequence(self):
        self.assertEqual([weather_on(7,day)["weather"] for day in range(1,13)],
                         ["rain","clear","rain","clear","clear","rain","rain","rain","clear","clear","clear","clear"])

    def test_almanac_matches_daily_weather(self):
        w=empty_world();prediction=almanac(w,8)
        for expected in prediction["days"]:
            step(w)
            self.assertEqual(w.weather,expected["weather"])
        self.assertEqual(sum(prediction["weather_days"].values()),8)
        self.assertEqual(prediction["total_rainfall"],sum(p["rainfall"] for p in prediction["days"]))

    def test_calendar_expands_finite_repeats_and_open_tasks(self):
        w=empty_world();schedule(w,"water",1,[[0,0]],"water",2,3);add_task(w,"observe",2)
        days=calendar(w,7)
        self.assertEqual([d["day"] for d in days if d["plans"]],[1,3,5])
        self.assertEqual(days[2]["tasks"][0]["text"],"observe")

    def test_next_weather_first_match(self):
        w=empty_world();entry=next_weather(w,"clear",48)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["weather"],"clear")
        self.assertTrue(all(weather_on(w.seed,d)["weather"]!="clear" for d in range(1,entry["day"])))

    def test_experiment_controls_and_expected_initial_treatment(self):
        w=empty_world();before=copy.deepcopy(w.to_dict())
        result=experiment(w,2,[{"name":"Plant","events":[{"offset":0,"command":{"op":"tend","args":{"x":0,"y":0,"action":"plant_moss"}}}]}],2)
        self.assertEqual(result["branches"][0]["samples"][0]["occupied"],0)
        self.assertEqual(result["branches"][1]["samples"][0]["occupied"],1)
        self.assertEqual(w.to_dict(),before)
        self.assertEqual(rank_experiment(result)[0]["name"],"Plant")

    def test_experiment_rejects_time_advancement_and_duplicate_names(self):
        w=empty_world()
        for treatments in ([{"name":"control"}], [{"name":"one","events":[{"offset":0,"command":{"op":"grow"}}]}]):
            with self.assertRaises(ValueError):experiment(w,2,treatments)

    def test_final_day_event_runs_before_ecology(self):
        w=empty_world()
        result=experiment(w,2,[{"name":"Late","events":[{"offset":2,"command":{"op":"tend","args":{"x":0,"y":0,"action":"plant_moss"}}}]}])
        self.assertEqual([s["occupied"] for s in result["branches"][1]["samples"]],[0,0,1])
        self.assertEqual(result["branches"][1]["final"]["oldest"],1)
