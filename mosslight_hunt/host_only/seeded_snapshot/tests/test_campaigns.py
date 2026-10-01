import concurrent.futures
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from mosslight.campaigns import CampaignStore
from mosslight.engine import create
from mosslight.experiments import experiment


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "experiments.sqlite"
        self.now = 100.0
        self.store = CampaignStore(self.path, clock=lambda: self.now)
        self.world = create(13, 4, 4)
        self.treatments = [{"name": "Wet", "events": [
            {"offset": 0, "command": {"op": "tend", "args": {"x": 0, "y": 0, "action": "water"}}},
            {"offset": 3, "command": {"op": "tend", "args": {"x": 1, "y": 0, "action": "water"}}},
            {"offset": 5, "command": {"op": "tend", "args": {"x": 2, "y": 0, "action": "water"}}},
        ]}]

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def run_all(self, campaign):
        while self.store.work_once(campaign):
            pass
        return self.store.result(campaign)

    def test_resuming_every_offset_matches_existing_scientific_reference(self):
        before = copy.deepcopy(self.world.to_dict())
        ident = self.store.create(self.world, 5, self.treatments, every=3)
        for _ in range(12):
            self.assertTrue(self.store.work_once(ident))
            self.store.close()
            self.store = CampaignStore(self.path, clock=lambda: self.now)
        self.assertFalse(self.store.work_once(ident))
        self.assertEqual(self.store.result(ident), experiment(self.world, 5, self.treatments, every=3))
        self.assertEqual(self.world.to_dict(), before)

    def test_identity_contains_complete_state_and_ordered_treatment_history(self):
        ident = self.store.create(self.world, 5, self.treatments)
        self.assertEqual(ident, self.store.create(self.world, 5, self.treatments))
        other = copy.deepcopy(self.treatments)
        other[0]["events"][0]["offset"] = 1
        self.assertNotEqual(ident, self.store.create(self.world, 5, other))
        changed = copy.deepcopy(self.world)
        changed.workbench["title"] = "Separate archived source"
        self.assertNotEqual(ident, self.store.create(changed, 5, self.treatments))

    def test_reclaimed_worker_cannot_publish_or_fail_the_new_owner(self):
        ident = self.store.create(self.world, 5, self.treatments)
        original = self.store.claim(ident, lease_seconds=10)
        computed = self.store.compute(original)
        self.now = 111
        replacement = self.store.claim(ident, lease_seconds=10)
        self.assertEqual(original["ordinal"], replacement["ordinal"])
        self.assertGreater(replacement["generation"], original["generation"])
        self.assertFalse(self.store.publish(original, computed))
        self.assertFalse(self.store.fail(original, "old worker failed"))
        self.assertTrue(self.store.publish(replacement, self.store.compute(replacement)))
        self.assertEqual(self.run_all(ident), experiment(self.world, 5, self.treatments))

    def test_two_live_workers_claim_different_branches(self):
        ident = self.store.create(self.world, 5, self.treatments)
        barrier = threading.Barrier(2)

        def worker():
            connection = CampaignStore(self.path, clock=lambda: 100)
            try:
                barrier.wait(timeout=5)
                return connection.claim(ident)
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(worker)
            second = pool.submit(worker)
            claims = [first.result(timeout=10), second.result(timeout=10)]
        self.assertEqual({claim["ordinal"] for claim in claims}, {0, 1})

    def test_process_death_before_and_after_checkpoint_replays_exactly_once(self):
        for publish in (False, True):
            with self.subTest(after_publication=publish):
                path = Path(self.directory.name) / ("published.sqlite" if publish else "unpublished.sqlite")
                store = CampaignStore(path, clock=lambda: 100)
                ident = store.create(self.world, 5, self.treatments)
                store.close()
                script = "\n".join([
                    "import os,sys", "from mosslight.campaigns import CampaignStore",
                    "store=CampaignStore(sys.argv[1],clock=lambda:100)",
                    "claim=store.claim(sys.argv[2],lease_seconds=10)",
                    "state=store.compute(claim)",
                    "store.publish(claim,state)" if publish else "pass",
                    "os._exit(23)",
                ])
                process = subprocess.run([sys.executable, "-B", "-c", script, str(path), ident], capture_output=True, text=True)
                self.assertEqual(process.returncode, 23, process.stderr)
                resumed = CampaignStore(path, clock=lambda: 111)
                try:
                    while resumed.work_once(ident):
                        pass
                    self.assertEqual(resumed.result(ident), experiment(self.world, 5, self.treatments))
                finally:
                    resumed.close()

    def test_cancel_fences_computations_already_in_flight(self):
        ident = self.store.create(self.world, 5, self.treatments)
        claim = self.store.claim(ident)
        self.store.cancel(ident)
        self.assertFalse(self.store.publish(claim, self.store.compute(claim)))
        self.assertFalse(self.store.work_once(ident))
        self.assertTrue(all(row["status"] == "cancelled" for row in self.store.status(ident)))
        with self.assertRaisesRegex(ValueError, "not complete"):
            self.store.result(ident)

    def test_failed_command_publishes_no_partial_day(self):
        treatments = copy.deepcopy(self.treatments)
        treatments[0]["events"].append({"offset": 0, "command": {"op": "unknown", "args": {}}})
        ident = self.store.create(self.world, 5, treatments)
        while self.store.work_once(ident):
            pass
        statuses = self.store.status(ident)
        self.assertEqual([row["status"] for row in statuses], ["complete", "failed"])
        state = json.loads(self.store.db.execute(
            "SELECT state FROM branches WHERE campaign = ? AND ordinal = 1", (ident,)).fetchone()[0])
        self.assertEqual(state["next_offset"], 0)
        self.assertEqual(state["world"], self.world.to_dict())

    def test_changed_engine_fails_closed_and_inputs_remain_owned(self):
        ident = self.store.create(self.world, 5, self.treatments)
        claim = self.store.claim(ident)
        before = copy.deepcopy(claim)
        self.store.compute(claim)
        self.assertEqual(before, claim)
        with mock.patch("mosslight.campaigns.engine_fingerprint", return_value="new-engine"):
            with self.assertRaisesRegex(ValueError, "original engine"):
                self.store.claim(ident)
            with self.assertRaisesRegex(ValueError, "original engine"):
                self.store.result(ident)


if __name__ == "__main__":
    unittest.main()
