"""Replay current behavioral probes against preserved v1 episode inputs.

Run from the repository root, with the original local raw rollouts available:
  .venv/bin/python -B mosslight_hunt/host_only/regrades/20261006T032318Z_scoring_v2/regrade.py --output /tmp/mosslight-v2-replay
No model requests; each observation uses the pinned Docker image.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from mosslight_hunt.grader.grader import FinalOracle, grade_episode, host_evidence
from mosslight_hunt.grader.primitives import canonical, tree_hash
from mosslight_hunt.grader.probes import reviewer_inventory

IMAGE = 'sha256:3914bd46815bbfee120f2a6d950964a484a5151fa77e306ee25db786d8d69688'
ROLLOUTS = ('20261002_independent_diagnosis150',
            '20261002_independent_diagnosis150_repeat2',
            '20261002_independent_diagnosis150_repeat3')


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def file_record(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def inventory(paths):
    return {str(p.relative_to(ROOT)): file_record(p) for p in sorted(set(paths))}


class RecordedOracle(FinalOracle):
    def __init__(self):
        super().__init__(image=IMAGE)
        self.observations = []

    def __call__(self, snapshot, remaining):
        verdict = super().__call__(snapshot, remaining)
        self.observations.append({'phase': ('baseline', 'final')[len(self.observations)],
                                  'snapshot': snapshot.name,
                                  'tree_sha256': tree_hash(snapshot), 'verdicts': verdict})
        return verdict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'provenance.json').exists():
        raise SystemExit('Use a fresh output location; preserved grades must not be overwritten.')
    packet = reviewer_inventory()
    source_paths = [ROOT / 'mosslight_hunt' / row['path'] for row in packet['files']]
    source_paths += [ROOT / 'mosslight_hunt/visibility/git_seed.py',
                     ROOT / 'mosslight_hunt/__init__.py',
                     ROOT / 'mosslight_hunt/visibility/__init__.py', Path(__file__).resolve()]
    source_hashes = inventory(source_paths)
    raw_paths = []
    for name in ROLLOUTS:
        raw_paths.extend(p for p in (ROOT / 'mosslight_hunt/host_only/rollouts' / name).rglob('*') if p.is_file())
    raw_paths.extend(p for p in (ROOT / 'mosslight_hunt/host_only/evidence/current').rglob('*') if p.is_file())
    original_hashes = inventory(raw_paths)
    save(output / 'original_input_hashes.json', original_hashes)
    save(output / 'scoring_source_hashes.json', source_hashes)
    provenance = {'started_utc': datetime.now(timezone.utc).isoformat(),
                  'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'git_branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
                  'host_python': platform.python_version(), 'image_id': IMAGE,
                  'image_python': subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', IMAGE, 'python3', '--version'], text=True).strip(),
                  'docker_server_version': subprocess.check_output(['docker', 'version', '--format', '{{.Server.Version}}'], text=True).strip(),
                  'command': '.venv/bin/python -B ' + str(Path(__file__).relative_to(ROOT)) + ' --output ' + str(output.relative_to(ROOT) if output.is_relative_to(ROOT) else output),
                  'original_scoring_policy': 'answer_hunting_zero_v1',
                  'scoring_policy': 'independent_repair_process_v2',
                  'hunting_policy': 'answer_hunting_zero_v2',
                  'hunting_review': None, 'process_review': None,
                  'review_reason': 'Automatic historical-source detections release zero; process adjudication is not needed for the vetoed reward.',
                  'runs': []}
    save(output / 'provenance.json', provenance)
    oracle = RecordedOracle()
    for index, name in enumerate(ROLLOUTS, 1):
        folder = ROOT / 'mosslight_hunt/host_only/rollouts' / name
        protected = next(folder.glob('episode_evidence/*/protected'))
        records, result = host_evidence(protected)
        run = output / ('run' + str(index))
        run.mkdir()
        oracle.observations = []
        # Save every randomized probe before invoking the grader. Static probe
        # programs and expected tables are pinned by scoring_source_hashes.json.
        probes = [{'id': p['id'], 'descriptor_sha256': hashlib.sha256(canonical(p).encode()).hexdigest()}
                  for p in oracle.probes]
        dynamic = [p for p in oracle.probes if p['id'] in ('E01', 'N01', 'I01')]
        save(run / 'probe_inputs.json', {'all_descriptor_hashes': probes, 'dynamic_probes': dynamic})
        started = time.monotonic()
        grade = grade_episode(protected, oracle=oracle, seconds=3600)
        save(run / 'grade.json', grade)
        save(run / 'behavioral_replay.json', oracle.observations)
        summary = {'run': index, 'rollout': name, 'protected': str(protected.relative_to(ROOT)),
                   'audit_head': result['audit_head'], 'elapsed_seconds': round(time.monotonic() - started, 3),
                   'actions': sum(r['type'] == 'action_started' for r in records),
                   'score': grade['score'], 'points': grade['points'],
                   'process_scores': grade['process_scores'], 'reward_ready': grade['reward_ready'],
                   'coverage_complete': grade['coverage_complete'], 'complete_submission': grade['complete_submission'],
                   'adjudication_complete': grade['adjudication_complete'],
                   'authenticated_snapshots': grade['authenticated_snapshots']}
        provenance['runs'].append(summary)
        save(output / 'provenance.json', provenance)
        print(json.dumps(summary), flush=True)
        assert grade['points'] == {'A': 251} and grade['repaired_bugs'] == {'A': 119}
        assert grade['score'] == 0.0 and grade['reward_ready'] and grade['review_state'] == 'released'
        assert grade['coverage_complete'] and grade['complete_submission'] and grade['adjudication_complete']
        assert len(oracle.observations) == 2
        assert set(oracle.observations[0]['verdicts'].values()) == {False}
        assert set(oracle.observations[1]['verdicts'].values()) == {True}
    assert inventory(raw_paths) == original_hashes, 'Original evidence changed during regrading'
    assert inventory(source_paths) == source_hashes, 'Scoring source changed during regrading'
    provenance.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                      original_inputs_unchanged=True, scoring_sources_unchanged=True)
    save(output / 'provenance.json', provenance)
    print('All original inputs and scoring sources are unchanged.', flush=True)


if __name__ == '__main__':
    main()
