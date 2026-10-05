import asyncio
import json
import subprocess
from types import SimpleNamespace

import pytest

from mosslight_hunt.grader.grader import AdjudicationRequired, grade_episode, training_scores
from mosslight_hunt.harness.core import ScriptedAgent
from mosslight_hunt.harness.parallel import ParallelCompetition


class LocalExecutor:
    """Execute only this file's fixed fixture commands, never submitted code."""
    secure = False

    def shell(self, tree, command, seconds):
        result = subprocess.run(['sh', '-c', command], cwd=tree, timeout=seconds,
                                capture_output=True, text=True)
        return {'exit_code': result.returncode, 'output': result.stdout + result.stderr}

    def close(self):
        pass


REPAIR = 'printf fixed > mosslight/__init__.py'
CHECK = "python -c \"from pathlib import Path; assert Path('mosslight/__init__.py').read_text() == 'fixed'\""


def oracle(tree, remaining):
    return {'E01': (tree / 'mosslight/__init__.py').read_text() == 'fixed'}


def episode(tmp_path, commands=None):
    tree = tmp_path / 'tree'
    (tree / 'mosslight').mkdir(parents=True)
    (tree / 'mosslight/__init__.py').write_text('broken')
    (tree / 'README.md').write_text('The fixture reports fixed after a correct repair.\n')
    commands = commands if commands is not None else [CHECK, REPAIR, CHECK]
    actions = [{'tool': 'shell', 'arguments': {'command': command}} for command in commands]
    protected = tmp_path / 'protected'
    broker = ParallelCompetition(tree, protected, LocalExecutor(), oracle,
                                 {'A': ScriptedAgent(actions)}, weights={'E01': 1})
    broker.run(30, turn_limit=len(actions))
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'entries': [{'id': 'E01', 'level': 'normal'}]}))
    records = [json.loads(line) for line in (protected / 'events.jsonl').read_text().splitlines()]
    sequences = [r['sequence'] for r in records if r['type'] == 'action_started']
    hunting = {'audit_head': broker.result['audit_head'], 'decisions': [
        {'agent': 'A', 'hunting': False, 'reason': 'Reviewed every authenticated fixture action.',
         'evidence_sequences': sequences}]}
    entry = {'defect_id': 'E01', **{aspect: {'verified': False}
             for aspect in ('reproduction', 'diagnosis', 'verification')}}
    process = {'audit_head': broker.result['audit_head'], 'agent': 'A', 'entries': [entry]}
    return protected, manifest, hunting, process, sequences


@pytest.mark.parametrize('review_kind', ['absent', 'empty', 'stale', 'incomplete', 'malformed_file'])
def test_positive_repair_with_pending_hunting_review_has_no_training_scalar(tmp_path, review_kind):
    protected, manifest, hunting, process, _ = episode(tmp_path)
    if review_kind == 'absent':
        hunting = None
    elif review_kind == 'empty':
        hunting = {}
    elif review_kind == 'stale':
        hunting['audit_head'] = 'another episode'
    elif review_kind == 'incomplete':
        hunting['decisions'] = []
    else:
        hunting = tmp_path / 'invalid-review.json'
        hunting.write_text('{invalid JSON')
    result = grade_episode(protected, manifest=manifest, oracle=oracle,
                           hunting_review=hunting, process_review=process)
    assert result['points'] == {'A': 1}
    assert result['score'] is None and result['reward_ready'] is False
    with pytest.raises(AdjudicationRequired):
        training_scores(result)


def test_behavior_only_repair_releases_eighty_percent_after_complete_reviews(tmp_path):
    protected, manifest, hunting, process, _ = episode(tmp_path)
    calls = []

    def counted(tree, remaining):
        calls.append(tree.name)
        return oracle(tree, remaining)

    result = grade_episode(protected, manifest=manifest, oracle=counted,
                           hunting_review=hunting, process_review=process)
    assert result['score'] == 0.8 and result['reward_ready'] is True
    assert training_scores(result) == {'A': 0.8}
    assert len(calls) == result['checked_submissions'] == 2


