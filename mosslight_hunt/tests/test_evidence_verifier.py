"""Offline checks that rescored evidence remains tied to captured actions."""
import json
import shutil

import pytest

from mosslight_hunt.grader.weights import manifest_weights
from mosslight_hunt.host_only.tools.verify_evidence import (
    REPO, read_json, sha256, verify, verify_file_manifest, verify_replay,
)

PACKAGE = REPO / 'mosslight_hunt/host_only/evidence/current'


def test_published_current_evidence_verifies_without_legacy_scoring():
    assert len(verify(PACKAGE, REPO)) == 3


def test_regrade_manifest_rejects_modified_grade(tmp_path):
    regrade = REPO / read_json(PACKAGE / 'manifest.json')['regrade_package']
    shutil.copytree(regrade, tmp_path / 'regrade')
    grade = tmp_path / 'regrade/run1/grade.json'
    grade.write_text(grade.read_text().replace('"score": 0.0', '"score": 1.0'))
    with pytest.raises(ValueError, match='file hash mismatch: run1/grade.json'):
        verify_file_manifest(tmp_path / 'regrade')


@pytest.mark.parametrize('artifact,mutation,error', [
    ('behavioral_replay.json', 'tree', 'baseline replay verdict/tree differs'),
    ('behavioral_replay.json', 'verdict', 'final replay verdict/tree differs'),
    ('probe_inputs.json', 'descriptor', 'probe descriptor differs: E01'),
    ('probe_inputs.json', 'coverage', 'probe coverage differs'),
])
def test_replay_rejects_semantic_tampering(tmp_path, artifact, mutation, error):
    regrade = REPO / read_json(PACKAGE / 'manifest.json')['regrade_package']
    (tmp_path / 'run1').mkdir()
    for name in ('behavioral_replay.json', 'probe_inputs.json'):
        shutil.copyfile(regrade / 'run1' / name, tmp_path / 'run1' / name)
    path = tmp_path / 'run1' / artifact
    data = read_json(path)
    if mutation == 'tree':
        data[0]['tree_sha256'] = '0' * 64
    elif mutation == 'verdict':
        data[1]['verdicts']['E01'] = False
    elif mutation == 'descriptor':
        data['dynamic_probes'][0]['expected'][0] = 'invalid season'
    else:
        data['all_descriptor_hashes'].pop()
    path.write_text(json.dumps(data))
    provenance = read_json(PACKAGE / 'run1/provenance.json')
    summary = read_json(regrade / 'provenance.json')['runs'][0]
    with pytest.raises(ValueError, match=error):
        verify_replay(tmp_path, 'run1', manifest_weights(), provenance, summary)


def test_recaptured_manifest_cannot_rewrite_original_source_provenance(tmp_path):
    package = tmp_path / 'evidence'
    shutil.copytree(PACKAGE, package)
    source = package / 'run1/source_hashes.json'
    data = read_json(source)
    data['pristine_files']['mosslight/engine.py'] = '0' * 64
    source.write_text(json.dumps(data))
    manifest = read_json(package / 'manifest.json')
    manifest['files']['run1/source_hashes.json'] = sha256(source.read_bytes())
    (package / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='pinned file differs: .*run1/source_hashes.json'):
        verify(package, REPO)
