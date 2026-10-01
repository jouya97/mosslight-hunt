"""Public integration behavior for all three local workspace workflows."""
import tempfile
import unittest
from pathlib import Path

from mosslight.campaigns import CampaignStore
from mosslight.engine import create
from mosslight.ensembles import EnsembleStore
from mosslight.history import HistoryStore
from mosslight.model import World


class WorkspaceWorkflowTests(unittest.TestCase):
    def test_shared_database_preserves_history_campaign_and_ensemble_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "field-station.sqlite"
            history, campaigns, ensembles = HistoryStore(path), CampaignStore(path), EnsembleStore(path)
            try:
                original = history.create(create(13, 4, 4), "source garden")
                authored = history.append(original["branch"], {"op": "note", "args": {"content": "Before comparison"}})
                source = World.from_dict(authored["world"])
                campaign = campaigns.create(source, 2, [{"name": "Observe", "events": []}], version="classic-1")
                while campaigns.work_once(campaign):
                    pass
                child = campaigns.fork(campaign, 0, 1, days=1, version="conservation-2")
                while campaigns.work_once(child):
                    pass
                archived_report = campaigns.report(campaign)
                first = campaigns.checkpoint(campaign, 0, 2)["state"]["world"]
                second = campaigns.checkpoint(child, 0, 1)["state"]["world"]
                ensemble = ensembles.create({"original release": first, "conservation release": second}, 1,
                                            {"observe": {"events": []}}, {"routine": {"plan": "observe"}},
                                            [{"name": "Observation", "route": "routine"}])
                captured = ensembles.inputs(ensemble)
                while ensembles.work_once(ensemble) is not None:
                    pass
                history.append(original["branch"], {"op": "note", "args": {"content": "A later observation"}})
                self.assertEqual(ensembles.inputs(ensemble), captured)
                self.assertEqual(campaigns.report(campaign), archived_report)
                self.assertEqual(len(history.snapshot(original["branch"], authored["revision"])["world"]["workbench"]["notes"]), 1)
                self.assertEqual(campaigns.report(child)["runtime"]["id"], "conservation-2")
                self.assertEqual(len(campaigns.provenance(child)), 2)
                report = ensembles.report(ensemble)
                self.assertEqual(report["result"]["comparisons"][0]["paired_replicates"],
                                 ["original release", "conservation release"])
            finally:
                ensembles.close()
                campaigns.close()
                history.close()


if __name__ == "__main__":
    unittest.main()
