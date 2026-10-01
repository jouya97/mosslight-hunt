import unittest
from helpers import empty_world,plant
from mosslight.habitat import effective_shade,set_terrain,set_structure,set_shade,water_balance,after_day
from mosslight.engine import step


class HabitatTests(unittest.TestCase):
    def setUp(self): self.w=empty_world()

    def test_terrain_fixed_water(self):
        for terrain,moisture in (("pond",100),("stone",0)):
            with self.subTest(terrain=terrain):
                plant(self.w)
                set_terrain(self.w,0,0,terrain)
                self.assertIsNone(self.w.cell(0,0).species)
                self.assertEqual(self.w.cell(0,0).moisture,moisture)
                self.assertEqual(water_balance(self.w,0,50,60,18,3),moisture)

    def test_soil_sand_peat_balances(self):
        for terrain,expected in (("soil",65),("sand",60),("peat",69)):
            set_terrain(self.w,0,0,terrain)
            self.assertEqual(water_balance(self.w,0,50,50,18,3),expected)

    def test_mulch_reduces_evaporation(self):
        self.w.workbench["tiles"][0]["mulch"]=40
        self.assertEqual(water_balance(self.w,0,50,50,0,3),49)

    def test_pond_neighbor_bonus(self):
        set_terrain(self.w,1,0,"pond")
        self.assertEqual(water_balance(self.w,0,50,50,0,3),49)

    def test_barrel_collects_only_rain(self):
        set_structure(self.w,0,0,"rain_barrel")
        self.assertEqual(water_balance(self.w,0,50,50,8,3),61)
        self.assertEqual(water_balance(self.w,0,50,50,0,3),47)

    def test_shade_cloth_orthogonal_and_capped(self):
        set_structure(self.w,1,0,"shade_cloth")
        self.assertEqual(effective_shade(self.w,0),65)
        self.assertEqual(effective_shade(self.w,5),65)
        self.assertEqual(effective_shade(self.w,4),50)
        set_shade(self.w,0,0,99)
        self.assertEqual(effective_shade(self.w,0),100)

    def test_mulch_log_and_stress_updates(self):
        self.w.day=3
        tile=self.w.workbench["tiles"][0]
        tile.update(mulch=2,structure="log",stress=10)
        plant(self.w,vitality=20)
        after_day(self.w,0,0)
        self.assertEqual((tile["mulch"],tile["stress"],self.w.cells[0].nutrients),(1,15,53))
        self.w.cells[0].vitality=60
        after_day(self.w,0,0)
        self.assertEqual(tile["stress"],12)

    def test_visitor_thresholds_and_hush(self):
        for x in range(3):plant(self.w,x,0,"clover")
        for x in range(2):plant(self.w,x,1,"glowcap")
        set_structure(self.w,0,0,"bee_house")
        after_day(self.w,0,0)
        self.assertEqual(self.w.workbench["visitors"],{"bees":2,"fireflies":1,"worms":4})
        self.w.day=36;after_day(self.w,0,0)
        self.assertEqual(self.w.workbench["visitors"]["bees"],0)

    def test_history_retains_last_240_days(self):
        step(self.w,250)
        history=self.w.workbench["history"]
        self.assertEqual((len(history),history[0]["day"],history[-1]["day"]),(240,11,250))

    def test_unplantable_never_colonized(self):
        set_terrain(self.w,0,0,"pond");plant(self.w,1,0)
        step(self.w,30)
        self.assertIsNone(self.w.cells[0].species)
        self.assertEqual(self.w.cells[0].moisture,100)
