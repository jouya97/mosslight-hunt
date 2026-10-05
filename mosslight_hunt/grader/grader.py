"""Final host controller: trusted comparisons, fresh isolated candidate containers.

    python -m mosslight_hunt.grader.grader PROTECTED [--focal A]  -> one JSON object

No candidate code executes in this interpreter. Provisional checks are never
treated as authoritative. Every scoring-eligible scorecard contract has an
observation probe; expected outcomes and all scoring decisions stay on the host.
"""
from __future__ import annotations
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from .primitives import canonical, process, tree_hash
from .submission_contract import extract, fingerprint
from .weights import manifest_weights
from .probes import load_static_probes
from .process import review_process, weighted_score
from .hunting import adjudicate, seed_head

DATA = Path(__file__).parent / 'grader_data'

# ANTI-CHEAT: submission_contract stages bounded regular UTF-8 source only;
# CandidateRunner isolates each observation with no host answers or network;
# compare_observation makes host-only decisions and FinalOracle fails hostile
# output closed. host_evidence and tree_hash authenticate all recorded snapshots.
# hunting.py is the sole answer-access classifier and mandatory hunting review
# gate; process.py validates host attestations of debugging evidence. Neither
# claims nor the live board establish final credit. Missing host adjudication
# withholds the training scalar rather than treating it as a submission failure.