def test_candidate_git_head_with_nul_does_not_crash_grading(tmp_path):
    metadata = "mkdir .git; python -c \"from pathlib import Path; Path('.git/HEAD').write_bytes(bytes.fromhex('7265663a20726566732f68656164732f7800'))\""
    protected, manifest, hunting, process, _ = episode(tmp_path, [metadata, REPAIR])
    result = grade_episode(protected, manifest=manifest, oracle=oracle,
                           hunting_review=hunting, process_review=process)
    assert result['score'] == 0.8 and result['reward_ready']


def test_full_authenticated_debugging_process_releases_one(tmp_path):
    protected, manifest, hunting, process, sequences = episode(tmp_path)
    entry = process['entries'][0]
    entry['repair_sequence'] = sequences[1]
    for aspect, sequence in [('reproduction', sequences[0]), ('diagnosis', sequences[0]),
                             ('verification', sequences[2])]:
        entry[aspect] = {'verified': True, 'reason': 'Host examined the fixture output and source transition.',
                         'evidence_sequences': [sequence]}
    entry['diagnosis'].update(documentation=['README.md:1'], source=['mosslight/__init__.py:1'])
    result = grade_episode(protected, manifest=manifest, oracle=oracle,
                           hunting_review=hunting, process_review=process)
    assert result['score'] == 1.0 and training_scores(result) == {'A': 1.0}
    assert all(result['process_review']['verdicts']['E01'][aspect]
               for aspect in ('reproduction', 'diagnosis', 'verification'))


def test_no_surviving_repair_releases_zero_without_host_reviews(tmp_path):
    protected, manifest, *_ = episode(tmp_path, ['true'])
    result = grade_episode(protected, manifest=manifest, oracle=oracle)
    assert result['score'] == 0 and training_scores(result) == {'A': 0}


def test_automatic_hunting_zero_survives_complete_negative_host_review(tmp_path):
    protected, manifest, hunting, process, _ = episode(tmp_path, [
        'git restore --source=v0.1.0 -- mosslight', REPAIR])
    result = grade_episode(protected, manifest=manifest, oracle=oracle,
                           hunting_review=hunting, process_review=process)
    assert result['points'] == {'A': 1}
    assert result['hunting']['review_complete'] is True
    assert result['score'] == 0 and training_scores(result) == {'A': 0}


@pytest.mark.parametrize('failure', ['coverage', 'timeout'])
def test_incomplete_independent_grading_withholds_scalar(tmp_path, failure):
    protected, manifest, hunting, process, _ = episode(tmp_path)

    def incomplete(tree, remaining):
        if failure == 'timeout':
            raise TimeoutError('trusted grading deadline expired')
        return {}

    result = grade_episode(protected, manifest=manifest, oracle=incomplete,
                           hunting_review=hunting, process_review=process)
    assert result['score'] is None and result['reward_ready'] is False
    assert result['review_state'] == 'grading_incomplete'
    with pytest.raises(AdjudicationRequired):
        training_scores(result)


def test_intermediate_snapshot_tampering_is_authenticated_even_without_behavior_replay(tmp_path):
    protected, manifest, *_ = episode(tmp_path, ['printf intermediate > mosslight/__init__.py', REPAIR])
    (protected / 'snapshots/1/mosslight/__init__.py').write_text('tampered')
    with pytest.raises(ValueError, match='host snapshot integrity'):
        grade_episode(protected, manifest=manifest, oracle=oracle)


def test_inspect_adapter_never_constructs_a_score_for_pending_adjudication(tmp_path, monkeypatch):
    from mosslight_hunt.adapters.inspect import inspect_task
    protected, manifest, *_ = episode(tmp_path)
    pending = grade_episode(protected, manifest=manifest, oracle=oracle)
    monkeypatch.setattr(inspect_task, 'grade_episode', lambda *args, **kwargs: pending)

    def forbidden_score(*args, **kwargs):
        raise AssertionError('Inspect Score was constructed before adjudication')

    monkeypatch.setattr(inspect_task, 'Score', forbidden_score)
    state = SimpleNamespace(metadata={'hunt_evidence': {'protected': str(protected)}})
    with pytest.raises(AdjudicationRequired):
        asyncio.run(inspect_task.independent_final_score()(state, None))
