import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mosslight.model import Cell, World
from mosslight.save_merge import reconcile, verify_receipt


def garden():
    return World(7, 4, 4, cells=[Cell(50, 50, 50) for _ in range(16)]).to_dict()


def note(save, ident, text="same independent observation"):
    save["workbench"]["notes"].append({"id": ident, "day": 0, "text": text, "tags": [], "tile": None})
    save["workbench"]["next_id"] = max(save["workbench"]["next_id"], ident + 1)


class SaveMergeTests(unittest.TestCase):
    def merge(self, base, left, right, **kw):
        return reconcile(base, left, right, left_origin="desk", right_origin="field", **kw)

    def test_independent_allocations_with_identical_content_survive(self):
        base = garden()
        left, right = copy.deepcopy(base), copy.deepcopy(base)
        note(left, 1)
        note(right, 1)
        originals = copy.deepcopy([base, left, right])
        result = self.merge(base, left, right)
        self.assertEqual(result["status"], "ready")
        entries = result["world"]["workbench"]["notes"]
        self.assertEqual(len(entries), 2)
        self.assertNotEqual(entries[0]["id"], entries[1]["id"])
        self.assertEqual(entries[0]["text"], entries[1]["text"])
        self.assertEqual([base, left, right], originals)
        self.assertTrue(verify_receipt(result, base, left, right, left_origin="desk", right_origin="field"))

    def test_different_fields_of_an_inherited_note_merge(self):
        base = garden();note(base, 1, "ancestor")
        left, right = copy.deepcopy(base), copy.deepcopy(base)
        left["workbench"]["notes"][0]["text"] = "revised"
        right["workbench"]["notes"][0]["tags"] = ["fern"]
        result = self.merge(base, left, right)
        self.assertEqual(result["status"], "ready")
        entry = result["world"]["workbench"]["notes"][0]
        self.assertEqual((entry["id"], entry["text"], entry["tags"]), (1, "revised", ["fern"]))

    def test_delete_edit_conflict_is_explicit_and_resolvable(self):
        base = garden();note(base, 1, "ancestor")
        left, right = copy.deepcopy(base), copy.deepcopy(base)
        left["workbench"]["notes"] = []
        right["workbench"]["notes"][0]["text"] = "remote change"
        conflict = self.merge(base, left, right)
        self.assertEqual(conflict["status"], "conflict")
        path = conflict["conflicts"][0]["path"]
        self.assertFalse(conflict["conflicts"][0]["left"]["present"])
        restored = self.merge(base, left, right, resolutions={path: {"choose": "right"}})
        self.assertEqual(restored["world"]["workbench"]["notes"][0]["text"], "remote change")
        removed = self.merge(base, left, right, resolutions={path: {"choose": "left"}})
        self.assertEqual(removed["world"]["workbench"]["notes"], [])

    def test_ecology_conflict_retains_a_consistent_habitat_unit(self):
        base = garden();left, right = copy.deepcopy(base), copy.deepcopy(base)
        left["cells"][0]["moisture"] = 100
        left["workbench"]["tiles"][0]["terrain"] = "pond"
        right["cells"][0].update(species="fern", age=2, vitality=60)
        conflict = self.merge(base, left, right)
        self.assertEqual([c["path"] for c in conflict["conflicts"]], ["/ecology"])
        result = self.merge(base, left, right, resolutions={"/ecology": {"choose": "right"}})
        self.assertEqual(result["world"]["cells"][0]["species"], "fern")
        self.assertEqual(result["world"]["workbench"]["tiles"][0]["terrain"], "soil")

    def test_swapping_replica_inputs_preserves_the_merged_garden(self):
        base = garden();left, right = copy.deepcopy(base), copy.deepcopy(base)
        note(left, 1, "left");note(right, 1, "right")
        original = self.merge(base, left, right)
        swapped = reconcile(base, right, left, left_origin="field", right_origin="desk")
        self.assertEqual(original, swapped)

    def test_v1_ancestor_upgrades_before_reconciliation(self):
        old = garden();old["version"] = 1;old.pop("workbench")
        left = World.from_dict(old).to_dict();right = copy.deepcopy(left)
        note(left, 1, "one");note(right, 1, "two")
        result = self.merge(old, left, right)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["world"]["version"], 2)
        self.assertEqual(len(result["world"]["workbench"]["notes"]), 2)

    def test_allocation_keeps_numeric_plan_order(self):
        base = garden();left, right = copy.deepcopy(base), copy.deepcopy(base)
        for ident, action in [(10, "clear"), (2, "plant_moss")]:
            left["workbench"]["plans"].append({"id": ident, "name": str(ident), "day": 1,
                "action": action, "tiles": [[0, 0]], "repeat": 0, "remaining": 1,
                "status": "pending", "last_error": ""})
        left["workbench"]["next_id"] = 11
        result = self.merge(base, left, right)
        self.assertEqual(result["status"], "ready")
        self.assertEqual([p["action"] for p in result["world"]["workbench"]["plans"]], ["plant_moss", "clear"])

    def test_cross_field_incompatibility_is_reported_without_a_save(self):
        base = garden();left, right = copy.deepcopy(base), copy.deepcopy(base)
        for value, point in [(left, [0, 0]), (right, [1, 1])]:
            value["workbench"]["beds"] = [{"id": 1, "name": "Fern bed", "tiles": [point]}]
            value["workbench"]["next_id"] = 2
        result = self.merge(base, left, right)
        self.assertEqual(result["status"], "incompatible")
        self.assertNotIn("world", result)
        self.assertIn("Bed names", result["reason"])

    def test_save_validation_checks_every_bed(self):
        world = garden()
        world["workbench"]["beds"] = [{"id": 1, "name": "Fern bed", "tiles": [[0, 0]]},
            {"id": 2, "name": "fern BED", "tiles": [[1, 1]]}]
        world["workbench"]["next_id"] = 3
        with self.assertRaisesRegex(ValueError, "Bed names"):
            World.from_dict(world)
        world["workbench"]["beds"][1] = {"id": 2, "name": "Another bed", "tiles": [[90, 90]]}
        with self.assertRaises(ValueError):
            World.from_dict(world)

    def test_stale_conflict_resolution_and_wrong_origins_rejected(self):
        base = garden()
        with self.assertRaises(ValueError):
            self.merge(base, base, base, resolutions={"/title": {"choose": "right"}})
        with self.assertRaises(ValueError):
            reconcile(base, base, base, left_origin="device", right_origin="device")

    def test_receipt_detects_result_and_source_changes(self):
        base = garden();left, right = copy.deepcopy(base), copy.deepcopy(base)
        note(left, 1)
        result = self.merge(base, left, right)
        altered = copy.deepcopy(result);altered["world"]["workbench"]["notes"][0]["text"] = "changed"
        self.assertFalse(verify_receipt(altered, base, left, right, left_origin="desk", right_origin="field"))
        note(right, 1, "different source")
        self.assertFalse(verify_receipt(result, base, left, right, left_origin="desk", right_origin="field"))

    def test_cli_writes_a_reviewable_receipt_and_save(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder);base = garden()
            for name in ("base", "left", "right"):
                (folder/(name + ".json")).write_text(json.dumps(base))
            output = folder/"merged.json"
            completed = subprocess.run([sys.executable, "-B", "-m", "mosslight.save_merge",
                str(folder/"base.json"), str(folder/"left.json"), str(folder/"right.json"), str(output),
                "--left-origin", "desk", "--right-origin", "field"], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(output.read_text())["status"], "ready")


if __name__ == "__main__":
    unittest.main()
