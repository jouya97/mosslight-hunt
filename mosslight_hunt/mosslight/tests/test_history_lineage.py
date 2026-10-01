"""Historical authoring context and shared-insertion order in real workflows."""
import tempfile
from pathlib import Path
import unittest

from mosslight.history import HistoryConflict, HistoryStore
from mosslight.model import Cell, World


def command(op, **args):
    return {"op": op, "args": args}


class HistoryLineageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.temporary.name) / "history.sqlite")
        world = World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)])
        self.main = self.store.create(world)["branch"]

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def append(self, branch, op, **args):
        return self.store.append(branch, command(op, **args))

    def test_correcting_a_past_edit_can_reference_a_later_deleted_object(self):
        self.append(self.main, "note", content="observed")
        edited = self.append(self.main, "edit_note", ident=1, content="first revision")
        event = edited["events"][-1]["id"]
        source = self.append(self.main, "delete_entry", collection="notes", ident=1)
        corrected = self.store.correct(self.main, {event: command("edit_note", ident=1, content="historical correction")})
        self.assertEqual(corrected["status"], "ready")
        self.assertEqual(corrected["world"]["workbench"]["notes"], [])
        self.assertEqual(corrected["events"][1]["command"]["args"]["content"], "historical correction")
        self.assertEqual(corrected["events"][1]["command"]["args"]["ident"], edited["events"][1]["command"]["args"]["ident"])
        self.assertTrue(self.store.verify(corrected["branch"])["matches"])
        self.assertEqual(self.store.snapshot(self.main), source)

    def test_contradictory_shared_insertions_report_order_conflict(self):
        source = self.store.fork(self.main)["branch"]
        planted = self.append(source, "tend", x=0, y=0, action="plant_moss")
        cleared = self.append(source, "tend", x=0, y=0, action="clear")
        a, b = planted["events"][0]["id"], cleared["events"][1]["id"]
        local = self.store.cherry_pick(source, self.main, [a, b])
        target = self.store.cherry_pick(source, self.main, [b])
        target = self.store.cherry_pick(source, target["branch"], [a])
        self.assertIsNone(local["world"]["cells"][0]["species"])
        self.assertEqual(target["world"]["cells"][0]["species"], "moss")
        count = self.store.db.execute("SELECT COUNT(*) FROM history_branches").fetchone()[0]
        with self.assertRaises(HistoryConflict) as error:
            self.store.rebase(local["branch"], target["branch"])
        self.assertEqual(error.exception.details["kind"], "order-conflict")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM history_branches").fetchone()[0], count)
        self.assertEqual(self.store.snapshot(local["branch"]), local)
        self.assertEqual(self.store.snapshot(target["branch"]), target)

    def test_shared_event_can_constrain_a_local_insertion_before_destination(self):
        source = self.store.fork(self.main)["branch"]
        self.append(source, "tend", x=0, y=0, action="water")
        self.append(source, "tend", x=1, y=0, action="compost")
        authored = self.append(source, "tend", x=2, y=0, action="water")
        a, b, c = [event["id"] for event in authored["events"]]
        local = self.store.cherry_pick(source, self.main, [a, b])
        target = self.store.cherry_pick(source, self.main, [b, c])
        merged = self.store.rebase(local["branch"], target["branch"])
        self.assertEqual([event["id"] for event in merged["events"]], [a, b, c])
        self.assertEqual(merged["world"], authored["world"])
        self.assertTrue(self.store.verify(merged["branch"])["matches"])

    def binding_histories(self):
        first = self.append(self.main, "note", content="unrelated")
        self.append(self.main, "note", content="target")
        initial = self.append(self.main, "edit_note", ident=2, content="same authored content")
        edit_id = initial["events"][-1]["id"]
        base = self.store.correct(self.main, {first["events"][0]["id"]: None})
        local = self.store.correct(base["branch"], {
            edit_id: command("edit_note", ident=1, content="same authored content")})
        remote = self.store.correct(base["branch"], {
            edit_id: command("edit_note", ident=1, content="new remote content")})
        return base, local, remote, edit_id

    def test_audit_binding_change_does_not_conflict_with_authored_correction(self):
        base, local, remote, _ = self.binding_histories()
        self.assertEqual(base["events"][-1]["command"], local["events"][-1]["command"])
        self.assertEqual(base["events"][-1]["bindings"], {"ident": 2})
        self.assertEqual(local["events"][-1]["bindings"], {"ident": 1})
        rebased = self.store.rebase(local["branch"], remote["branch"])
        self.assertEqual(rebased["world"]["workbench"]["notes"][0]["text"], "new remote content")
        self.assertEqual(rebased["status"], "ready")

    def test_same_authored_action_with_rebound_audit_data_is_pick_idempotent(self):
        base, local, _, edit_id = self.binding_histories()
        picked = self.store.cherry_pick(local["branch"], base["branch"], [edit_id])
        self.assertEqual(picked["world"], base["world"])
        self.assertEqual(picked["events"], base["events"])


if __name__ == "__main__":
    unittest.main()
