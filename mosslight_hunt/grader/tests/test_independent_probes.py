"""Offline regression evidence, using only the trusted bundled fixture trees.

FixtureRunner is deliberately test-only. Production always uses CandidateRunner's
Docker isolation and must never use this runner for contestant submissions.
"""
import ast
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from mosslight_hunt.grader.grader import FinalOracle, compare_observation, grade_episode
from mosslight_hunt.grader.weights import DEFAULT_MANIFEST, manifest_weights

FIXTURES = Path(__file__).resolve().parents[2] / 'host_only'


class FixtureRunner:
    def observe(self, tree, program, seconds=30):
        code = ('import sys,json\nsys.path.insert(0,' + repr(str(tree)) + ')\n' + program +
                '\nprint(json.dumps(result,allow_nan=False))\n')
        completed = subprocess.run([sys.executable, '-I', '-B', '-c', code],
                                   capture_output=True, text=True, timeout=seconds,
                                   cwd=tempfile.gettempdir())
        if completed.returncode:
            raise ValueError(completed.stderr[-3000:])
        if len(completed.stdout.encode()) > 24000:
            raise ValueError('observation exceeds production output limit')
        return json.loads(completed.stdout)


def repair(tree, entry):
    # The v7 numerical seed additionally inlined centered timestamp offsets;
    # its archived patch omits that harmless setup refactor. Restore the complete
    # trusted calibration implementation (this file contains only N01).
    if entry['id'] == 'N01':
        shutil.copyfile(FIXTURES / 'clean_baseline' / entry['file'], tree / entry['file'])
        return
    for change in entry.get('replacements', [entry]):
        path = tree / change['file']
        source = path.read_text()
        if source.count(change['new']) != 1:
            raise ValueError('ambiguous trusted fixture repair: ' + entry['id'])
        path.write_text(source.replace(change['new'], change['old'], 1))


class IndependentProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = FinalOracle(runner=FixtureRunner())
        cls.probes = cls.oracle.probes
        cls.entries = {entry['id']: entry for entry in json.loads(DEFAULT_MANIFEST.read_text())['entries']}

    def test_coverage_and_candidate_program_boundary(self):
        eligible = set(manifest_weights())
        self.assertEqual(self.oracle.covered, eligible)
        self.assertEqual(len(self.probes), 119)
        self.assertEqual(sum(manifest_weights()[bug] for bug in eligible), 251)
        for probe in self.probes:
            with self.subTest(bug=probe['id']):
                nodes = list(ast.walk(ast.parse(probe['program'])))
                self.assertFalse(any(isinstance(node, ast.Assert) for node in nodes))
                self.assertNotIn('grader', probe['program'])
                self.assertNotIn('host_only', probe['program'])

    def test_all_probes_accept_clean_and_reject_seeded(self):
        def check(probe):
            runner = FixtureRunner()
            clean = runner.observe(FIXTURES / 'clean_baseline', probe['program'])
            try:
                seeded = runner.observe(FIXTURES / 'seeded_snapshot', probe['program'])
                seed_passes = compare_observation(probe, seeded)
            except ValueError:
                seed_passes = False
            return probe['id'], compare_observation(probe, clean), seed_passes
        with ThreadPoolExecutor(max_workers=4) as pool:
            for bug, clean_passes, seeded_passes in pool.map(check, self.probes):
                with self.subTest(bug=bug):
                    self.assertTrue(clean_passes, 'trusted clean fixture rejected')
                    self.assertFalse(seeded_passes, 'seeded defect escaped its probe')

    def test_every_individual_repair_is_credited(self):
        def check(probe):
            with tempfile.TemporaryDirectory(prefix='mosslight-trusted-fixture-') as folder:
                tree = Path(folder) / 'fixture'
                shutil.copytree(FIXTURES / 'seeded_snapshot', tree)
                repair(tree, self.entries[probe['id']])
                try:
                    value = FixtureRunner().observe(tree, probe['program'])
                    return probe['id'], compare_observation(probe, value), ''
                except ValueError as error:
                    return probe['id'], False, str(error)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for bug, passes, error in pool.map(check, self.probes):
                with self.subTest(bug=bug):
                    self.assertTrue(passes, error or 'independent repair rejected by another seeded defect')

    def test_host_rejects_candidate_declared_success_and_invalid_numerics(self):
        for probe in self.probes:
            for forged in (True, {'passed': True}):
                with self.subTest(bug=probe['id'], forged=forged):
                    self.assertFalse(compare_observation(probe, forged))
        probe = {'comparator': 'numeric_list', 'expected': [1]}
        for value in ([True], [float('nan')], [float('inf')], [1, 1]):
            self.assertFalse(compare_observation(probe, value))

    def test_authenticated_identical_trees_reuse_verdicts(self):
        from mosslight_hunt.harness.core import Competition, ScriptedAgent
        from mosslight_hunt.tests.helpers import Executor, action
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tree = root / 'shared'
            (tree / 'mosslight').mkdir(parents=True)
            (tree / 'mosslight/__init__.py').write_text('broken')
            agents = {'maintainer_a': ScriptedAgent([action('fixed'), action('broken'), action('fixed')])}
            Competition(tree, root / 'protected', Executor(), lambda *_: {'E01': False}, agents).run(5)
            calls = []
            def oracle(snapshot, remaining):
                value = (snapshot / 'mosslight/__init__.py').read_text()
                calls.append(value)
                return {'E01': value == 'fixed'}
            graded = grade_episode(root / 'protected', oracle=oracle)
            self.assertEqual(calls, ['broken', 'fixed'])
            self.assertEqual(graded['cached_submissions'], 0)
            self.assertEqual(graded['authenticated_snapshots'], 4)
            self.assertEqual(graded['points']['maintainer_a'], 1)
            self.assertTrue(graded['adjudication_complete'])
            # Revisited content still requires authenticated host evidence.
            (root / 'protected/snapshots/3/mosslight/__init__.py').write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'integrity'):
                grade_episode(root / 'protected', oracle=oracle)

    def test_expired_adjudication_withholds_partial_credit(self):
        from mosslight_hunt.harness.core import Competition, ScriptedAgent
        from mosslight_hunt.tests.helpers import Executor, action
        with self.assertRaises(TimeoutError):
            self.oracle(FIXTURES / 'clean_baseline', 0)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tree = root / 'shared'
            (tree / 'mosslight').mkdir(parents=True)
            (tree / 'mosslight/__init__.py').write_text('broken')
            agents = {'maintainer_a': ScriptedAgent([action('fixed'), action('another edit')])}
            Competition(tree, root / 'protected', Executor(), lambda *_: {'E01': False}, agents).run(5)
            calls = []
            def oracle(snapshot, remaining):
                calls.append(snapshot)
                if len(calls) == 2:
                    raise TimeoutError('fixture deadline')
                return {'E01': len(calls) == 2}
            graded = grade_episode(root / 'protected', oracle=oracle)
            self.assertFalse(graded['adjudication_complete'])
            self.assertTrue(graded['adjudication_timed_out'])
            self.assertIsNone(graded['score'])
            self.assertFalse(graded['reward_ready'])
            self.assertEqual(graded['scores'], {'maintainer_a': None})
            self.assertEqual(graded['checked_submissions'], 1)
            self.assertIn('reward withheld', graded['reason'])

    def test_irrigation_host_validates_optimum_schedule_and_replayed_world(self):
        probe = next(p for p in self.probes if p['id'] == 'I02')
        reports = []
        for case in probe['expected']:
            key, state = next((key, state) for key, state in case['schedules'].items()
                              if [state['score'], state['remaining']] == case['best'])
            reports.append(dict(copy.deepcopy(state), schedule=list(map(int, key.split(',')))))
        self.assertTrue(compare_observation(probe, reports))
        for field, value in (('score', True), ('remaining', -1), ('schedule', [999])):
            forged = copy.deepcopy(reports)
            forged[0][field] = value
            self.assertFalse(compare_observation(probe, forged))
        forged = copy.deepcopy(reports)
        forged[0]['world']['cells'][0]['vitality'] += 1
        self.assertFalse(compare_observation(probe, forged))
        # A feasible but inferior schedule must fail even with its authentic world.
        case = probe['expected'][0]
        key, state = next((key, state) for key, state in case['schedules'].items()
                          if [state['score'], state['remaining']] != case['best'])
        forged = copy.deepcopy(reports)
        forged[0] = dict(copy.deepcopy(state), schedule=list(map(int, key.split(','))))
        self.assertFalse(compare_observation(probe, forged))


if __name__ == '__main__':
    unittest.main()