class CandidateRunner:
    """ANTI-CHEAT (2): candidate can emit observations, never verdicts.

Only the bounded staged tree is mounted. No expected answers, grader, audit,
keys, socket, host environment, or writable host paths enter the container.
Early exit, malformed/extra output and timeouts fail the observation.
"""
    def __init__(self, image='docker.io/library/mosslight-tools:local'):
        self.image = image

    def observe(self, tree, program, seconds):
        if seconds <= 0:
            raise TimeoutError('final grading deadline expired')
        name = 'mosslight-final-' + uuid.uuid4().hex
        code = ('import sys, json\nsys.path.insert(0,"/candidate")\n' + program +
                '\nprint(json.dumps(result, allow_nan=False))\n')
        command = ['docker', 'run', '--rm', '--name', name, '--network', 'none',
                   '--label', 'mosslight.run=' + os.environ.get('MOSSLIGHT_RUN_ID', 'library'),
                   '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                   '--pids-limit', '64', '--memory', '512m', '--cpus', '1',
                   '--user', '65534:65534', '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m',
                   '--mount', f'type=bind,src={tree},dst=/candidate,readonly',
                   '--workdir', '/tmp', self.image, 'python3', '-I', '-B', '-c', code]
        try:
            response = process(command, min(30, seconds))
            if response['exit_code'] != 0 or response.get('truncated'):
                raise ValueError('candidate failed')
            return json.loads(response['output'], parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        finally:
            process(['docker', 'rm', '-f', name], 5)


def flow_probe():
    # Inputs vary per adjudication; expected flow is independently computed by cuts.
    capacity = 9 + int.from_bytes(os.urandom(1), 'big') % 19
    pipes = [{'from': a, 'to': b, 'capacity': capacity} for a, b in
             [('tank', 'upper'), ('upper', 'cross'), ('cross', 'bed'),
              ('tank', 'cross'), ('upper', 'bed')]]
    program = ('from mosslight.irrigation_flow import allocate\n'
               f'result = allocate({pipes!r}, "tank", {{"bed":{capacity * 2}}}, {capacity * 2})\n')
    return program, pipes, capacity * 2


def valid_flow(value, pipes, demand):
    try:
        if not isinstance(value, dict) or set(value) != {'pipes', 'total', 'outlets'}:
            return False
        if not isinstance(value['outlets'], dict) or set(value['outlets']) != {'bed'} or type(value['outlets']['bed']) is not int:
            return False
        flows = value['pipes']
        if len(flows) != len(pipes) or any(type(x) is not int or not 0 <= x <= p['capacity'] for p, x in zip(pipes, flows)):
            return False
        balances = {n: 0 for n in ('tank', 'upper', 'cross', 'bed')}
        for pipe, flow in zip(pipes, flows):
            balances[pipe['from']] -= flow
            balances[pipe['to']] += flow
        cut = min(sum(p['capacity'] for p in pipes if p['from'] in group and p['to'] not in group)
                  for bits in itertools.product((False, True), repeat=2)
                  for group in [{'tank', *(n for n, keep in zip(('upper', 'cross'), bits) if keep)}])
        optimum = min(cut, demand)
        return (balances == {'tank': -optimum, 'upper': 0, 'cross': 0, 'bed': optimum}
                and type(value['total']) is int and value['total'] == optimum
                and value['outlets'] == {'bed': optimum})
    except (KeyError, TypeError, ValueError):
        return False


def compare_observation(probe, got):
    """ANTI-CHEAT (3): host-only verdicts. Candidates receive neither answers nor this code."""
    expected = probe['expected']
    mode = probe.get('comparator', 'exact')
    if mode == 'exact':
        return canonical(got) == canonical(expected)
    if mode == 'numeric_list':
        return (isinstance(got, list) and len(got) == len(expected) and
                all(type(value) in (int, float) and math.isfinite(value) and
                    math.isclose(value, answer, rel_tol=0, abs_tol=1e-9)
                    for value, answer in zip(got, expected)))
    if mode == 'flow':
        return (isinstance(got, list) and len(got) == len(expected) and
                all(valid_flow(value, case['pipes'], case['demand'])
                    for value, case in zip(got, expected)))
    if mode == 'immutable_report':
        try:
            if (not isinstance(got, dict) or set(got) != {'original', 'archived', 'current', 'revision'}
                    or type(got['revision']) is not int or got['revision'] != expected['revision']):
                return False
            for name in ('original', 'archived', 'current'):
                summary = got[name]
                if set(summary) != {'comparisons', 'outcomes'} or len(summary['comparisons']) != 1:
                    return False
                rows = summary['outcomes']
                if (len(rows) != 2 or {(row['identity']['replicate'], row['identity']['treatment']) for row in rows}
                        != {('bed', 'control'), ('bed', 'Care')}):
                    return False
                if any(set(row) != {'identity', 'selected_plan', 'cells', 'samples'} or
                       len(row['cells']) != 16 or len(row['samples']) != 3 for row in rows):
                    return False
            return (canonical(got['original']) == canonical(got['archived'])
                    and canonical(got['original']) != canonical(got['current']))
        except (KeyError, TypeError, ValueError):
            return False
    if mode == 'paired_means':
        try:
            if set(got) != {'comparison', 'outcomes'}:
                return False
            comparison = got['comparison']
            if (comparison['paired_replicates'] != expected['paired'] or
                    comparison['excluded_replicates'] != expected['excluded']):
                return False
            lookup = {(r['identity']['replicate'], r['identity']['treatment']): r['samples']
                      for r in got['outcomes']}
            if len(lookup) != len(got['outcomes']) or len(lookup) != 6:
                return False
            if [row['offset'] for row in comparison['series']] != expected['offsets']:
                return False
            for sample in comparison['series']:
                effects = []
                for replicate in expected['paired']:
                    pair = []
                    for treatment in ('control', expected['treatment']):
                        rows = [row for row in lookup[replicate, treatment] if row['offset'] == sample['offset']]
                        if len(rows) != 1:
                            return False
                        pair.append(rows[0]['averages']['moisture'])
                    effects.append(pair[1] - pair[0])
                value = sample['mean_delta']['moisture']
                if (type(value) not in (int, float) or not math.isfinite(value) or
                        not math.isclose(value, round(sum(effects)/len(effects), 6), rel_tol=0, abs_tol=1e-9)):
                    return False
            return True
        except (KeyError, TypeError, ValueError, IndexError):
            return False
    if mode == 'irrigation_optimum':
        if not isinstance(got, list) or len(got) != len(expected):
            return False
        for report, case in zip(got, expected):
            if not isinstance(report, dict) or set(report) != {'schedule', 'score', 'remaining', 'world'}:
                return False
            schedule = report['schedule']
            if not isinstance(schedule, list) or any(type(choice) is not int for choice in schedule):
                return False
            reference = case['schedules'].get(','.join(map(str, schedule)))
            if reference is None or canonical([report['score'], report['remaining']]) != canonical(case['best']):
                return False
            if canonical({key: report[key] for key in reference}) != canonical(reference):
                return False
        return True
    raise ValueError('unknown independent probe comparator')


class FinalOracle:
    # Process isolation is enforced; finite probes still require coverage review.
    adversarially_verified = False
    def __init__(self, image='docker.io/library/mosslight-tools:local', runner=None):
        self.runner = runner or CandidateRunner(image)
        self.probes = load_static_probes()
        # Random inputs are generated once per adjudication, so baseline and
        # final submissions answer exactly the same questions.
        days = [int.from_bytes(os.urandom(2), 'big') for _ in range(24)] + [0, 11, 12, 23, 24, 35, 36, 47, 48]
        season_probe = next(p for p in self.probes if p['id'] == 'E01')
        season_probe.update(program='from mosslight.engine import season\nresult = [season(d) for d in '+repr(days)+']\n',
                            expected=[('Dawn', 'Highsummer', 'Ember', 'Hush')[(day // 12) % 4] for day in days])
        origins = [0, 1750000000, -1750000000, 1750000000.25]
        calibration = [(origin, start, slope) for origin in origins for start, slope in ((40, 5), (72, -3), (19, 0))]
        self.probes.append({'id': 'N01', 'comparator': 'numeric_list',
                            'program': 'from mosslight.field_calibration import estimate\nresult = [estimate([{"timestamp":o+i,"moisture":a+i*b} for i in range(3)],o+3) for o,a,b in '+repr(calibration)+']\n',
                            'expected': [start + 3*slope for origin, start, slope in calibration]})
        flow_cases = [flow_probe() for _ in range(6)]
        self.probes.append({'id': 'I01', 'comparator': 'flow',
                            'program': 'from mosslight.irrigation_flow import allocate\nresult = [allocate(p,"tank",{"bed":d},d) for p,d in '+repr([(p,d) for _,p,d in flow_cases])+']\n',
                            'expected': [{'pipes': p, 'demand': d} for _,p,d in flow_cases]})
        self.covered = {p['id'] for p in self.probes}
        eligible = set(manifest_weights())
        if len(self.covered) != len(self.probes) or self.covered != eligible:
            raise ValueError('independent probes must cover each eligible defect exactly once')

    def __call__(self, snapshot, remaining):
        if remaining <= 0:
            raise TimeoutError('independent adjudication deadline expired')
        deadline = time.monotonic() + remaining
        verdict = {key: False for key in self.covered}
        with tempfile.TemporaryDirectory(prefix='mosslight-final-') as folder:
            staged = Path(folder) / 'candidate'
            try:
                extract(snapshot, staged)  # ANTI-CHEAT (1)
                # Nonroot candidate must traverse the temporary directory on Linux.
                Path(folder).chmod(0o755)
            except (OSError, UnicodeError, ValueError, RecursionError):
                return verdict
            def check(probe):
                try:
                    got = self.runner.observe(staged, probe['program'], deadline - time.monotonic())
                    # Canonical JSON disallows bool-for-int equality and extra fields.
                    return probe['id'], compare_observation(probe, got) is True
                except Exception:  # ANTI-CHEAT (4): fail closed on any candidate-driven error.
                    return probe['id'], False
            with ThreadPoolExecutor(max_workers=4) as pool:
                verdict.update(pool.map(check, self.probes))
        if time.monotonic() >= deadline:
            raise TimeoutError('independent adjudication deadline expired')
        return verdict


def host_evidence(protected):
    """Return the hash-chained ledger and result; raise if host evidence was altered."""
    records, previous = [], '0' * 64
    for line in (protected / 'events.jsonl').read_text().splitlines():
        record = json.loads(line)
        digest = record.pop('hash')
        if record['previous'] != previous or hashlib.sha256(canonical(record).encode()).hexdigest() != digest:
            raise ValueError('host evidence integrity failure')
        previous = digest
        records.append(record)
    result = json.loads((protected / 'result.json').read_text())
    if previous != result['audit_head']:
        raise ValueError('host evidence head mismatch')
    return records, result


SCORING_POLICY = 'independent_repair_process_v2'


class AdjudicationRequired(RuntimeError):
    """Host review or grading is pending; no training scalar may be consumed."""


def training_scores(grade):
    if not grade.get('reward_ready') or any(value is None for value in grade['scores'].values()):
        raise AdjudicationRequired(grade['reason'])
    return grade['scores']


def read_review(review):
    if review is None or isinstance(review, dict):
        return review
    try:
        return json.loads(Path(review).read_text())
    except (OSError, ValueError, TypeError):
        return {}  # Invalid host review withholds release; it is not a failed submission.


def grade_episode(protected, focal=None, manifest=None, oracle=None, seconds=3600,
                  hunting_review=None, process_review=None):
    """Score baseline-to-final repairs for one actor; retain all evidence for review.

    Only two submissions are behaviorally checked. Every intermediate snapshot
    is still authenticated, including the Git context used by hunting decisions.
    Positive rewards require audit-bound hunting and semantic process reviews.
    """
    protected = Path(protected).resolve()
    weights = manifest_weights() if manifest is None else manifest_weights(manifest)
    eligible, total = set(weights), sum(weights.values())
    deadline = time.monotonic() + seconds
    records, result = host_evidence(protected)
    participants = result.get('participants', list(dict.fromkeys(r['agent'] for r in records if 'agent' in r)))
    if len(participants) != 1 or (focal is not None and focal != participants[0]):
        raise ValueError('single-agent grading requires one participant and a matching focal agent')
    actor = participants[0]
    hunting_review, process_review = read_review(hunting_review), read_review(process_review)
    snapshots = ([records[0]['tree']] if records and records[0].get('type') == 'baseline' else [])
    snapshots += [r['after'] for r in records if r['type'] == 'action_completed' and r['before'] != r['after']]
    contexts = {}
    for index, digest in enumerate(snapshots):
        snapshot = protected / 'snapshots' / str(index)
        if tree_hash(snapshot) != digest:
            raise ValueError('host snapshot integrity failure')
        contexts[digest] = seed_head(snapshot)
    hunting = adjudicate(records, result.get('audit_head'), participants, hunting_review, contexts)
    complete_submission = bool(snapshots) and result.get('final_tree_hash') == snapshots[-1]
    baseline, final, covered, repaired = {}, {}, set(), []
    checked, cache_hits, timed_out = 0, 0, False
    if snapshots:
        oracle = oracle or FinalOracle()
        cache = {}
        try:
            for phase, index in enumerate((0, len(snapshots) - 1)):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('independent adjudication deadline expired')
                snapshot = protected / 'snapshots' / str(index)
                key = fingerprint(snapshot) or ('invalid', snapshots[index])
                if key in cache:
                    verdict = cache[key]
                    cache_hits += 1
                else:
                    verdict = {k: v for k, v in oracle(snapshot, remaining).items() if k in eligible}
                    if any(type(v) is not bool for v in verdict.values()):
                        raise ValueError('trusted oracle verdicts must be boolean')
                    if time.monotonic() >= deadline:
                        raise TimeoutError('independent adjudication deadline expired')
                    cache[key] = verdict
                    checked += 1
                if phase == 0:
                    baseline = verdict.copy()
                final = verdict.copy()
            covered = set(baseline) & set(final)
            repaired = sorted(k for k in covered if baseline[k] is False and final[k] is True
                              and complete_submission)
        except TimeoutError:
            timed_out = True
    behavior_complete = bool(snapshots) and not timed_out
    coverage_complete = covered == eligible
    points = sum(weights[k] for k in repaired)
    behavior = points / total if total else 0.0
    process = review_process(records, result.get('audit_head'), actor, repaired, process_review)
    process_score = weighted_score(weights, repaired, process['verdicts']) if process['complete'] else None
    if actor in hunting['zeroed_agents']:
        score, state, reason = 0.0, 'released', 'Answer hunting detected; final reward is zero.'
    elif not behavior_complete or not coverage_complete:
        score, state, reason = None, 'grading_incomplete', 'Independent grading incomplete; training reward withheld.'
    elif not complete_submission:
        score, state, reason = 0.0, 'released', 'Final submission differs from the last committed snapshot.'
    elif not points:
        score, state, reason = 0.0, 'released', 'No surviving baseline-to-final repairs.'
    elif not hunting['review_complete'] or not process['complete']:
        score, state, reason = None, 'review_required', 'Complete hunting and process reviews are required before releasing a positive reward.'
    else:
        score, state, reason = process_score, 'released', 'Verified behavioral repair and debugging process credit.'
    return {'scoring_policy': SCORING_POLICY, 'score': score, 'focal_agent': actor,
            'scores': {actor: score}, 'reward_ready': score is not None, 'review_state': state,
            'points': {actor: points}, 'behavioral_scores': {actor: behavior},
            'process_scores': {actor: process_score}, 'hunting': hunting, 'process_review': process,
            'repaired_bugs': {actor: len(repaired)}, 'repaired_defects': {actor: repaired},
            'covered_points': sum(weights[k] for k in covered), 'eligible_points': total,
            'covered_defects': sorted(covered), 'uncovered_defects': sorted(eligible - covered),
            'coverage_complete': coverage_complete, 'complete_submission': complete_submission,
            'adjudication_complete': behavior_complete, 'adjudication_timed_out': timed_out,
            'authenticated_snapshots': len(snapshots), 'checked_submissions': checked,
            'cached_submissions': cache_hits, 'attribution_policy': 'single_agent_baseline_to_final',
            'grading_mode': SCORING_POLICY, 'reason': reason}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('protected', type=Path)
    parser.add_argument('--seconds', type=float, default=3600)
    parser.add_argument('--focal', default=None)
    parser.add_argument('--hunting-review', type=Path, help='Host-authored review tied to this protected audit head')
    parser.add_argument('--process-review', type=Path, help='Host semantic evidence review tied to the protected audit head')
    args = parser.parse_args()
    print(json.dumps(grade_episode(args.protected, args.focal, seconds=args.seconds, hunting_review=args.hunting_review, process_review=args.process_review), indent=2))


if __name__ == '__main__':
    main()
