"""Concurrent actions, isolated workspaces, and ordered host-owned commits.

Arbitrary shell commands never write the canonical checkout. Each action starts
from its latest committed state; only changed regular files are published after
its container has stopped and its merged candidate has been graded. A file that
another commit changed after the action started is three-way merged by lines; if
the edits overlap, the head version is kept and the result carries a conflict notice.
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from .core import (TOOL_SCHEMAS, Competition, SHELL_SECONDS, TOOLS, UNKNOWN_TOOL, WEB_SEARCH_FAILED, WEB_SEARCH_UNCONFIGURED,
                   argument_error, known_tool, tree_hash, recent_action, repair_summary, status_viewed, work_board)
from .merge import merge_mode, merge_text
from .credit import LIVE_POLICY, update_live_owners

# Countdown notices. The result of this actor's k-th completed action (1-based) carries
# the number of actions that remain AFTER it: remaining = turn_limit - k. A notice is
# attached at 20 remaining, then at every count from 10 through 1, strictly below
# turn_limit. For turn_limit=150: action 130 -> "20 actions remaining", actions
# 131..139 carry none, action 140 -> "10 actions remaining", ..., action 149 ->
# "1 action remaining"; action 150 (the last) carries none. A count equal to the
# limit is never shown at the start, including for short runs.
# Notices ride on the tool result only; they are recorded in the ledger observation and
# never consume an action.
ACTIONS_REMAINING_COUNTDOWN_FROM = 10


def actions_remaining_text(remaining):
    return f'[Notice: {remaining} action{"" if remaining == 1 else "s"} remaining.]'


ACTIONS_REMAINING_NOTICES = {n: actions_remaining_text(n)
                             for n in (20, *range(ACTIONS_REMAINING_COUNTDOWN_FROM, 0, -1))}


def actions_remaining_notice(turn_limit, used_after):
    """The notice for the action that brings this actor's count to used_after, if any."""
    if turn_limit is None:
        return None
    remaining = turn_limit - used_after
    if remaining in ACTIONS_REMAINING_NOTICES and remaining < turn_limit:
        return ACTIONS_REMAINING_NOTICES[remaining]
    return None


# A shell command's own limit. Overrunning it fails only that action; the contest's
# global deadline (the agent-time budget) still ends the contest as `safety_deadline`.
TIMEOUT_EXIT_CODE = 124
TIMEOUT_ERROR = f'Command timed out after {SHELL_SECONDS} seconds.'
# Per-action rejections of workspace states the shared checkout cannot hold.
SPECIAL_FILE_REJECTION = ('Only regular files and directories are allowed in the shared checkout; '
                          "this action's changes were not applied.")
UNREADABLE_REJECTION = ('Unreadable files or directories are not allowed in the shared checkout; '
                        "this action's changes were not applied.")
FILE_NAME_REJECTION = ('File names must be valid UTF-8 in the shared checkout; '
                       "this action's changes were not applied.")
# Relative paths are bounded so every host copy (workspace, candidate, snapshot, publication)
# stays well inside the host's PATH_MAX (1024 bytes on macOS).
MAX_PATH_BYTES = 512
PATH_LENGTH_REJECTION = (f'File paths must be at most {MAX_PATH_BYTES} bytes long in the shared checkout; '
                         "this action's changes were not applied.")
# A symlink in an action's workspace ends the contest for everyone (stop reason `symlink`);
# every participant is told only this.
COMPETITION_ENDED = {'message':'The repair session has ended.'}


class WorkspaceRejected(ValueError):
    """An action left its workspace in a state the shared checkout cannot hold."""
    def __init__(self, error, path):
        super().__init__(f'{error} ({path})')
        self.error, self.path = error, path


def display_path(relative):
    """A ledger-safe (UTF-8 encodable) form of a relative path, even for undecodable names."""
    return relative.encode('utf8', 'surrogateescape').decode('utf8', 'backslashreplace')


def find_symlinks(tree):
    """Every symlink under tree, without following any.

    Unreadable directories, and entries that cannot be inspected (a directory without
    search permission), are skipped: file_inventory then rejects the action as unreadable."""
    found = []
    for folder, directories, files in os.walk(tree):
        for name in directories + files:
            path = Path(folder) / name
            try:
                link = path.is_symlink()
            except OSError:
                continue
            if link:
                found.append(display_path(path.relative_to(tree).as_posix()))
    return sorted(found)


