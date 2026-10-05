"""Host-only static scoring inputs, with readable candidate observation programs.

The loader never executes these programs. FinalOracle sends their text to an
isolated candidate runner. All expected values and comparison remain on the host.
I02 stores one full world template and the only changing world fields (day and
the first two cells), retaining exact comparisons of the reconstructed worlds.
"""
import copy
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'grader_data'


def irrigation_expected(path):
    """Losslessly expand the reviewed schedule table; no candidate code is used."""
    packed = json.loads(Path(path).read_text())
    cases = []
    for case in packed['cases']:
        schedules = {}
        for schedule, report in case['schedules'].items():
            world = copy.deepcopy(packed['world_template'])
            world['day'] = report['day']
            world['cells'][:2] = copy.deepcopy(report['cells'])
            schedules[schedule] = {key: report[key] for key in ('score', 'remaining')}
            schedules[schedule]['world'] = world
        cases.append({'best': case['best'], 'schedules': schedules})
    return cases


def load_static_probes(data=DATA):
    """Return the original 117 probe dicts in their original order.

    Programs are text files, not imported Python modules. N01 and I01 dynamic
    inputs, and the randomized E01 replacement, still live in FinalOracle.
    """
    data = Path(data)
    descriptors = json.loads((data / 'expected.json').read_text())
    probes = []
    for bug, descriptor in descriptors.items():
        probe = {'id': bug, 'program': (data / 'probes' / (bug + '.py')).read_text()}
        if 'expected_file' in descriptor:
            if bug != 'I02' or descriptor['expected_file'] != 'irrigation_expected.json':
                raise ValueError('unexpected factored expected input')
            probe['expected'] = irrigation_expected(data / descriptor['expected_file'])
        else:
            probe['expected'] = descriptor['expected']
        if 'comparator' in descriptor:
            probe['comparator'] = descriptor['comparator']
        probes.append(probe)
    return probes


def reviewer_inventory(data=DATA):
    """Enumerate the effective final-grader packet, counting code and inputs.

    Includes all top-level grader modules (including compatibility attribution),
    all observation programs, expected tables, scorecard and referenced guides.
    Authoring manifest/archive are excluded: the active final reward does not read
    them. Harness/broker integrity and the reward consumer also need host review;
    their code is listed separately rather than claiming this packet suffices.
    """
    data = Path(data).resolve()
    package = data.parent.parent
    scorecard = json.loads((data / 'scorecard.json').read_text())
    files = set(data.parent.glob('*.py'))
    files.update((data / 'probes').glob('*.py'))
    files.update(data / name for name in ('scorecard.json', 'expected.json', 'irrigation_expected.json'))
    for entry in scorecard['entries']:
        files.update(package / scorecard['documentation_root'] / doc.split('#')[0]
                     for doc in entry['documentation'])
    rows = []
    for path in sorted(files):
        contents = path.read_bytes()
        rows.append({'path': str(path.relative_to(package)), 'bytes': len(contents),
                     'lines': len(contents.splitlines()), 'sha256': hashlib.sha256(contents).hexdigest()})
    integration = [package / 'environment.py', package / 'task.py']
    integration.extend((package / 'harness').glob('*.py'))
    integration.extend((package / 'visibility').glob('*.py'))
    integration.extend((package / 'adapters').rglob('*.py'))
    integration.extend(package / 'adapters' / 'docker' / name
                       for name in ('Dockerfile', 'adapter.json'))
    integration.extend(package / 'host_only' / 'tools' / name
                       for name in ('runtime.py', 'live_log.py', 'fresh_rollout.py'))
    integration_rows = []
    for path in sorted(set(integration)):
        contents = path.read_bytes()
        integration_rows.append({'path': str(path.relative_to(package)), 'bytes': len(contents),
                                 'lines': len(contents.splitlines()),
                                 'sha256': hashlib.sha256(contents).hexdigest()})
    return {'contracts': len(scorecard['entries']),
            'points': sum(entry['weight'] for entry in scorecard['entries']),
            'static_programs': len(list((data / 'probes').glob('*.py'))),
            'dynamic_programs': 2, 'randomized_static_replacements': 1,
            'bytes': sum(row['bytes'] for row in rows),
            'lines': sum(row['lines'] for row in rows), 'files': rows,
            'integration_files': integration_rows,
            'integration_bytes': sum(row['bytes'] for row in integration_rows),
            'integration_lines': sum(row['lines'] for row in integration_rows)}
