"""Runtime packet equivalence against preserved authoring inputs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mosslight_hunt.grader.probes import load_static_probes, reviewer_inventory
from mosslight_hunt.grader.weights import DEFAULT_MANIFEST, DEFAULT_SCORECARD, manifest_weights
from mosslight_hunt.grader.tests.test_independent_probes import FIXTURES, FixtureRunner

ARCHIVE = FIXTURES / 'probe_archive'
ORIGINAL_FILES = ('probes_ecology_forms.json', 'probes_persistence.json',
                  'probes_specialist.json', 'probes_irrigation.json')


class ScorecardTests(unittest.TestCase):
    def test_same_contracts_and_points_without_injection_inputs(self):
        legacy = manifest_weights(DEFAULT_MANIFEST)
        # Default weighting must remain independent of the injection manifest.
        read = Path.read_text
        def guarded(path, *args, **kwargs):
            if path == DEFAULT_MANIFEST:
                raise AssertionError('runtime consulted authoring manifest')
            return read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            current = manifest_weights()
        self.assertEqual(current, legacy)
        self.assertEqual((len(current), sum(current.values())), (119, 251))
        card = json.loads(DEFAULT_SCORECARD.read_text())
        for entry in card['entries']:
            self.assertEqual(set(entry), {'id', 'weight', 'contract', 'documentation', 'source', 'probe'})
            self.assertTrue(entry['contract'])
            for ref in entry['documentation']:
                document = FIXTURES / 'seeded_snapshot' / ref.split('#')[0]
                self.assertTrue(document.is_file(), ref)
            for ref in entry['source']:
                self.assertTrue((FIXTURES / 'seeded_snapshot' / ref).is_file(), ref)
            if entry['id'] not in ('N01', 'I01'):
                self.assertTrue((DEFAULT_SCORECARD.parent.parent / entry['probe']).is_file())

    def test_original_expected_values_comparators_and_programs(self):
        original = [probe for name in ORIGINAL_FILES for probe in json.loads((ARCHIVE / name).read_text())]
        current = load_static_probes()
        self.assertEqual(len(current), 117)
        self.assertEqual([p['id'] for p in current], [p['id'] for p in original])
        for before, after in zip(original, current):
            with self.subTest(contract=before['id']):
                self.assertEqual(before['expected'], after['expected'])
                self.assertEqual(before.get('comparator'), after.get('comparator'))
                if before['id'] != 'I02':
                    self.assertEqual(before['program'], after['program'])

    def test_factored_irrigation_program_preserves_observations(self):
        original = json.loads((ARCHIVE / 'probes_irrigation.json').read_text())[0]
        current = next(probe for probe in load_static_probes() if probe['id'] == 'I02')
        for tree in ('clean_baseline', 'seeded_snapshot'):
            with self.subTest(tree=tree):
                runner = FixtureRunner()
                self.assertEqual(runner.observe(FIXTURES / tree, original['program']),
                                 runner.observe(FIXTURES / tree, current['program']))
        # Each load is independent: mutating one returned full-world answer must
        # not contaminate another schedule or a subsequent oracle construction.
        pristine = copy.deepcopy(current['expected'])
        schedule = next(iter(current['expected'][0]['schedules'].values()))
        schedule['world']['cells'][3]['moisture'] = 100
        self.assertEqual(next(p for p in load_static_probes() if p['id'] == 'I02')['expected'], pristine)

    def test_inventory_counts_executable_inputs_and_documents(self):
        packet = reviewer_inventory()
        self.assertEqual((packet['contracts'], packet['points'], packet['static_programs']), (119, 251, 117))
        files = {row['path']: row for row in packet['files']}
        self.assertIn('grader/probes.py', files)
        self.assertIn('grader/grader.py', files)
        self.assertIn('grader/grader_data/probes/I02.py', files)
        self.assertIn('grader/grader_data/irrigation_expected.json', files)
        self.assertIn('host_only/seeded_snapshot/IRRIGATION.md', files)
        self.assertNotIn('grader/grader_data/manifest.json', files)
        self.assertEqual(packet['bytes'], sum(row['bytes'] for row in files.values()))
        self.assertEqual(packet['lines'], sum(row['lines'] for row in files.values()))
        for row in files.values():
            self.assertEqual(len(row['sha256']), 64)

    def test_rejects_invalid_scorecards_and_preserves_explicit_legacy_levels(self):
        cases = [([{'id': 'A', 'weight': True}], 'positive integers'),
                 ([{'id': 'A', 'weight': 0}], 'positive integers'),
                 ([{'id': 'A', 'weight': 1}, {'id': 'A', 'weight': 2}], 'duplicate'),
                 ([{'id': 'A', 'level': 'unknown'}], 'unknown defect level'),
                 ([], 'empty')]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'input.json'
            for entries, message in cases:
                path.write_text(json.dumps({'entries': entries}))
                with self.subTest(entries=entries), self.assertRaisesRegex(ValueError, message):
                    manifest_weights(path)
            path.write_text(json.dumps({'entries': [{'id': 'A', 'level': 'hard'}]}))
            self.assertEqual(manifest_weights(path), {'A': 5})


if __name__ == '__main__':
    unittest.main()
