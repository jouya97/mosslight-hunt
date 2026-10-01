import copy
import unittest

from mosslight import act, create, step, summary
from mosslight.engine import neighbors, season
from mosslight.model import World


class WorldTests(unittest.TestCase):
    def test_same_seed_same_world_and_future(self):
        a, b = create(123), create(123)
        self.assertEqual(a.to_dict(), b.to_dict())
        step(a, 41)
        step(b, 41)
        self.assertEqual(a.to_dict(), b.to_dict())
        self.assertNotEqual(create(124).to_dict(), b.to_dict())

    def test_seasons_and_day_count(self):
        world = create(8)
        step(world, 12)
        self.assertEqual(world.day, 12)
        self.assertEqual(season(world.day), "Highsummer")
        self.assertTrue(any("Highsummer" in e["text"] for e in world.journal))
        self.assertEqual(world.revision, 12)

    def test_interventions_are_local_and_bounded(self):
        world = create(3)
        before = copy.deepcopy(world.to_dict())
        target = world.cell(0, 0)
        act(world, 0, 0, "water")
        self.assertEqual(target.moisture, min(100, before["cells"][0]["moisture"] + 32))
        self.assertEqual(world.cells[1].to_dict(), before["cells"][1])
        act(world, 0, 0, "plant_glowcap")
        self.assertEqual(target.species, "glowcap")
        act(world, 0, 0, "clear")
        self.assertIsNone(target.species)
        self.assertEqual((target.age, target.vitality), (0, 0))
        self.assertEqual(world.revision, 3)

    def test_wet_weather_and_ecology_stay_bounded(self):
        world = create(92, 9, 7)
        step(world, 200)
        self.assertEqual(len(world.cells), 63)
        for cell in world.cells:
            self.assertTrue(0 <= cell.moisture <= 100)
            self.assertTrue(0 <= cell.nutrients <= 100)
            self.assertTrue(0 <= cell.vitality <= 100)
        self.assertLessEqual(len(world.journal), 100)
        self.assertEqual(sum(summary(world)["population"].values()), summary(world)["occupied"])

    def test_neighbors_and_bad_inputs(self):
        world = create(1, 4, 4)
        self.assertEqual(set(neighbors(world, 0, 0)), {(1, 0), (0, 1)})
        for args in [(True, 4, 4), (1, 3, 4), (1, 4, 31)]:
            with self.assertRaises(ValueError): create(*args)
        for days in (0, 366, 2.5, True):
            with self.assertRaises(ValueError): step(world, days)
        for x, y, action in [(-1, 0, "water"), (0, 4, "water"), (0, 0, "ignite")]:
            with self.assertRaises(ValueError): act(world, x, y, action)

    def test_save_validation_rejects_bad_shape_and_species(self):
        data = create(2).to_dict()
        self.assertEqual(World.from_dict(data).to_dict(), data)
        broken = copy.deepcopy(data)
        broken["cells"].pop()
        with self.assertRaises(ValueError): World.from_dict(broken)
        broken = copy.deepcopy(data)
        broken["cells"][0]["species"] = "dragon"
        with self.assertRaises(ValueError): World.from_dict(broken)
        broken = copy.deepcopy(data)
        broken["cells"][0] = "soil"
        with self.assertRaises(ValueError): World.from_dict(broken)