def tracked_mode(mode):
    """The mode the shared checkout keeps: as in git, only the owner's executable bit counts.

    Every file is stored as 0o644 or 0o755, so no committed mode change (e.g. `chmod a-w`)
    can block a later write by the host or by another participant."""
    return 0o755 if mode & 0o100 else 0o644


def file_inventory(tree):
    """Validate first; compare bytes and modes, never execute candidate content.

    Special files, unreadable entries, undecodable names and over-long paths raise
    WorkspaceRejected. Modes are recorded as tracked_mode.
    Callers check symlinks first (find_symlinks); one found here is a plain ValueError.
    """
    result = {}
    pending = [tree]
    while pending:
        folder = pending.pop()
        try:
            with os.scandir(folder) as listing:
                entries = list(listing)
        except OSError as exc:
            where = display_path(folder.relative_to(tree).as_posix())
            if isinstance(exc, PermissionError):
                raise WorkspaceRejected(UNREADABLE_REJECTION, where) from None
            if exc.errno == errno.ENAMETOOLONG:
                raise WorkspaceRejected(PATH_LENGTH_REJECTION, where) from None
            raise
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(tree).as_posix()
            try:
                # Without d_type these stat the entry, which needs search permission on folder.
                link = entry.is_symlink()
                directory = not link and entry.is_dir(follow_symlinks=False)
                regular = not link and entry.is_file(follow_symlinks=False)
            except PermissionError:
                raise WorkspaceRejected(UNREADABLE_REJECTION, display_path(relative)) from None
            if link:
                raise ValueError(f'symlinks forbidden in snapshot: {display_path(relative)}')
            try:
                relative.encode('utf8')
            except UnicodeEncodeError:
                raise WorkspaceRejected(FILE_NAME_REJECTION, display_path(relative)) from None
            if len(relative.encode('utf8')) > MAX_PATH_BYTES:
                raise WorkspaceRejected(PATH_LENGTH_REJECTION, relative)
            if directory:
                pending.append(path)
                continue
            if not regular:
                raise WorkspaceRejected(SPECIAL_FILE_REJECTION, relative)
            digest = hashlib.sha256()
            try:
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                mode = entry.stat(follow_symlinks=False).st_mode
            except PermissionError:
                raise WorkspaceRejected(UNREADABLE_REJECTION, relative) from None
            result[relative] = (digest.hexdigest(), tracked_mode(mode))
    return result


def remove_tree(path):
    """Best-effort removal that also clears directories an action made unreadable."""
    try:
        for folder, directories, _ in os.walk(path):
            for name in directories:
                child = os.path.join(folder, name)
                if not os.path.islink(child):
                    os.chmod(child, 0o700)
    except OSError:
        pass
    shutil.rmtree(path, ignore_errors=True)


def conflict_notice(relative):
    return f'[Error: {relative} your change was not applied]'


def write_file(target, mode, *, source=None, content=None):
    """Replace target with source's bytes (or content) at a tracked mode.

    The old file is unlinked first, so its own mode can never block the write."""
    if target.is_file():
        target.unlink()
    if content is None:
        shutil.copy2(source, target)
    else:
        target.write_bytes(content)
    target.chmod(mode)


def integrate_files(candidate, workspace, base, changed, before, after, latest):
    """Apply one action's changes to the latest head copy (candidate).

    before/after are the action workspace inventories at start and end; latest is the
    head inventory; base is a read-only tree identical to the action's starting state.
    A path the head has not changed since the base takes the action's version. A path
    both sides changed is three-way merged by lines when the edits do not overlap and
    is otherwise left at the head version and reported. Returns (merged, conflicts).
    """
    merged, conflicts = [], []
    for relative in sorted(changed, key=lambda p: (p.count('/'), p)):
        source, target = workspace / relative, candidate / relative
        was, ours, head = before.get(relative), after.get(relative), latest.get(relative)
        if head == ours:
            continue  # The head already has exactly this result.
        # A file ancestor at the head (one this action did not delete) blocks the path.
        blocked = any(parent.is_file() for parent in target.parents
                      if parent != candidate and candidate in parent.parents)
        if head != was:
            content = mode = None
            if not blocked and None not in (was, ours, head) and target.is_file():
                mode = merge_mode(was[1], ours[1], head[1])
                original = base / relative
                if mode is not None and original.is_file() and not original.is_symlink():
                    base_bytes = original.read_bytes()
                    if hashlib.sha256(base_bytes).hexdigest() == was[0]:
                        content = merge_text(base_bytes, source.read_bytes(), target.read_bytes())
            if content is None or mode is None:
                conflicts.append(relative)
                continue
            write_file(target, mode, content=content)
            merged.append(relative)
            continue
        if ours is None:
            if target.is_file():
                target.unlink()
            # Another commit may have replaced this old file with a directory.
            # Deleting the old file must not discard new descendants.
            continue
        if blocked:
            conflicts.append(relative)
            continue
        if target.is_dir():
            # Replacing a directory is safe only if the head left its files as in the base.
            inside = relative + '/'
            if any(latest[path] != before.get(path) for path in latest if path.startswith(inside)):
                conflicts.append(relative)
                continue
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        write_file(target, ours[1], source=source)
    return merged, conflicts


