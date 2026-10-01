import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mosslight.ensembles import EnsembleStore
from mosslight.engine import create
from mosslight.experiments import experiment


def water(offset=0):
    return {"offset": offset, "command": {"op": "tend", "args": {"x": 0, "y": 0, "action": "water"}}}


class EnsembleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "ensemble.sqlite"
        self.store = EnsembleStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def create(self, sources=None, every=1):
        return self.store.create(sources or {"north": create(7, 4, 4), "south": create(8, 4, 4)}, 3,
                                 {"water": {"events": [water()]}, "reserve": {"events": [water(2)]}},
                                 {"routine": {"plan": "water"}}, [{"name": "Watered", "route": "routine"}], every)

    def finish(self, ident):
        work = []
        while (result := self.store.work_once(ident)) is not None:
            work.append(result)
        return self.store.report(ident), work

    def test_matches_ordinary_experiment_and_does_not_mutate_sources(self):
        sources = {"north": create(7, 4, 4), "south": create(8, 4, 4)}
        before = {key: value.to_dict() for key, value in sources.items()}
        ident = self.create(sources, every=2)
        report, work = self.finish(ident)
        self.assertEqual(len(work), 4)
        for outcome in report["result"]["outcomes"]:
            reference = experiment(sources[outcome["identity"]["replicate"]], 3,
                                   [{"name": "Watered", "events": [water()]}], every=2)
            branch = next(b for b in reference["branches"] if b["name"] == outcome["identity"]["treatment"])
            self.assertEqual(outcome["payload"]["samples"], branch["samples"])
            self.assertEqual(outcome["payload"]["final"], branch["final"])
        self.assertEqual(before, {key: value.to_dict() for key, value in sources.items()})

    def test_edit_recomputes_only_read_plans_and_retains_old_report(self):
        ident = self.create()
        original, _ = self.finish(ident)
        self.assertEqual(self.store.edit(ident, {"plan:reserve": {"events": []}}), 1)
        self.finish(ident)
        self.assertEqual(self.store.edit(ident, {"plan:water": {"events": [water(1)]}}), 2)
        with self.assertRaises(ValueError):
            self.store.report(ident)
        self.finish(ident)
        self.assertEqual(self.store.report(ident, 0), original)
        self.assertEqual(self.store.inputs(ident, 0)["plan:water"], {"events": [water()]})

    def test_stale_author_edit_and_invalid_batch_are_atomic(self):
        ident = self.create()
        self.store.edit(ident, {"plan:water": {"events": []}}, 0)
        with self.assertRaises(ValueError):
            self.store.edit(ident, {"plan:reserve": {"events": []}}, 0)
        with self.assertRaises(ValueError):
            self.store.edit(ident, {"plan:water": {"events": [water()]}, "route:routine": {"plan": "unknown"}})
        self.assertEqual(self.store.status(ident)["revision"], 1)
        self.assertEqual(self.store.inputs(ident)["plan:water"], {"events": []})

    def test_two_workers_complete_one_generation_once(self):
        ident = self.create()
        other = EnsembleStore(self.path)
        try:
            first = self.store.prepare(ident)
            duplicate = other.prepare(ident)
            self.assertEqual(first["node"], duplicate["node"])
            self.assertTrue(other.publish(duplicate, other.compute(duplicate)))
            self.assertFalse(self.store.publish(first, self.store.compute(first)))
        finally:
            other.close()
        self.finish(ident)

    def test_newly_discovered_plan_edit_cannot_publish_old_numbers(self):
        ident = self.create({"north": create(7, 4, 4)})
        self.finish(ident)
        self.store.edit(ident, {"route:routine": {"plan": "reserve"}})
        ticket = self.store.prepare(ident)
        computed = self.store.compute(ticket)
        other = EnsembleStore(self.path)
        try:
            other.edit(ident, {"plan:reserve": {"events": []}})
        finally:
            other.close()
        self.store.publish(ticket, computed)
        report, _ = self.finish(ident)
        fresh = self.store.replay(ident)
        self.assertEqual([r["payload"] for r in report["result"]["outcomes"]],
                         [r["payload"] for r in fresh["outcomes"]])

    def test_unrelated_edit_preserves_correctness(self):
        ident = self.create()
        ticket = self.store.prepare(ident)
        computed = self.store.compute(ticket)
        self.store.edit(ident, {"plan:reserve": {"events": []}})
        self.store.publish(ticket, computed)
        self.finish(ident)

    def test_publication_failure_rolls_back_work_and_cache(self):
        ident = self.create()
        ticket = self.store.prepare(ident)
        computed = self.store.compute(ticket)
        with patch.object(self.store, "_archive_if_ready", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.store.publish(ticket, computed)
        self.assertEqual(self.store.status(ident)["nodes"][0]["status"], "pending")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM ensemble_cache").fetchone()[0], 0)
        self.assertTrue(self.store.publish(ticket, computed))

    def test_process_exit_before_publication_leaves_work_retryable(self):
        ident = self.create()
        script = "from mosslight.ensembles import EnsembleStore; import os,sys; s=EnsembleStore(sys.argv[1]); t=s.prepare(sys.argv[2]); s.compute(t); os._exit(0)"
        subprocess.run([sys.executable, "-B", "-c", script, str(self.path), ident], check=True)
        self.assertEqual(self.store.status(ident)["nodes"][0]["status"], "pending")
        report, _ = self.finish(ident)
        self.store.close()
        self.store = EnsembleStore(self.path)
        self.assertEqual(report, self.store.report(ident))

    def test_cache_reuse_keeps_equal_source_members_distinct(self):
        source = create(7, 4, 4)
        ident = self.create({"north": source, "south": copy.deepcopy(source)})
        report, work = self.finish(ident)
        self.assertEqual(report["result"]["comparisons"][0]["paired_replicates"], ["north", "south"])
        identities = [out["identity"]["replicate"] for out in report["result"]["outcomes"]]
        self.assertEqual(identities, ["north", "north", "south", "south"])

    def test_failed_treatment_is_reported_and_source_days_do_not_shift_offsets(self):
        north, south = create(7, 4, 4), create(8, 6, 4)
        south.day = 30
        command = {"offset": 0, "command": {"op": "tend", "args": {"x": 5, "y": 0, "action": "water"}}}
        ident = self.store.create({"north": north, "south": south}, 3,
                                  {"edge": {"events": [command]}}, {"edge": {"plan": "edge"}},
                                  [{"name": "Edge watering", "route": "edge"}], every=2)
        report, _ = self.finish(ident)
        comparison = report["result"]["comparisons"][0]
        self.assertEqual(comparison["paired_replicates"], ["south"])
        self.assertEqual(comparison["excluded_replicates"], ["north"])
        self.assertEqual([p["offset"] for p in comparison["series"]], [0, 2, 3])
        south_rows = [r for r in report["result"]["outcomes"] if r["identity"]["replicate"] == "south"]
        self.assertEqual(comparison["final_delta"]["moisture"], round(south_rows[1]["payload"]["final"]["averages"]["moisture"]
                                                                    - south_rows[0]["payload"]["final"]["averages"]["moisture"], 6))

    def test_conditional_selection_and_input_ownership(self):
        source = create(7, 4, 4)
        ident = self.create({"north": source})
        route = {"plan": "water", "when": {"metric": "coverage", "below": 101, "plan": "reserve"}}
        self.store.edit(ident, {"route:routine": route})
        route["when"]["plan"] = "not saved"
        report, _ = self.finish(ident)
        outcome = report["result"]["outcomes"][1]
        self.assertEqual(outcome["selected_plan"], "reserve")
        self.assertIn("plan:reserve", outcome["reads"])
        self.assertNotIn("plan:water", outcome["reads"])

    def test_cli_exports_immutable_inputs_and_report(self):
        example = Path(__file__).resolve().parent.parent / "examples" / "ensemble.json"
        output = subprocess.check_output([sys.executable, "-B", "-m", "mosslight.ensembles", str(self.path), "create", str(example)])
        ident = json.loads(output)
        subprocess.check_output([sys.executable, "-B", "-m", "mosslight.ensembles", str(self.path), "work", ident])
        for operation in ("inputs", "report"):
            output = subprocess.check_output([sys.executable, "-B", "-m", "mosslight.ensembles", str(self.path), operation, ident])
            self.assertIsInstance(json.loads(output), dict)


if __name__ == "__main__":
    unittest.main()
