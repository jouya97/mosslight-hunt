import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mosslight.campaigns import CampaignStore
from mosslight.model import World, Cell
from mosslight.runtime import execute_for, step_for, version_info
from mosslight.semantics import ACTIVE_RELEASE


class HistoricalCampaignTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = CampaignStore(Path(self.directory.name) / "history.sqlite")
        self.world = World(7, 4, 4, cells=[Cell(68, 50, 50) for _ in range(16)])
        for tile in self.world.workbench["tiles"]:
            tile["structure"] = "rain_barrel"
        self.treatments = [{"name": "Observe", "events": []}]

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def finish(self, ident):
        while self.store.work_once(ident):
            pass
        return self.store.result(ident)

    def test_both_releases_retained_and_execution_context_restored(self):
        old = copy.deepcopy(self.world)
        new = copy.deepcopy(self.world)
        step_for("classic-1", old)
        step_for("conservation-2", new)
        self.assertEqual(old.cells[0].moisture - new.cells[0].moisture, 4)
        self.assertEqual(ACTIVE_RELEASE.get(), "classic-1")
        with self.assertRaises(ValueError):
            execute_for("conservation-2", new, {"op": "unknown"})
        self.assertEqual(ACTIVE_RELEASE.get(), "classic-1")

    def test_historical_campaign_uses_recorded_release_on_resume_and_replay(self):
        ident = self.store.create(self.world, 3, self.treatments, version="classic-1")
        self.store.work_once(ident)
        result = self.finish(ident)
        expected = copy.deepcopy(self.world)
        step_for("classic-1", expected, 3)
        actual = self.store.checkpoint(ident, 0, 3)["state"]["world"]
        self.assertEqual(actual, expected.to_dict())
        self.assertEqual(result, self.store.replay(ident))
        self.assertEqual(self.store.report(ident)["runtime"]["id"], "classic-1")

    def test_completed_reports_are_immutable_even_when_installation_changes(self):
        ident = self.store.create(self.world, 2, self.treatments)
        self.finish(ident)
        report = self.store.report(ident)
        with mock.patch("mosslight.campaigns.census", side_effect=AssertionError("must not reinterpret")):
            with mock.patch("mosslight.campaigns.engine_fingerprint", return_value="changed"):
                self.assertEqual(self.store.report(ident), report)
                self.assertEqual(self.store.result(ident), report["result"])

    def test_fork_boundary_event_is_not_reapplied_and_future_events_follow(self):
        treatments = [{"name": "Notes", "events": [
            {"offset": 2, "command": {"op": "note", "args": {"content": "At the checkpoint"}}},
            {"offset": 3, "command": {"op": "note", "args": {"content": "After the checkpoint"}}},
        ]}]
        parent = self.store.create(self.world, 4, treatments)
        self.finish(parent)
        child = self.store.fork(parent, 1, 2, version="conservation-2")
        self.finish(child)
        notes = self.store.checkpoint(child, 1, 2)["state"]["world"]["workbench"]["notes"]
        self.assertEqual([n["text"] for n in notes], ["At the checkpoint", "After the checkpoint"])
        self.assertEqual(self.store.report(child)["runtime"]["id"], "conservation-2")
        self.assertEqual(len(self.store.provenance(child)), 2)

    def test_compaction_retains_fork_roots_and_historical_reports(self):
        parent = self.store.create(self.world, 6, self.treatments)
        self.finish(parent)
        child = self.store.fork(parent, 1, 2, days=3)
        self.finish(child)
        grandchild = self.store.fork(child, 1, 1, days=2)
        self.finish(grandchild)
        report = self.store.report(parent)
        self.assertGreater(self.store.compact(parent, keep_every=5), 0)
        self.store.compact(child, keep_every=5)
        self.assertEqual(len(self.store.provenance(grandchild)), 3)
        self.assertEqual(self.store.report(parent), report)
        self.assertEqual(self.store.replay(parent), report["result"])

    def test_checkpoint_failure_rolls_back_progress_and_terminal_publication(self):
        ident = self.store.create(self.world, 2, self.treatments)
        claim = self.store.claim(ident)
        prior = copy.deepcopy(claim["state"])
        computed = self.store.compute(claim)
        with mock.patch.object(self.store, "_checkpoint", side_effect=OSError("storage unavailable")):
            with self.assertRaises(OSError):
                self.store.publish(claim, computed)
        import json
        row = self.store.db.execute("SELECT state, status FROM branches WHERE campaign = ? AND ordinal = 0", (ident,)).fetchone()
        self.assertEqual(json.loads(row["state"]), prior)
        self.assertEqual(row["status"], "running")
        self.assertTrue(self.store.publish(claim, computed))
        self.finish(ident)

    def test_release_and_lineage_participate_in_campaign_identity(self):
        classic = self.store.create(self.world, 2, self.treatments, version="classic-1")
        conservation = self.store.create(self.world, 2, self.treatments, version="conservation-2")
        self.assertNotEqual(classic, conservation)
        self.assertEqual(self.store._definition(conservation)["runtime"], version_info("conservation-2"))


if __name__ == "__main__":
    unittest.main()