class ParallelCompetition(Competition):
    """One action in flight per actor; model calls and shell processes may overlap."""
    def __init__(self, *args, relevance=None, **kwargs):
        super().__init__(*args, relevance=relevance, **kwargs)
        self.lock = threading.RLock()
        self.commit_lock = threading.Lock()
        self.inflight = set()
        self.finished = set()
        self.stopping = False
        self.started = False
        self.result = None
        self.stop_actor = None

    def begin(self, seconds, turn_limit=40):
        if self.started:
            raise ValueError('competition already started')
        if turn_limit is not None and (type(turn_limit) is not int or turn_limit < 1):
            raise ValueError('turn_limit must be a positive integer')
        self.started = True
        self.deadline = time.monotonic() + seconds
        self.turn_limit = turn_limit
        self.turns_used = dict.fromkeys(self.agents, 0)
        self.reason = 'agents_exhausted'
        self.current, self.baseline, self.owners = {}, {}, {}
        self.current_hash = None
        self.work_root = self.protected / 'work'
        self.work_root.mkdir()
        try:
            # The shared checkout holds only tracked modes, so every workspace copy is writable.
            for folder, _, files in os.walk(self.tree):
                for name in files:
                    path = Path(folder) / name
                    if not path.is_symlink():
                        path.chmod(tracked_mode(path.stat().st_mode))
            snapshot, digest = self.snapshot()
            baseline = self.oracle(snapshot, self.remaining())
            self._validate_verdict(baseline)
            self._check_deadline()
            self.baseline, self.current = baseline.copy(), baseline.copy()
            self.current_hash = digest
            self.audit.append({'type':'baseline', 'tree':digest, 'oracle':baseline,
                               'scheduler':'single_agent_transactions',
                               'attribution_policy':LIVE_POLICY, 'status_protocol':self.status_protocol})
        except BaseException as exc:
            self.stop(exc)
            raise

    def remaining(self):
        return self.deadline - time.monotonic()

    def remaining_notice(self, used_after):
        """Instance hook so continuations can change future notices without changing history."""
        return actions_remaining_notice(self.turn_limit, used_after)

    def _check_deadline(self):
        if self.remaining() <= 0:
            raise TimeoutError('competition safety deadline')
        if self.stopping:
            raise InterruptedError('competition stopped')

    def _validate_verdict(self, verdict):
        if any(type(v) is not bool for v in verdict.values()):
            raise ValueError('oracle verdicts must be boolean')
        if self.current_hash is not None and set(verdict) != set(self.baseline):
            raise ValueError('oracle contract changed')

    def view(self, identity):
        with self.lock:
            if identity not in self.agents:
                raise ValueError('unknown participant')
            terminal = (self.stopping or identity in self.finished or
                        self.turn_limit is not None and self.turns_used[identity] >= self.turn_limit)
            return {'identity':identity, 'prompt':self.prompt, 'tools':TOOLS,
                    'observation':self.last_observation.get(identity, {'message':'Begin inspection.'}),
                    'seconds_remaining':self.remaining(), 'terminal':terminal}

    def _points(self):
        return {actor:sum(self.weights.get(bug, 1) for bug, owner in self.owners.items()
                          if owner == actor and self.current.get(bug))
                for actor in self.agents}

    def reject_response(self, identity, response, error):
        with self.lock:
            self.audit.append({'type':'response_rejected', 'agent':identity,
                               'provider_response':response, 'error':error})

    def ended_observation(self):
        """The neutral result owed to any call answered after a symlink ended the contest."""
        with self.lock:
            return dict(COMPETITION_ENDED) if self.reason == 'symlink' else None

    def _end_for_symlink(self, identity, action_id, action, base_hash, symlinks, observation):
        """Stop cleanly: nothing from this action is committed; the last committed head is
        graded as at any other ending. Actions still in flight are discarded as at the deadline."""
        with self.lock:
            self._check_deadline()
            number = self.turns_used[identity] + 1
            ended = dict(COMPETITION_ENDED)
            self.audit.append({'type':'action_ended_competition', 'agent':identity, 'action_id':action_id,
                               'action_number':number, 'action':action,
                               'command':action['arguments'].get('command'), 'symlinks':symlinks,
                               'base':base_hash, 'before':self.current_hash, 'after':self.current_hash,
                               'changed_paths':[], 'shell_observation':observation, 'observation':ended})
            self.audit.append({'type':'competition_stopped', 'stop_reason':'symlink', 'actor':identity,
                               'action_id':action_id, 'action_number':number})
            self.stopping, self.reason, self.stop_actor = True, 'symlink', identity
            self.turns_used[identity] = number
            self.recent.append(recent_action(identity, 'shell'))
            self.last_observation[identity] = ended
            return ended

    def stop(self, error):
        with self.lock:
            if not self.stopping:
                self.stopping = True
                self.reason = ('safety_deadline' if isinstance(error, (TimeoutError, subprocess.TimeoutExpired))
                               else 'error')
                self.audit.append({'type':'error', 'error':str(error), 'reason':self.reason})

    def act(self, identity, action):
        """Called concurrently by independent participant loops; identity is host routing."""
        folder = None
        rejection, changed = None, []
        with self.lock:
            self._check_deadline()
            if self.view(identity)['terminal'] or identity in self.inflight:
                raise ValueError('participant has finished or already has an action in flight')
            if action is None:
                self.audit.append({'type':'agent_finished', 'agent':identity,
                                   'provider_response':getattr(self.agents[identity], 'last_response', None)})
                self.finished.add(identity)
                return None
            if not isinstance(action, dict) or not isinstance(action.get('arguments'), dict):
                raise ValueError('invalid agent action')
            action_id = uuid.uuid4().hex
            base_hash = self.current_hash
            tool, args = action.get('tool'), action['arguments']
            self.audit.append({'type':'action_started', 'agent':identity, 'action_id':action_id,
                               'action':action, 'before':base_hash,
                               'provider_response':getattr(self.agents[identity], 'last_response', None)})
            self.inflight.add(identity)
        invalid = None
        try:
            if known_tool(tool):
                invalid = argument_error(tool, args)
            if invalid is not None:
                # Nothing runs. Like an unknown tool, the call still uses one action.
                observation, changed = {'error':invalid}, []
                rejection = {'reason':'arguments', 'error':invalid}
            elif tool == 'shell':
                # Readers see only complete commits. Copying is protected against publication.
                with self.lock:
                    self._check_deadline()
                    folder = self.work_root / action_id
                    folder.mkdir()
                    workspace = folder / 'workspace'
                    shutil.copytree(self.tree, workspace)
                    base_hash = self.current_hash
                    # The published tree always equals the latest numbered snapshot; that
                    # immutable copy supplies merge bases for this action's stale files.
                    base_tree = self.protected / 'snapshots' / str(self.counter - 1)
                    before_files = file_inventory(workspace)
                limit = min(self.shell_seconds, self.remaining())
                try:
                    observation = self.executor.shell(workspace, args['command'], limit)
                except (TimeoutError, subprocess.TimeoutExpired) as exc:
                    if limit < self.shell_seconds:
                        raise  # The contest's global deadline, not this command's own limit.
                    # Only this action fails. Its workspace is never inventoried or committed.
                    partial = getattr(exc, 'output', None)
                    if isinstance(partial, bytes):
                        partial = partial.decode('utf8', 'replace')
                    observation = {'exit_code':TIMEOUT_EXIT_CODE, 'output':partial or '',
                                   'truncated':bool(getattr(exc, 'truncated', False)), 'error':f'Command timed out after {self.shell_seconds:g} seconds.'}
                    rejection = {'reason':'timeout', 'seconds':self.shell_seconds}
                # DockerShell removes the entire container before returning, including descendants.
                symlinks = find_symlinks(workspace)
                if symlinks:
                    return self._end_for_symlink(identity, action_id, action, base_hash, symlinks, observation)
                if rejection is None:
                    try:
                        after_files = file_inventory(workspace)
                    except WorkspaceRejected as exc:
                        # The workspace is discarded; the next action starts from the head.
                        rejection = {'reason':'workspace', 'error':exc.error, 'path':exc.path}
                        observation = {**observation, 'error':exc.error} if isinstance(observation, dict) \
                            else {'error':exc.error}
                    else:
                        changed = sorted(p for p in before_files.keys() | after_files.keys()
                                         if before_files.get(p) != after_files.get(p))
            elif tool == 'web_search':
                changed = []
                if self.search is None:
                    observation = dict(WEB_SEARCH_UNCONFIGURED)
                else:
                    try:
                        observation = self.search(args['query'], self.remaining())
                    except Exception as exc:
                        # A query the provider refuses, or a provider/network failure, fails only
                        # this action. The contest's global deadline is still checked at commit.
                        observation = {'error':WEB_SEARCH_FAILED}
                        rejection = {'reason':'web_search', 'error':f'{type(exc).__name__}: {exc}'}
            else:
                observation, changed = None, []
            # Commit order is lock acquisition after shell completion. Never serialize shell work.
            with self.commit_lock:
                with self.lock:
                    self._check_deadline()
                    before = self.current_hash
                    if invalid is None and tool == 'claim':
                        self.claims.append({'agent':identity, 'provisional':True,
                                            **{k:args[k] for k in TOOL_SCHEMAS['claim']['properties'] if k in args}})
                        observation = {'recorded':True, 'provisional':True,
                                       'repair_count':{'provisional':True, 'repaired_bugs':repair_summary(identity, self.owners, self.current, self.weights)['your_credited_bugs'], 'total_bugs':len(self.current)}}
                    elif invalid is None and tool == 'status':
                        # The committed provisional work board, read in commit order like a claim.
                        observation = work_board(identity, self.agents, self.owners, self.current,
                                                 self.weights, self.claims, self.recent, self.status_protocol)
                    elif not known_tool(tool):
                        observation = dict(UNKNOWN_TOOL)
                    if changed:
                        candidate = folder / 'candidate'
                        shutil.copytree(self.tree, candidate)
                delta, transfers = {}, {}
                committed_paths, merged_paths, conflicted_paths = [], [], []
                snapshot = None
                after = before
                verdict, owners = self.current.copy(), self.owners.copy()
                if changed:
                    latest_files = file_inventory(candidate)
                    merged_paths, conflicted_paths = integrate_files(
                        candidate, workspace, base_tree, changed, before_files, after_files, latest_files)
                    candidate_files = file_inventory(candidate)
                    committed_paths = sorted(p for p in latest_files.keys() | candidate_files.keys()
                                             if latest_files.get(p) != candidate_files.get(p))
                    after = tree_hash(candidate)
                    if after != before:
                        verdict = self.oracle(candidate, self.remaining())
                        self._validate_verdict(verdict)
                        self._check_deadline()
                        delta = {bug:passed for bug,passed in verdict.items() if passed != self.current[bug]}
                        update_live_owners(self.baseline, self.current, verdict, owners, identity,
                                      committed_paths, self.relevance)
                        transfers = {bug:owner for bug,owner in owners.items()
                                     if self.owners.get(bug) != owner}
                        # Number only committed snapshots; interrupted candidates never enter replay.
                        snapshot = self.protected / 'snapshots' / str(self.counter)
                        candidate.rename(snapshot)
                        try:
                            publication = folder / 'publication'
                            shutil.copytree(snapshot, publication)
                        except BaseException:
                            shutil.rmtree(snapshot)
                            raise
                with self.lock:
                    published = False
                    # One fixed order: conflicts, then the countdown. No score line is attached;
                    # an actor sees provisional scores only on the 'status' work board.
                    notices = [conflict_notice(path) for path in conflicted_paths]
                    countdown = self.remaining_notice(self.turns_used[identity] + 1)
                    if countdown is not None:
                        notices.append(countdown)
                    if notices and isinstance(observation, dict):
                        observation = {**observation, 'notice':'\n'.join(notices)}
                    try:
                        self._check_deadline()
                        if snapshot is not None:
                            backup = folder / 'previous'
                            self.tree.rename(backup)
                            try:
                                publication.rename(self.tree)
                            except BaseException:
                                backup.rename(self.tree)
                                raise
                            published = True
                        self.audit.append({'type':'action_completed', 'agent':identity, 'action_id':action_id,
                                           'action':action, 'base':base_hash, 'before':before, 'after':after,
                                           'changed_paths':committed_paths, 'merged_paths':merged_paths,
                                           'conflicted_paths':conflicted_paths, 'oracle_transitions':delta,
                                           'ownership_transfers':transfers, 'rejection':rejection,
                                           'observation':observation})
                        if invalid is None and tool == 'status':
                            # Exactly what this caller was shown, notices included.
                            self.audit.append(status_viewed(identity, observation, action_id=action_id,
                                                            action_number=self.turns_used[identity] + 1))
                    except BaseException:
                        # Publication and the authenticated completion record form one commit.
                        # No actor can stage a workspace while this lock is held.
                        if published:
                            shutil.rmtree(self.tree)
                            backup.rename(self.tree)
                        if snapshot is not None:
                            shutil.rmtree(snapshot)
                        raise
                    if snapshot is not None:
                        self.current_hash = after
                        self.current, self.owners = verdict, owners
                        self.counter += 1
                    self.turns_used[identity] += 1
                    self.recent.append(recent_action(identity, tool))
                    self.last_observation[identity] = observation
                return observation
        except BaseException as exc:
            with self.lock:
                self.audit.append({'type':'action_discarded', 'agent':identity, 'action_id':action_id,
                                   'action':action, 'reason':str(exc)})
            if not isinstance(exc, InterruptedError):
                self.stop(exc)
            raise
        finally:
            if folder is not None:
                remove_tree(folder)
            with self.lock:
                self.inflight.discard(identity)

    def finish(self):
        """Call after all action workers settle, including cancelled adapter operations."""
        with self.lock:
            if self.result is not None:
                return self.result
            if not self.started:
                self.executor.close()
                self.audit.close()
                return None
            if self.inflight:
                raise RuntimeError('cannot finish while actions are in flight')
            self.stopping = True
            if self.reason == 'agents_exhausted' and self.turn_limit is not None and any(
                    n >= self.turn_limit for n in self.turns_used.values()):
                self.reason = 'turn_limit'
            try:
                self.executor.close()
            except Exception as exc:
                self.reason = 'cleanup_error'
                self.audit.append({'type':'cleanup_error', 'error':str(exc)})
            trusted = getattr(self.oracle, 'adversarially_verified', False)
            no_oracle = getattr(self.oracle, 'no_oracle', False)
            grade = self._points() if self.current_hash is not None else None
            result = {'participants':list(self.agents), 'stop_reason':self.reason, 'stop_actor':self.stop_actor,
                      'scheduler':'single_agent_transactions', 'attribution_policy':LIVE_POLICY,
                      'final_tree_hash':tree_hash(self.tree), 'turn_limit':self.turn_limit,
                      'turns_used':self.turns_used,
                      'verified_score':grade if trusted and not no_oracle else None,
                      'diagnostic_score':grade if not trusted and not no_oracle else None,
                      'provisional_repaired_bugs':sum(not self.baseline.get(bug, True) and passed for bug, passed in self.current.items()),
                      'grading_mode':'offline_smoke_no_oracle' if no_oracle else 'verified' if trusted else 'tamperable_python_checks',
                      'provisional_claims':self.claims, 'audit_head':self.audit.previous}
            self.audit.append({'type':'result', **result})
            result['audit_head'] = self.audit.previous
            self.audit.close()
            (self.protected / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            remove_tree(self.work_root)
            self.result = result
            return result

    def run(self, seconds, turn_limit=40):
        try:
            self.begin(seconds, turn_limit)
            def participant(identity, agent):
                try:
                    while not self.view(identity)['terminal']:
                        view = self.view(identity)
                        action = agent.action({k:v for k,v in view.items() if k != 'identity'}, self.remaining())
                        self.act(identity, action)
                except Exception as exc:
                    if not isinstance(exc, InterruptedError):
                        self.stop(exc)
            with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
                list(pool.map(lambda item: participant(*item), self.agents.items()))
        except Exception as exc:
            self.stop(exc)
        finally:
            self.finish()
        return self.result
