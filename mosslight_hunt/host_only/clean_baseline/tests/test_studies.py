import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mosslight.studies import StudyStore
from mosslight.model import World, Cell


def garden(seed=7, width=4, moisture=40):
    return World(seed, width, 4, cells=[Cell(moisture, 50, 50) for _ in range(width * 4)])


def note(content, offset=0):
    return {"offset": offset, "command": {"op": "note", "args": {"content": content}}}


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "workspace.sqlite"
        self.now = [100.0]
        self.store = StudyStore(self.path, clock=lambda: self.now[0])

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def create(self, sources=None, stages=None):
        return self.store.create(sources or {"north": garden(), "south": garden(11)},
                                 [{"name": "A", "events": [note("A")]}, {"name": "B", "events": [note("B")]}],
                                 stages or [{"until": 1, "keep": 1}, {"until": 3, "keep": 1}], metric="moisture", every=2)

    def finish(self, ident, offsets=2):
        for _ in range(200):
            if self.store.work_once(ident, offsets=offsets) is None:
                return self.store.status(ident)
        self.fail("study did not finish")

    def test_stages_preserve_full_trajectory_and_boundary_samples(self):
        source = garden()
        before = copy.deepcopy(source.to_dict())
        ident = self.create({"north": source})
        self.assertEqual(self.finish(ident)["status"], "complete")
        first = self.store.report(ident, 0)
        final = self.store.report(ident, 1)
        self.assertEqual(first["decision"]["promoted"], ["A"])
        final_a = self.store.checkpoint(ident, 1, "north", "A")
        parent = self.store.checkpoint(ident, 0, "north", "A")
        self.assertEqual(final_a["parent"]["digest"], parent["digest"])
        self.assertEqual(final_a["parent"]["treatment"], "A")
        self.assertEqual([n["text"] for n in final_a["state"]["world"]["workbench"]["notes"]], ["A"])
        self.assertEqual([s["offset"] for s in final_a["state"]["samples"]], [0, 1, 2, 3])
        self.assertEqual(before, source.to_dict())
        self.assertEqual(final["decision"]["promoted"], ["A"])

    def test_partial_cohort_preview_does_not_promote(self):
        ident = self.create()
        claims = []
        while (claim := self.store.claim(ident)) is not None:
            claims.append(claim)
        for claim in claims:
            if claim["replicate"] == "north":
                self.assertTrue(self.store.publish(claim, self.store.compute(claim, offsets=2)))
        preview = self.store.preview(ident)
        self.assertEqual(preview["common"], ["north"])
        self.assertFalse(preview["terminal"])
        self.assertEqual(self.store.status(ident)["stage"], 0)
        with self.assertRaises(ValueError):
            self.store.report(ident, 0)
        for claim in reversed(claims):
            if claim["replicate"] == "south":
                self.store.publish(claim, self.store.compute(claim, offsets=2))
        self.assertEqual(self.store.status(ident)["stage"], 1)
        self.finish(ident)

    def test_later_tie_uses_original_order_not_previous_ranking(self):
        def action(name, offset):
            return {"offset": offset, "command": {"op": "tend", "args": {"x": 0, "y": 0, "action": name}}}
        ident = self.store.create({"bed": garden()},
                                  [{"name": "A", "events": []},
                                   {"name": "B", "events": [action("plant_fern", 0), action("clear", 2)]}],
                                  [{"until": 1, "keep": 2}, {"until": 2, "keep": 1}], metric="richness")
        self.finish(ident)
        self.assertEqual(self.store.report(ident, 0)["decision"]["promoted"], ["B", "A"])
        self.assertEqual(self.store.report(ident, 1)["decision"]["promoted"], ["A"])

    def test_future_edits_freeze_at_dispatch_and_preserve_reports(self):
        ident = self.create(stages=[{"until": 1, "keep": 2}, {"until": 3, "keep": 1}])
        ticket = self.store.claim(ident)
        self.store.edit_future(ident, {"A": [note("A"), note("future", 2)]}, expected_revision=0)
        self.store.publish(ticket, self.store.compute(ticket, offsets=2))
        while self.store.status(ident)["stage"] == 0:
            self.store.work_once(ident, offsets=2)
        first = self.store.report(ident, 0)
        self.assertEqual(first["plan_revision"], 0)
        with self.assertRaises(ValueError):
            self.store.edit_future(ident, {"A": [note("A"), note("too late", 2)]}, expected_revision=1)
        self.finish(ident)
        self.assertEqual(self.store.report(ident, 0), first)
        self.assertEqual(self.store.report(ident, 1)["plan_revision"], 1)
        notes = self.store.checkpoint(ident, 1, "north", "A")["state"]["world"]["workbench"]["notes"]
        self.assertEqual([n["text"] for n in notes], ["A", "future"])

    def test_source_failure_uses_same_common_cohort_for_all_scores(self):
        action = {"offset": 0, "command": {"op": "tend", "args": {"x": 5, "y": 0, "action": "water"}}}
        ident = self.store.create({"narrow": garden(width=4), "wide": garden(11, 6)},
                                  [{"name": "edge", "events": [action]}, {"name": "observe", "events": []}],
                                  [{"until": 1, "keep": 1}, {"until": 2, "keep": 1}], metric="moisture")
        self.finish(ident)
        first = self.store.report(ident, 0)
        self.assertEqual(first["decision"]["common"], ["wide"])
        self.assertEqual(first["decision"]["excluded"], ["narrow"])
        self.assertEqual(self.store.report(ident, 1)["cohort"], ["wide"])

    def test_empty_common_cohort_records_failed_study(self):
        bad = {"offset": 0, "command": {"op": "tend", "args": {"x": 9, "y": 0, "action": "water"}}}
        ident = self.store.create({"bed": garden()}, [{"name": "edge", "events": [bad]}], [{"until": 1, "keep": 1}])
        self.assertEqual(self.finish(ident)["status"], "failed")
        self.assertEqual(self.store.report(ident, 0)["decision"]["common"], [])
        self.assertIn("No source", self.store.report(ident, 0)["decision"]["error"])

    def test_reclaimed_worker_cannot_overwrite_replacement(self):
        ident = self.create()
        old = self.store.claim(ident, lease_seconds=1)
        computed = self.store.compute(old)
        self.now[0] = 102
        replacement = self.store.claim(ident)
        self.assertGreater(replacement["generation"], old["generation"])
        self.assertFalse(self.store.publish(old, computed))
        self.assertTrue(self.store.publish(replacement, self.store.compute(replacement)))
        self.finish(ident)

    def test_process_crash_reclaims_last_committed_offset(self):
        ident = self.create()
        program = 'from mosslight.studies import StudyStore; import os,sys; s=StudyStore(sys.argv[1],clock=lambda:100); t=s.claim(sys.argv[2],lease_seconds=1); s.compute(t); os._exit(0)'
        subprocess.run([sys.executable, "-B", "-c", program, str(self.path), ident], check=True)
        self.now[0] = 102
        self.assertEqual(self.finish(ident)["status"], "complete")

    def test_stage_transition_and_publication_roll_back_together(self):
        ident = self.create({"bed": garden()})
        claims = [self.store.claim(ident) for _ in range(3)]
        for claim in claims[:-1]:
            self.store.publish(claim, self.store.compute(claim, offsets=2))
        last = claims[-1]
        computed = self.store.compute(last, offsets=2)
        original = self.store._save_report
        def interrupted(*args):
            original(*args)
            raise OSError("storage interrupted")
        with patch.object(self.store, "_save_report", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.store.publish(last, computed)
        with self.assertRaises(ValueError):
            self.store.report(ident, 0)
        self.assertEqual(self.store.status(ident)["stage"], 0)
        self.assertTrue(self.store.publish(last, computed))
        self.finish(ident)

    def test_stale_edit_is_rejected_without_partial_plan_changes(self):
        ident = self.create()
        self.store.edit_future(ident, {"A": [note("A"), note("later", 3)]}, expected_revision=0)
        with self.assertRaises(ValueError):
            self.store.edit_future(ident, {"B": [note("B"), note("stale", 2)]}, expected_revision=0)
        with self.assertRaises(ValueError):
            self.store.edit_future(ident, {"A": [note("changed past")]}, expected_revision=1)
        self.assertEqual(self.store.status(ident)["plan_revision"], 1)

    def test_cli_create_work_and_stage_report(self):
        spec = {"sources": {"bed": garden().to_dict()}, "treatments": [{"name": "A", "events": [note("A")]}],
                "stages": [{"until": 1, "keep": 1}, {"until": 2, "keep": 1}]}
        path = Path(self.temp.name) / "study.json"
        path.write_text(json.dumps(spec))
        base = [sys.executable, "-B", "-m", "mosslight.studies", str(self.path)]
        ident = json.loads(subprocess.check_output([*base, "create", str(path)]))
        status = json.loads(subprocess.check_output([*base, "work", ident, "--offsets", "2"]))
        self.assertEqual(status["status"], "complete")
        report = json.loads(subprocess.check_output([*base, "report", ident, "--stage", "0"]))
        self.assertEqual(report["decision"]["promoted"], ["A"])


if __name__ == "__main__":
    unittest.main()
