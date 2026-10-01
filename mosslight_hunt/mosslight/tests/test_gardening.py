import copy
import unittest
from helpers import empty_world,plant
from mosslight import gardening as g
from mosslight.habitat import set_terrain


class GardeningTests(unittest.TestCase):
    def setUp(self):self.w=empty_world()

    def test_rectangle_normalizes_and_includes_edges(self):
        self.assertEqual(g.rectangle(self.w,2,1,0,0),[(0,0),(1,0),(2,0),(0,1),(1,1),(2,1)])

    def test_brush_shapes_clip_at_edges(self):
        self.assertEqual(g.brush(self.w,0,0,1),[(0,0),(1,0),(0,1)])
        self.assertEqual(len(g.brush(self.w,1,1,1,"square")),9)
        self.assertEqual(len(g.brush(self.w,1,1,1,"circle")),5)
        self.assertEqual(g.brush(self.w,2,2,0),[(2,2)])

    def test_batch_deduplicates_and_revises_once(self):
        self.assertEqual(g.tend_many(self.w,[[0,0],[0,0],[1,0]],"water"),2)
        self.assertEqual([c.moisture for c in self.w.cells[:3]],[82,82,50])
        self.assertEqual(self.w.revision,1)

    def test_batch_failure_rolls_back_earlier_tiles(self):
        set_terrain(self.w,1,0,"pond")
        before=copy.deepcopy(self.w.to_dict())
        with self.assertRaises(ValueError):g.tend_many(self.w,[[0,0],[1,0]],"plant_moss")
        self.assertEqual(self.w.to_dict(),before)

    def test_transplant_moves_only_plant_and_stress(self):
        plant(self.w,age=12,vitality=75)
        self.w.workbench["tiles"][0]["stress"]=18
        self.w.cell(1,0).moisture=10
        g.transplant(self.w,0,0,1,0)
        c=self.w.cell(1,0)
        self.assertEqual((c.species,c.age,c.vitality,c.moisture),("moss",12,65,10))
        self.assertIsNone(self.w.cells[0].species)
        self.assertEqual(self.w.workbench["tiles"][1]["stress"],18)
        self.assertEqual(self.w.workbench["tiles"][0]["stress"],0)

    def test_transplant_validation(self):
        plant(self.w)
        for point in ((0,0),(-1,0)):
            with self.assertRaises(ValueError):g.transplant(self.w,0,0,*point)
        plant(self.w,1,0)
        with self.assertRaises(ValueError):g.transplant(self.w,0,0,1,0)

    def test_prune_bounds(self):
        c=plant(self.w,age=2,vitality=98);g.prune(self.w,0,0)
        self.assertEqual((c.age,c.vitality),(0,100))
        with self.assertRaises(ValueError):g.prune(self.w,1,0)

    def test_harvest_yields_and_resets_maturity(self):
        for species,age,resource,expected in (("moss",8,"fiber",3),("fern",12,"fiber",4),("clover",6,"nectar",3),("glowcap",10,"spores",3)):
            with self.subTest(species=species):
                w=empty_world();c=plant(w,species=species,age=age)
                self.assertEqual(g.harvest(w,0,0),{resource:expected})
                self.assertEqual((c.age,c.vitality),(0,65))
                with self.assertRaises(ValueError):g.harvest(w,0,0)

    def test_seed_collection_and_sowing(self):
        c=plant(self.w,age=5,vitality=50)
        self.assertEqual(g.collect_seed(self.w,0,0),"moss")
        self.assertEqual((c.age,c.vitality),(0,45))
        g.sow(self.w,1,0,"moss")
        self.assertEqual(self.w.cell(1,0).species,"moss")
        self.assertEqual(self.w.workbench["seeds"]["moss"],0)
        with self.assertRaises(ValueError):g.sow(self.w,2,0,"moss")

    def test_recipes_and_atomic_shortage(self):
        inventory=self.w.workbench["inventory"]
        inventory.update(fiber=10,nectar=2,spores=1)
        self.assertEqual(g.craft(self.w,"compost",2),{"compost":4})
        self.assertEqual(inventory["fiber"],4)
        g.craft(self.w,"mulch");g.craft(self.w,"tonic")
        self.assertEqual((inventory["mulch"],inventory["tonic"],inventory["nectar"]),(3,1,0))
        before=inventory.copy()
        with self.assertRaises(ValueError):g.craft(self.w,"tonic")
        self.assertEqual(inventory,before)

    def test_material_application(self):
        self.w.workbench["inventory"].update(compost=1,mulch=1,tonic=1)
        c=plant(self.w,vitality=90)
        g.apply_material(self.w,0,0,"compost")
        g.apply_material(self.w,0,0,"mulch")
        g.apply_material(self.w,0,0,"tonic")
        self.assertEqual((c.nutrients,c.vitality,self.w.workbench["tiles"][0]["mulch"]),(90,100,30))
        self.assertEqual(self.w.workbench["inventory"]["tonic"],0)
