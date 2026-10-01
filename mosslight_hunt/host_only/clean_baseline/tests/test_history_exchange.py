"""Public offline workflows: parcels, causal heads and crisscross histories."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mosslight.history import HistoryConflict, _digest
from mosslight.history_exchange import HistoryExchange
from mosslight.model import Cell, World


def command(op, **args):
    return {"op": op, "args": args}


class HistoryExchangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.devices = [HistoryExchange(Path(self.temp.name) / (name + ".sqlite")) for name in ("desk", "field", "archive")]
        self.desk, self.field, self.archive = self.devices
        world = World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)])
        initial = self.desk.history.create(world)
        branch = initial["branch"]
        self.desk.history.append(branch, command("note", content="A0"))
        current = self.desk.history.append(branch, command("note", content="B0"))
        self.a, self.b = [event["id"] for event in current["events"]]
        self.announced = self.desk.announce(branch, author="desk", name="pond")
        self.channel, self.genesis = self.announced["channel"], self.announced["publication"]
        self.field.receive(self.desk.export(self.channel))

    def tearDown(self):
        for device in self.devices:
            device.close()
        self.temp.cleanup()

    def change(self, device, publication, event, text, author):
        checkout = device.checkout(publication)
        corrected = device.history.correct(checkout["branch"], {event: command("note", content=text)})
        return device.publish(corrected["branch"], checkout=checkout["branch"], author=author)

    def contents(self, device, publication):
        checked = device.checkout(publication)
        return [note["text"] for note in checked["world"]["workbench"]["notes"]]

    def crisscross(self):
        left = self.change(self.desk, self.genesis, self.a, "A1", "desk")
        right = self.change(self.field, self.genesis, self.b, "B1", "field")
        left_parcel = self.desk.export(self.channel)
        right_parcel = self.field.export(self.channel)
        self.desk.receive(right_parcel)
        self.field.receive(left_parcel)
        first = self.desk.reconcile(left["publication"], right["publication"], author="desk")
        second = self.field.reconcile(left["publication"], right["publication"], author="field")
        self.assertNotEqual(first["publication"], second["publication"])
        self.assertEqual(first["revision"], second["revision"])
        return left, right, first, second

    def test_round_trip_duplicate_and_delayed_parcels(self):
        old = self.desk.export(self.channel)
        newer = self.change(self.desk, self.genesis, self.a, "A1", "desk")
        parcel = self.desk.export(self.channel)
        received = self.archive.receive(parcel)
        self.assertEqual(received["heads"], [newer["publication"]])
        self.assertEqual(self.archive.receive(parcel)["heads"], received["heads"])
        self.assertEqual(self.archive.receive(old)["heads"], received["heads"])
        self.assertEqual(self.contents(self.archive, newer["publication"]), ["A1", "B0"])

    def test_concurrent_receive_preserves_local_history_and_both_heads(self):
        local = self.change(self.desk, self.genesis, self.a, "A1", "desk")
        remote = self.change(self.field, self.genesis, self.b, "B1", "field")
        before = self.desk.history.snapshot(local["branch"])
        self.desk.receive(self.field.export(self.channel))
        self.assertEqual(set(self.desk.heads(self.channel)), {local["publication"], remote["publication"]})
        self.assertEqual(self.desk.history.snapshot(local["branch"]), before)
        merged = self.desk.reconcile(local["publication"], remote["publication"], author="desk")
        self.assertEqual(self.contents(self.desk, merged["publication"]), ["A1", "B1"])

    def test_multiple_common_ancestors_preserve_both_observed_reverts(self):
        _, _, first, second = self.crisscross()
        left = self.change(self.desk, first["publication"], self.a, "A0", "desk")
        right = self.change(self.field, second["publication"], self.b, "B0", "field")
        self.archive.receive(self.field.export(self.channel))
        self.archive.receive(self.desk.export(self.channel))
        merged = self.archive.reconcile(left["publication"], right["publication"], author="archive")
        self.assertEqual(self.contents(self.archive, merged["publication"]), ["A0", "B0"])
        self.assertEqual(self.archive.heads(self.channel), [merged["publication"]])

    def test_crisscross_reconciliation_keeps_new_independent_edits(self):
        _, _, first, second = self.crisscross()
        left_checkout = self.desk.checkout(first["publication"])
        left = self.desk.history.correct(left_checkout["branch"], {self.a: command("note", content="A0")})
        self.desk.history.append(left["branch"], command("task", content="desk task", due=4))
        left = self.desk.publish(left["branch"], checkout=left_checkout["branch"], author="desk")
        right_checkout = self.field.checkout(second["publication"])
        right = self.field.history.correct(right_checkout["branch"], {self.b: command("note", content="B0")})
        self.field.history.append(right["branch"], command("note", content="new field observation"))
        right = self.field.publish(right["branch"], checkout=right_checkout["branch"], author="field")
        self.desk.receive(self.field.export(self.channel))
        result = self.desk.reconcile(left["publication"], right["publication"], author="desk")
        snapshot = self.desk.history.snapshot(result["branch"])
        self.assertEqual([n["text"] for n in snapshot["world"]["workbench"]["notes"]], ["A0", "B0", "new field observation"])
        self.assertEqual(snapshot["world"]["workbench"]["tasks"][0]["text"], "desk task")

    def test_incompatible_edits_preserved_until_explicit_resolution(self):
        left = self.change(self.desk, self.genesis, self.a, "desk wording", "desk")
        right = self.change(self.field, self.genesis, self.a, "field wording", "field")
        self.desk.receive(self.field.export(self.channel))
        before = self.desk.heads(self.channel)
        with self.assertRaises(HistoryConflict):
            self.desk.reconcile(left["publication"], right["publication"], author="desk")
        self.assertEqual(self.desk.heads(self.channel), before)
        chosen = self.desk.checkout(right["publication"])
        resolution = self.desk.resolve(self.channel, chosen["branch"], author="desk")
        self.assertEqual(self.desk.heads(self.channel), [resolution["publication"]])
        self.assertEqual(self.contents(self.desk, resolution["publication"]), ["field wording", "B0"])

    def test_delivery_order_gives_the_same_graph_frontier(self):
        left = self.change(self.desk, self.genesis, self.a, "A1", "desk")
        right = self.change(self.field, self.genesis, self.b, "B1", "field")
        a, b = self.desk.export(self.channel), self.field.export(self.channel)
        self.archive.receive(a)
        self.archive.receive(b)
        self.desk.receive(b)
        self.field.receive(a)
        expected = sorted([left["publication"], right["publication"]])
        self.assertEqual(self.archive.heads(self.channel), expected)
        self.assertEqual(self.desk.heads(self.channel), expected)
        self.assertEqual(self.field.heads(self.channel), expected)

    def test_missing_ancestor_and_modified_world_are_atomic_rejections(self):
        head = self.change(self.desk, self.genesis, self.a, "A1", "desk")
        parcel = self.desk.export(self.channel)
        broken = copy.deepcopy(parcel)
        del broken["body"]["publications"][self.genesis]
        broken["checksum"] = _digest(broken["body"])
        with self.assertRaises(ValueError):
            self.archive.receive(broken)
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM exchange_channels").fetchone()[0], 0)
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM history_roots").fetchone()[0], 0)
        altered = copy.deepcopy(parcel)
        revision = altered["body"]["publications"][head["publication"]]["revision"]
        altered["body"]["revisions"][revision]["result"]["world"]["cells"][0]["moisture"] = 99
        altered["checksum"] = _digest(altered["body"])
        with self.assertRaises(ValueError):
            self.archive.receive(altered)
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM history_roots").fetchone()[0], 0)

    def test_selected_parcel_contains_complete_ancestry_on_fresh_installation(self):
        _, _, first, _ = self.crisscross()
        parcel = self.desk.export(self.channel, heads=[first["publication"]])
        self.archive.receive(json.loads(json.dumps(parcel)))
        self.assertEqual(self.archive.heads(self.channel), [first["publication"]])
        self.assertEqual(self.contents(self.archive, first["publication"]), ["A1", "B1"])

    def test_checkout_and_republish_preserve_logical_entity_identity(self):
        checked = self.field.checkout(self.genesis)
        created = self.field.history.append(checked["branch"], command("task", content="water fern", due=4))
        completed = self.field.history.append(checked["branch"], command("complete_task", ident=3))
        published = self.field.publish(checked["branch"], checkout=checked["branch"], author="field")
        self.desk.receive(self.field.export(self.channel))
        local = self.desk.checkout(published["publication"])
        self.assertEqual(local["events"][-1]["command"], completed["events"][-1]["command"])
        self.assertTrue(local["world"]["workbench"]["tasks"][0]["done"])
        self.assertIn(created["events"][-1]["id"], local["events"][-1]["command"]["args"]["ident"]["$ref"])

    def test_sequential_publications_advance_the_checkout_receipt(self):
        checked = self.field.checkout(self.genesis)
        self.field.history.append(checked["branch"], command("note", content="first field note"))
        first = self.field.publish(checked["branch"], checkout=checked["branch"], author="field")
        self.field.history.append(checked["branch"], command("note", content="second field note"))
        second = self.field.publish(checked["branch"], checkout=checked["branch"], author="field")
        self.assertEqual(self.field._publication(second["publication"])["parents"], [first["publication"]])
        self.assertEqual(self.field.heads(self.channel), [second["publication"]])

    def test_conflicting_common_histories_report_ambiguous_ancestry(self):
        left = self.change(self.desk, self.genesis, self.a, "desk wording", "desk")
        right = self.change(self.field, self.genesis, self.a, "field wording", "field")
        left_parcel, right_parcel = self.desk.export(self.channel), self.field.export(self.channel)
        self.desk.receive(right_parcel)
        self.field.receive(left_parcel)
        first = self.desk.resolve(self.channel, left["branch"], author="desk")
        second = self.field.resolve(self.channel, right["branch"], author="field")
        self.desk.receive(self.field.export(self.channel))
        with self.assertRaises(HistoryConflict) as error:
            self.desk.reconcile(first["publication"], second["publication"], author="desk")
        self.assertEqual(error.exception.details["kind"], "ambiguous-ancestry")
        self.assertEqual(set(self.desk.heads(self.channel)), {first["publication"], second["publication"]})

    def test_resolution_rejects_a_head_set_changed_during_computation(self):
        checked = self.desk.checkout(self.genesis)
        remote = self.change(self.field, self.genesis, self.b, "B1", "field")
        parcel = self.field.export(self.channel)
        other = HistoryExchange(Path(self.temp.name) / "desk.sqlite")
        original = self.desk._checked_revision
        def concurrent_receive(branch):
            result = original(branch)
            other.receive(parcel)
            return result
        try:
            with patch.object(self.desk, "_checked_revision", side_effect=concurrent_receive):
                with self.assertRaises(HistoryConflict) as error:
                    self.desk.resolve(self.channel, checked["branch"], author="desk")
            self.assertEqual(error.exception.details["kind"], "stale-resolution")
            self.assertEqual(self.desk.heads(self.channel), [remote["publication"]])
        finally:
            other.close()

    def test_process_exit_during_receive_leaves_no_partial_ledger(self):
        self.change(self.desk, self.genesis, self.a, "A1", "desk")
        parcel_path = Path(self.temp.name) / "parcel.json"
        parcel_path.write_text(json.dumps(self.desk.export(self.channel)))
        database = Path(self.temp.name) / "interrupted.sqlite"
        script = """import json, os, sys
from pathlib import Path
from mosslight.history_exchange import HistoryExchange
exchange=HistoryExchange(sys.argv[1])
original=exchange._put_publication
def crash(ident, node):
    original(ident, node)
    os._exit(29)
exchange._put_publication=crash
exchange.receive(json.loads(Path(sys.argv[2]).read_text()))
"""
        child = subprocess.run([sys.executable, "-B", "-c", script, str(database), str(parcel_path)], capture_output=True, text=True)
        self.assertEqual(child.returncode, 29, child.stderr)
        recovered = HistoryExchange(database)
        try:
            self.assertEqual(recovered.db.execute("SELECT COUNT(*) FROM history_roots").fetchone()[0], 0)
            self.assertEqual(recovered.db.execute("SELECT COUNT(*) FROM exchange_publications").fetchone()[0], 0)
            result = recovered.receive(json.loads(parcel_path.read_text()))
            self.assertEqual(result["heads"], self.desk.heads(self.channel))
        finally:
            recovered.close()


if __name__ == "__main__":
    unittest.main()
