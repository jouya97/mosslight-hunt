"""Observable history workflows, including conflicting and concurrent branches."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mosslight.commands import execute
from mosslight.history import HistoryConflict, HistoryStore
from mosslight.model import Cell, World


def command(op, **args):
    return {"op": op, "args": args}


def garden():
    return World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)])


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "history.sqlite"
        self.store = HistoryStore(self.path)
        self.main = self.store.create(garden())["branch"]

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def append(self, branch, op, **args):
        return self.store.append(branch, command(op, **args))

    def populated(self):
        first = self.append(self.main, "note", content="unrelated")
        self.append(self.main, "note", content="target")
        self.append(self.main, "note", content="bystander")
        final = self.append(self.main, "edit_note", ident=2, content="correct target")
        return first["events"][0]["id"], final

    def test_correction_resolves_logical_reference_after_reallocation(self):
        first, original = self.populated()
        corrected = self.store.correct(self.main, {first: None})
        self.assertEqual(corrected["status"], "ready")
        self.assertEqual([(n["id"], n["text"]) for n in corrected["world"]["workbench"]["notes"]],
                         [(1, "correct target"), (2, "bystander")])
        self.assertIn("$ref", original["events"][-1]["command"]["args"]["ident"])
        self.assertEqual(self.store.snapshot(self.main), original)
        self.assertTrue(self.store.verify(corrected["branch"])["matches"])
        self.store.close()
        self.store = HistoryStore(self.path)
        self.assertEqual(self.store.snapshot(corrected["branch"]), corrected)

    def test_missing_reference_is_conflict_even_when_old_number_is_reused(self):
        _, original = self.populated()
        target = original["events"][1]["id"]
        corrected = self.store.correct(self.main, {target: None})
        self.assertEqual(corrected["status"], "conflicted")
        self.assertEqual(corrected["conflicts"][0]["kind"], "missing-reference")
        self.assertEqual(corrected["conflicts"][0]["event"], original["events"][-1]["id"])
        self.assertEqual([n["text"] for n in corrected["world"]["workbench"]["notes"]], ["unrelated", "bystander"])
        with self.assertRaises(HistoryConflict):
            self.append(corrected["branch"], "rename", title="unreachable edit")
        repaired = self.store.correct(corrected["branch"], {original["events"][-1]["id"]: None})
        self.assertEqual(repaired["status"], "ready")
        self.assertEqual(self.store.snapshot(self.main), original)

    def test_changing_creator_type_cannot_retarget_reference(self):
        original = self.append(self.main, "note", content="observation")
        self.append(self.main, "edit_note", ident=1, content="edited")
        corrected = self.store.correct(self.main, {
            original["events"][0]["id"]: command("task", content="reminder", due=5)})
        self.assertEqual(corrected["conflicts"][0]["kind"], "missing-reference")

    def test_imported_entities_and_typed_reference_validation(self):
        world = garden()
        execute(world, command("task", content="old reminder", due=3))
        branch = self.store.create(world)["branch"]
        completed = self.append(branch, "complete_task", ident=1)
        ref = completed["events"][-1]["command"]["args"]["ident"]
        self.assertTrue(ref["$ref"].startswith("root:"))
        with self.assertRaises(HistoryConflict) as error:
            self.append(branch, "edit_note", ident=ref, content="wrong type")
        self.assertEqual(error.exception.details["kind"], "reference-type")
        self.assertTrue(self.store.snapshot(branch)["world"]["workbench"]["tasks"][0]["done"])

    def test_nursery_reference_survives_history_correction(self):
        world = garden()
        world.cells[0] = Cell(60, 60, 60, "fern", 10, 80)
        branch = self.store.create(world)["branch"]
        first = self.append(branch, "task", content="remove this", due=9)
        self.append(branch, "cutting", x=0, y=0)
        self.append(branch, "grow", days=1)
        self.append(branch, "nursery_water", ident=2)
        corrected = self.store.correct(branch, {first["events"][0]["id"]: None})
        self.assertEqual(corrected["status"], "ready")
        batch = corrected["world"]["workbench"]["nursery"][0]
        self.assertEqual((batch["id"], batch["hydration"]), (1, 3))

    def test_replay_uses_recorded_release_after_process_restart(self):
        from mosslight.runtime import execute_for
        from mosslight.weather import weather_on
        world = garden()
        for cell in world.cells:
            cell.moisture = 90
        day = next(day for day in range(1, 366) if weather_on(world.seed, day)["weather"] == "drizzle")
        world.day = day - 1
        world.workbench["tiles"][0]["structure"] = "rain_barrel"
        branch = self.store.create(world, version="conservation-2")["branch"]
        result = self.append(branch, "grow", days=1)
        expected = World.from_dict(world.to_dict())
        classic = World.from_dict(world.to_dict())
        execute_for("conservation-2", expected, command("grow", days=1))
        execute_for("classic-1", classic, command("grow", days=1))
        self.assertEqual(result["world"], expected.to_dict())
        self.assertNotEqual(result["world"]["cells"][0]["moisture"], classic.cells[0].moisture)
        self.store.close()
        self.store = HistoryStore(self.path)
        self.assertTrue(self.store.verify(branch)["matches"])

    def test_checkpoint_reuse_requires_complete_ancestry(self):
        first = self.append(self.main, "tend", x=0, y=0, action="water")
        self.append(self.main, "tend", x=1, y=0, action="compost")
        corrected = self.store.correct(self.main, {
            first["events"][0]["id"]: command("tend", x=2, y=0, action="water")})
        self.assertEqual(corrected["world"]["cells"][0]["moisture"], 0)
        self.assertEqual(corrected["world"]["cells"][2]["moisture"], 32)
        self.assertTrue(self.store.verify(corrected["branch"])["matches"])

    def test_equal_independent_actions_both_apply_shared_actions_apply_once(self):
        left = self.store.fork(self.main)["branch"]
        right = self.store.fork(self.main)["branch"]
        a = self.append(left, "tend", x=0, y=0, action="water")
        b = self.append(right, "tend", x=0, y=0, action="water")
        picked = self.store.cherry_pick(left, right, [a["events"][-1]["id"]])
        self.assertEqual(picked["world"]["cells"][0]["moisture"], 64)
        self.assertEqual(len(picked["events"]), 2)
        repeated = self.store.cherry_pick(left, picked["branch"], [a["events"][-1]["id"]])
        self.assertEqual(repeated["world"], picked["world"])
        self.assertEqual(self.store.snapshot(right), b)

    def test_pick_references_require_selected_or_preexisting_producer(self):
        source = self.store.fork(self.main)["branch"]
        a = self.append(source, "note", content="observation")
        b = self.append(source, "edit_note", ident=1, content="revised")
        bad = self.store.cherry_pick(source, self.main, [b["events"][-1]["id"]])
        self.assertEqual(bad["conflicts"][0]["kind"], "missing-reference")
        good = self.store.cherry_pick(source, self.main, [e["id"] for e in b["events"]])
        self.assertEqual(good["world"]["workbench"]["notes"][0]["text"], "revised")
        self.assertEqual(good["events"][0]["id"], a["events"][0]["id"])

    def test_rebase_uses_immutable_fork_base_after_parent_advances(self):
        self.append(self.main, "note", content="shared")
        child = self.store.fork(self.main)["branch"]
        local = self.append(child, "tend", x=0, y=0, action="water")
        parent = self.append(self.main, "tend", x=1, y=0, action="compost")
        rebased = self.store.rebase(child, self.main)
        self.assertEqual(len(rebased["events"]), 3)
        self.assertEqual(rebased["world"]["cells"][0]["moisture"], 32)
        self.assertEqual(rebased["world"]["cells"][1]["nutrients"], 82)
        self.assertEqual(self.store.snapshot(child), local)
        self.assertEqual(self.store.snapshot(self.main), parent)

    def test_three_way_rebase_preserves_correction_and_target_insertions(self):
        original = self.append(self.main, "note", content="original")
        ident = original["events"][0]["id"]
        local = self.store.correct(self.main, {ident: command("note", content="corrected")})
        self.append(self.main, "task", content="new parent event", due=5)
        rebased = self.store.rebase(local["branch"], self.main)
        self.assertEqual(rebased["world"]["workbench"]["notes"][0]["text"], "corrected")
        self.assertEqual(len(rebased["world"]["workbench"]["tasks"]), 1)
        self.append(self.main, "rename", title="later parent")
        again = self.store.rebase(rebased["branch"], self.main)
        self.assertEqual(again["world"]["workbench"]["title"], "later parent")
        self.assertEqual(again["world"]["workbench"]["notes"][0]["text"], "corrected")

    def test_concurrent_edit_and_deleted_anchor_are_explicit_conflicts(self):
        initial = self.append(self.main, "note", content="original")
        ident = initial["events"][0]["id"]
        left = self.store.correct(self.main, {ident: command("note", content="left")})
        right = self.store.correct(self.main, {ident: command("note", content="right")})
        with self.assertRaises(HistoryConflict) as error:
            self.store.rebase(left["branch"], right["branch"])
        self.assertEqual(error.exception.details["kind"], "concurrent-edit")
        child = self.store.fork(self.main)["branch"]
        self.append(child, "rename", title="local insertion")
        deleted = self.store.correct(self.main, {ident: None})
        with self.assertRaises(HistoryConflict) as error:
            self.store.rebase(child, deleted["branch"])
        self.assertEqual(error.exception.details["kind"], "missing-anchor")

    def test_append_detects_concurrent_head_change_after_computation(self):
        other = HistoryStore(self.path)
        replay = self.store._replay
        def interleave(*args, **kwargs):
            result = replay(*args, **kwargs)
            other.append(self.main, command("rename", title="concurrent survivor"))
            return result
        try:
            with patch.object(self.store, "_replay", side_effect=interleave):
                with self.assertRaises(HistoryConflict) as error:
                    self.append(self.main, "note", content="stale candidate")
            self.assertEqual(error.exception.details["kind"], "stale-head")
            result = self.store.snapshot(self.main)
            self.assertEqual(result["world"]["workbench"]["title"], "concurrent survivor")
            self.assertEqual(result["world"]["workbench"]["notes"], [])
        finally:
            other.close()

    def test_invalid_command_rolls_back_append_and_conflicts_correction(self):
        original = self.append(self.main, "tend", x=0, y=0, action="water")
        with self.assertRaises(HistoryConflict):
            self.append(self.main, "tend", x=99, y=0, action="water")
        self.assertEqual(self.store.snapshot(self.main), original)
        corrected = self.store.correct(self.main, {
            original["events"][0]["id"]: command("tend", x=99, y=0, action="water")})
        self.assertEqual(corrected["status"], "conflicted")
        self.assertEqual(corrected["applied"], 0)
        self.assertEqual(self.store.snapshot(self.main), original)

    def test_cli_exports_and_refuses_conflicted_partial_world(self):
        first, original = self.populated()
        corrected = self.store.correct(self.main, {original["events"][1]["id"]: None})
        output = Path(self.temporary.name) / "export.json"
        run = subprocess.run([sys.executable, "-B", "-m", "mosslight.history", str(self.path),
                              "export", corrected["branch"], str(output)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertFalse(output.exists())
        run = subprocess.run([sys.executable, "-B", "-m", "mosslight.history", str(self.path),
                              "export", self.main, str(output)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(output.read_text()), original["world"])


if __name__ == "__main__":
    unittest.main()
