"""Host process attestations; structural checks cannot prove semantic relevance.

Only an explicit host review awards credit. The caller first authenticates the
ledger and snapshots. Reviewers must examine outputs, source transitions and
guide passages for each contract; exit status and populated claims prove nothing.
"""
from pathlib import PurePosixPath
from .submission_contract import PACKAGE_SUFFIXES

ASPECTS = {'reproduction': 8, 'diagnosis': 8, 'verification': 4}


def _location(value, source=False):
    if not isinstance(value, str):
        return False
    path, separator, line = value.partition(':')
    p = PurePosixPath(path)
    return (bool(path) and not p.is_absolute() and '..' not in p.parts
            and path == p.as_posix() and not any(ord(c) < 32 for c in path)
            and (not separator or (line.isdigit() and int(line) > 0))
            and ((p.parts[0] == 'mosslight' and p.suffix in PACKAGE_SUFFIXES)
                 if source else (len(p.parts) == 1 and p.suffix in ('.md', '.toml'))))


def _completed_actions(records):
    pending, completed = {}, {}
    for record in records:
        key = ('id', record['action_id']) if record.get('action_id') else ('agent', record.get('agent'))
        if record.get('type') == 'action_started':
            pending[key] = record
        elif record.get('type') in ('action_completed', 'action_discarded', 'action_ended_competition'):
            start = pending.pop(key, None)
            if (record['type'] == 'action_completed' and start
                    and record.get('agent') == start.get('agent')
                    and record.get('action') == start.get('action')
                    and record['sequence'] > start['sequence']):
                completed[start['sequence']] = (start, record)
    return completed


def review_process(records, audit_head, participant, repaired_defects, review=None):
    """Validate one audit-bound host review; omissions/malformed input stay pending.

    ``entries`` contains exactly one ``defect_id`` for each surviving repair.
    Each aspect is {verified: bool}; true also needs reason/evidence_sequences.
    Diagnosis additionally cites documentation/source locations. Evidence and
    repair_sequence refer to action_started sequences, never untrusted claims.
    """
    verdicts = {}
    try:
        if not isinstance(review, dict) or review.get('audit_head') != audit_head:
            raise ValueError('Missing process review or stale protected audit head')
        if review.get('agent') != participant or not isinstance(review.get('entries'), list):
            raise ValueError('Process review needs an actor and entries list')
        completed = _completed_actions(records)

        def evidence(sequence):
            if type(sequence) is not int or sequence not in completed:
                raise ValueError('Evidence must reference a completed action-start sequence')
            start, end = completed[sequence]
            observation = end.get('observation')
            if (start.get('agent') != participant or start['action'].get('tool') != 'shell'
                    or end.get('rejection') or not isinstance(observation, dict)
                    or type(observation.get('exit_code')) is not int
                    or observation.get('truncated') or observation.get('error')):
                raise ValueError('Evidence must be an actor-authenticated completed shell action')
            return start, end

        for entry in review['entries']:
            if not isinstance(entry, dict):
                raise ValueError('Process entry must be an object')
            defect = entry.get('defect_id')
            if not isinstance(defect, str) or defect not in repaired_defects or defect in verdicts:
                raise ValueError('Unknown, unrepaired or duplicate process contract')
            verdicts[defect] = {}
            repair = None
            for aspect in ASPECTS:
                decision = entry.get(aspect)
                if not isinstance(decision, dict) or type(decision.get('verified')) is not bool:
                    raise ValueError('Every process aspect needs a boolean host decision')
                verdicts[defect][aspect] = decision['verified']
                if not decision['verified']:
                    continue
                if repair is None:
                    repair = evidence(entry.get('repair_sequence'))
                    if (not isinstance(repair[1].get('before'), str) or not repair[1]['before']
                            or not isinstance(repair[1].get('after'), str) or not repair[1]['after']
                            or repair[1]['before'] == repair[1]['after']
                            or not any(_location(p, True) for p in repair[1].get('changed_paths', []))):
                        raise ValueError('Repair evidence must commit a source transition')
                reason, refs = decision.get('reason'), decision.get('evidence_sequences')
                if (not isinstance(reason, str) or not reason.strip()
                        or not isinstance(refs, list) or not refs):
                    raise ValueError('Positive process decisions require reasons and action evidence')
                pairs = [evidence(sequence) for sequence in refs]
                if aspect == 'reproduction' and any(end['sequence'] >= repair[0]['sequence'] for _, end in pairs):
                    raise ValueError('Reproduction must complete before the repair action starts')
                if aspect == 'verification' and any(start['sequence'] <= repair[1]['sequence'] for start, _ in pairs):
                    raise ValueError('Verification must start after the repair commits')
                if aspect == 'diagnosis':
                    for field, source in (('documentation', False), ('source', True)):
                        locations = decision.get(field)
                        if not isinstance(locations, list) or not locations or not all(_location(p, source) for p in locations):
                            raise ValueError('Diagnosis needs admitted documentation and source locations')
                    if any(start['sequence'] > repair[0]['sequence'] for start, _ in pairs):
                        raise ValueError('Diagnosis evidence must precede or accompany the repair')
            if repair is not None:
                verdicts[defect]['repair_sequence'] = entry['repair_sequence']
        if set(verdicts) != set(repaired_defects):
            raise ValueError('Process review is incomplete for surviving repairs')
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        return {'complete': False, 'error': str(error), 'verdicts': {}, 'basis': 'host_evidence_attestation'}
    return {'complete': True, 'error': None, 'verdicts': verdicts, 'basis': 'host_evidence_attestation'}


def weighted_score(weights, repaired_defects, verdicts):
    """Use integer hundredths so complete process and repair credit equals 1.0."""
    units = sum(weights[defect] * (80 + sum(value for aspect, value in ASPECTS.items()
                if verdicts.get(defect, {}).get(aspect) is True)) for defect in repaired_defects)
    return units / (100 * sum(weights.values())) if weights else 0.0
