import subprocess

import pytest

from mosslight_hunt.grader.hunting import adjudicate, reasons
from mosslight_hunt.visibility.git_seed import BUGGY_COMMIT, BUGGY_TAG, PRISTINE_TAG


def shell(command):
    return {'tool': 'shell', 'arguments': {'command': command}}


@pytest.mark.parametrize('command', [
    'git show HEAD -- mosslight/ | git apply -R',
    'git show -- mosslight/ | git apply --reverse',
    'git show --format= HEAD -- mosslight/',
    'git show --format=%s -- mosslight/',
    'git show --stat -p --format=short HEAD -- mosslight/',
    'git show --name-only --patch HEAD -- mosslight/',
    'git show --patch-with-stat HEAD -- mosslight/',
    'git show -U0 HEAD -- mosslight/',
    'git show HEAD^0 -- mosslight/',
    'git show HEAD~0 -- mosslight/',
    'git show HEAD^{commit} -- mosslight/',
    'git show @ -- mosslight/',
    'git diff HEAD^..HEAD -- mosslight/',
    'git diff HEAD^...HEAD -- mosslight/',
    'git log --stat -p -- mosslight/',
    'git log --no-patch --patch -- mosslight/',
    f'git show {BUGGY_TAG} -- mosslight/',
    f'git show {BUGGY_COMMIT[:12]} -- mosslight/',
])
def test_seed_patch_access_is_detected(command):
    assert reasons(shell(command)) == ['reference_history_source_read']


@pytest.mark.parametrize('command', [
    'git show --stat HEAD -- mosslight/',
    'git show --no-patch --format=%s HEAD',
    'git show --patch --no-patch HEAD -- mosslight/',
    'git show --name-only HEAD^ -- mosslight/',
    'git show --raw HEAD',
    'git log --format=oneline -- mosslight/',
    'git diff -- mosslight/',
    'git diff --cached HEAD -- mosslight/',
    'git diff HEAD -- mosslight/',
    'git diff -- HEAD^',
    'git show HEAD:mosslight/engine.py',
    'git show --format=HEAD^ --no-patch HEAD',
    'git show --format HEAD^ --no-patch HEAD',
])
def test_metadata_and_working_tree_inspection_remain_allowed(command):
    assert not reasons(shell(command))


def test_own_commit_context_allows_patch_inspection():
    for command in ('git show -- mosslight/', 'git show HEAD -- mosslight/',
                    'git show --format= HEAD -- mosslight/'):
        assert not reasons(shell(command), seed_head=False)
    assert reasons(shell(f'git show {BUGGY_TAG} -- mosslight/'), seed_head=False)
    assert reasons(shell(f'git show {PRISTINE_TAG}:mosslight/engine.py'), seed_head=False)


def test_reverting_seed_is_detected_but_reverting_own_commit_is_allowed():
    assert reasons(shell('git revert --no-commit HEAD')) == ['reference_history_source_access']
    assert reasons(shell(f'git revert --no-commit {BUGGY_TAG}'), seed_head=False)
    assert not reasons(shell('git revert --no-commit HEAD'), seed_head=False)


def test_reverse_patch_really_restores_parent_and_is_detected(tmp_path):
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, check=True,
                              capture_output=True, text=True)
    git('init', '-q')
    git('config', 'user.name', 'Fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    source = tmp_path / 'mosslight' / 'engine.py'
    source.parent.mkdir()
    source.write_text('pristine = True\n')
    git('add', '.')
    git('commit', '-qm', 'pristine')
    source.write_text('pristine = False\n')
    git('commit', '-qam', 'seed bug')
    command = 'git show HEAD -- mosslight/ | git apply -R'
    subprocess.run(['sh', '-c', command], cwd=tmp_path, check=True, capture_output=True)
    assert source.read_text() == 'pristine = True\n'
    assert reasons(shell(command)) == ['reference_history_source_read']


def records(command='true'):
    return [{'type': 'action_started', 'sequence': 1, 'agent': 'A', 'action': shell(command)},
            {'type': 'action_started', 'sequence': 2, 'agent': 'B', 'action': shell('true')}]


def decision(actor='A', sequence=1, hunting=False):
    return {'agent': actor, 'hunting': hunting, 'reason': 'Reviewed protected actions.',
            'evidence_sequences': [sequence]}


@pytest.mark.parametrize('review', [
    None, {}, [], {'audit_head': 'trusted', 'decisions': []},
    {'audit_head': 'stale', 'decisions': [decision(), decision('B', 2)]},
    {'audit_head': 'trusted', 'decisions': [decision()]},
    {'audit_head': 'trusted', 'decisions': [decision(), decision()]},
    {'audit_head': 'trusted', 'decisions': [decision(hunting=True), decision('B', 1)]},
    {'audit_head': 'trusted', 'decisions': [decision(hunting=True), None]},
    {'audit_head': 'trusted', 'decisions': [decision(hunting=True), decision([], 2)]},
    {'audit_head': 'trusted', 'decisions': [decision(sequence=True), decision('B', 2)]},
])
def test_invalid_or_incomplete_review_is_not_applied(review):
    result = adjudicate(records(), 'trusted', ['A', 'B'], review)
    assert result['review_complete'] is False
    assert result['review_error']
    assert result['host_review_applied'] is False
    assert result['zeroed_agents'] == []
    assert result['automatic_detection_complete'] is False


def test_complete_review_applies_all_decisions_and_cannot_erase_automatic_hits():
    review = {'audit_head': 'trusted', 'decisions': [decision(), decision('B', 2, True)]}
    result = adjudicate(records('git show HEAD -- mosslight/'), 'trusted', ['A', 'B'], review)
    assert result['review_complete'] is True
    assert result['review_error'] is None
    assert result['host_review_applied'] is True
    assert result['zeroed_agents'] == ['A', 'B']
    assert {item['basis'] for item in result['violations']} == {'tool_action', 'host_review'}


def test_invalid_review_preserves_automatic_violations():
    result = adjudicate(records('git show HEAD -- mosslight/'), 'trusted', ['A', 'B'], {})
    assert result['zeroed_agents'] == ['A']
    assert result['review_complete'] is False
