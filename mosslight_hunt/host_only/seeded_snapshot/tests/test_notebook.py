import unittest
from helpers import empty_world,plant
from mosslight import notebook as n


class NotebookTests(unittest.TestCase):
    def setUp(self):self.w=empty_world()

    def test_note_normalization_search_and_location(self):
        note=n.add_note(self.w,"  Wet roots  ",[" Pond ","POND","Dawn"],[0,0])
        self.assertEqual(note["tags"],["dawn","pond"])
        self.assertEqual(note["text"],"Wet roots")
        self.assertEqual(len(n.search_notes(self.w,"ROOT",tag="Pond")),1)
        self.assertEqual(n.search_notes(self.w,"dry"),[])

    def test_note_edit_and_delete(self):
        note=n.add_note(self.w,"old")
        n.edit_note(self.w,note["id"],"new",["test"])
        self.assertEqual(n.search_notes(self.w)[0]["text"],"new")
        n.delete_entry(self.w,"notes",note["id"])
        self.assertEqual(n.search_notes(self.w),[])
        with self.assertRaises(ValueError):n.edit_note(self.w,note["id"],"missing")

    def test_failed_note_does_not_consume_id(self):
        for args in (("",),("a",[],[99,0]),("a",["x"*33])):
            with self.assertRaises(ValueError):n.add_note(self.w,*args)
        self.assertEqual(self.w.workbench["next_id"],1)

    def test_search_returns_independent_copy(self):
        n.add_note(self.w,"roots",["wet"])
        n.search_notes(self.w)[0]["tags"].append("changed")
        self.assertEqual(self.w.workbench["notes"][0]["tags"],["wet"])

    def test_specimen_is_snapshot_not_destructive(self):
        c=plant(self.w);entry=n.press_specimen(self.w,0,0,"First moss")
        c.vitality=10
        self.assertEqual(entry["vitality"],80)
        self.assertEqual(self.w.workbench["specimens"][0]["vitality"],80)
        self.assertEqual(c.species,"moss")

    def test_tasks_sort_due_and_complete(self):
        a=n.add_task(self.w,"later",4)
        b=n.add_task(self.w,"now",0)
        self.assertEqual([t["text"] for t in n.task_list(self.w)],["now","later"])
        self.assertEqual([t["id"] for t in n.task_list(self.w,"due")],[b["id"]])
        self.assertEqual(n.task_list(self.w,"overdue"),[])
        n.complete_task(self.w,b["id"])
        self.assertEqual([t["id"] for t in n.task_list(self.w)],[a["id"]])
        n.complete_task(self.w,b["id"],False)
        self.w.day=1
        self.assertEqual(len(n.task_list(self.w,"overdue")),1)

    def test_identifier_sequence_across_collections(self):
        a=n.add_note(self.w,"one");b=n.add_task(self.w,"two",2)
        plant(self.w);c=n.press_specimen(self.w,0,0)
        self.assertEqual([a["id"],b["id"],c["id"]],[1,2,3])

    def test_title_trim_and_limits(self):
        n.rename_garden(self.w,"  Fern hollow  ")
        self.assertEqual(self.w.workbench["title"],"Fern hollow")
        with self.assertRaises(ValueError):n.rename_garden(self.w,"x"*101)
