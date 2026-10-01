import copy
import unittest
from helpers import empty_world
from mosslight.model import World,load
from mosslight.commands import execute,command_catalog
from mosslight.notebook import add_note
from pathlib import Path


class StateCommandTests(unittest.TestCase):
    def test_v1_example_migrates_with_zeroed_extensions(self):
        world=load(Path(__file__).parents[1]/"examples/first-garden.json")
        self.assertEqual(world.day,24)
        self.assertEqual(world.to_dict()["version"],2)
        self.assertEqual(world.workbench["inventory"]["fiber"],0)
        self.assertTrue(all(t["terrain"]=="soil" for t in world.workbench["tiles"]))

    def test_bad_save_values(self):
        for field,value in (("title",""),("next_id",False),("tiles",[]),("inventory",{}),("mystery",1)):
            data=empty_world().to_dict();data["workbench"][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):World.from_dict(data)

    def test_duplicate_ids_invalid_reference_and_future_entry(self):
        w=empty_world();add_note(w,"one")
        for mutation in (lambda d:d["workbench"]["notes"].append(copy.deepcopy(d["workbench"]["notes"][0])),
                         lambda d:d["workbench"]["notes"][0].update(tile=[40,40]),
                         lambda d:d["workbench"]["notes"][0].update(day=1)):
            data=copy.deepcopy(w.to_dict());mutation(data)
            with self.assertRaises(ValueError):World.from_dict(data)

    def test_roundtrip_is_independent(self):
        w=empty_world();add_note(w,"one",["tag"])
        data=w.to_dict();restored=World.from_dict(data)
        restored.workbench["notes"][0]["tags"].append("new")
        self.assertEqual(w.workbench["notes"][0]["tags"],["tag"])

    def test_command_revises_once_for_multiple_days(self):
        w=empty_world();execute(w,{"op":"grow","args":{"days":7}})
        self.assertEqual((w.day,w.revision),(7,1))

    def test_bad_commands_leave_source_unchanged(self):
        w=empty_world();before=copy.deepcopy(w.to_dict())
        for command in (None,{}, {"op":"dragon"},{"op":"grow","args":{"days":True}},
                        {"op":"terrain","args":{"x":0,"y":0,"terrain":"mars"}},
                        {"op":"note","args":{"content":"ok","surprise":1}}):
            with self.subTest(command=command),self.assertRaises(ValueError):execute(w,command)
            self.assertEqual(w.to_dict(),before)

    def test_catalog_has_required_and_optional_arguments(self):
        catalog=command_catalog()
        self.assertTrue(catalog["tend"]["x"]["required"])
        self.assertFalse(catalog["grow"]["days"]["required"])
        self.assertEqual(catalog["grow"]["days"]["default"],1)
        self.assertEqual(len(catalog),34)

    def test_save_dictionary_has_no_mutable_aliases(self):
        w=empty_world();add_note(w,"one",["tag"])
        data=w.to_dict()
        data["workbench"]["notes"][0]["tags"].append("new")
        data["journal"][0]["text"]="changed"
        self.assertEqual(w.workbench["notes"][0]["tags"],["tag"])
        self.assertNotEqual(w.journal[0]["text"],"changed")

    def test_import_rejects_inconsistent_pending_plan(self):
        from mosslight.planning import schedule
        w=empty_world();schedule(w,"Water",1,[[0,0]],"water")
        data=w.to_dict();data["workbench"]["plans"][0]["remaining"]=0
        with self.assertRaises(ValueError):World.from_dict(data)

    def test_import_rejects_duplicate_rule_tiles(self):
        from mosslight.planning import add_rule
        w=empty_world();add_rule(w,"Water",[[0,0]],"moisture","below",30,"water")
        data=w.to_dict();data["workbench"]["rules"][0]["tiles"].append([0,0])
        with self.assertRaises(ValueError):World.from_dict(data)
