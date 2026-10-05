"""Process rewards require host decisions and authenticated action evidence."""
import copy
import unittest

from mosslight_hunt.grader.process import review_process, weighted_score


def action(sequence, before='seed', after='seed', tool='shell', agent='A', action_id=None):
    command = {'tool': tool, 'arguments': {'command': f'command {sequence}'}}
    start = {'type': 'action_started', 'sequence': sequence, 'agent': agent,
             'before': before, 'action': command}
    end = {'type': 'action_completed', 'sequence': sequence + 1, 'agent': agent,
           'before': before, 'after': after, 'action': command,
           'changed_paths': ['mosslight/engine.py'] if before != after else [],
           'observation': {'exit_code': 0, 'output': 'observed relevant behavior'}}
    if action_id is not None:
        start['action_id'] = end['action_id'] = action_id
    return [start, end]


def review(verified=True):
    decision = {'verified': verified}
    if verified:
        decision.update(reason='Reviewer checked contract-specific command and output.',
                        evidence_sequences=[1])
    entry = {'defect_id': 'E01', 'repair_sequence': 3,
             'reproduction': copy.deepcopy(decision),
             'diagnosis': copy.deepcopy(decision),
             'verification': copy.deepcopy(decision)}
    if verified:
        entry['diagnosis'].update(documentation=['BEHAVIORS.md:29'], source=['mosslight/engine.py:12'])
        entry['verification']['evidence_sequences'] = [5]
    return {'audit_head': 'authenticated-head', 'agent': 'A', 'entries': [entry]}


class ProcessReviewTests(unittest.TestCase):
    def setUp(self):
        self.records = action(1) + action(3, after='fixed') + action(5, before='fixed', after='fixed')

    def checked(self, host_review, records=None, repaired=('E01',)):
        return review_process(self.records if records is None else records,
                              'authenticated-head', 'A', repaired, host_review)

    def test_valid_host_attestation_and_integer_scoring(self):
        checked = self.checked(review())
        self.assertTrue(checked['complete'], checked['error'])
        self.assertEqual(checked['basis'], 'host_evidence_attestation')
        self.assertEqual(weighted_score({'E01': 5}, ['E01'], checked['verdicts']), 1.0)
        self.assertEqual(weighted_score({'E01': 5, 'E02': 5}, ['E01'], checked['verdicts']), 0.5)
        self.assertEqual(weighted_score({'E01': 5}, [], checked['verdicts']), 0)

    def test_negative_decisions_need_no_evidence_and_earn_behavior_credit(self):
        checked = self.checked(review(False), records=[])
        self.assertTrue(checked['complete'])
        self.assertEqual(weighted_score({'E01': 5}, ['E01'], checked['verdicts']), 0.8)
        self.assertTrue(self.checked({'audit_head': 'authenticated-head', 'agent': 'A', 'entries': []}, repaired=[])['complete'])

    def test_missing_stale_partial_and_malformed_reviews_stay_pending(self):
        invalid = [None, [], {}, {'audit_head': 'stale'}, review(False)]
        invalid[-1]['entries'] = []
        for value in invalid:
            with self.subTest(value=value):
                checked = self.checked(value)
                self.assertFalse(checked['complete'])
                self.assertEqual(checked['verdicts'], {})
        for mutate in (lambda r: r.update(agent='B'),
                       lambda r: r['entries'].append(copy.deepcopy(r['entries'][0])),
                       lambda r: r['entries'][0].update(defect_id='not-repaired'),
                       lambda r: r['entries'][0]['diagnosis'].update(verified=1),
                       lambda r: r['entries'][0]['verification'].update(reason='   ')):
            value = review()
            mutate(value)
            self.assertFalse(self.checked(value)['complete'])

    def test_short_concrete_review_reasons_are_valid(self):
        value = review()
        for aspect in ('reproduction', 'diagnosis', 'verification'):
            value['entries'][0][aspect]['reason'] = 'Output matches spec.'
        self.assertTrue(self.checked(value)['complete'])

    def test_claims_rejected_failed_and_other_actor_actions_are_not_evidence(self):
        for mutate in (lambda r: r[0].update(agent='B'),
                       lambda r: r[1].update(agent='B'),
                       lambda r: r[1].update(type='action_discarded'),
                       lambda r: r[1].update(rejection='conflict'),
                       lambda r: r[1]['observation'].update(error='did not execute'),
                       lambda r: r[1]['observation'].update(truncated=True),
                       lambda r: r[1]['observation'].update(exit_code=True),
                       lambda r: r[0]['action'].update(tool='claim')):
            records = copy.deepcopy(self.records)
            mutate(records)
            self.assertFalse(self.checked(review(), records)['complete'])
        value = review()
        value['entries'][0]['reproduction']['evidence_sequences'] = [True]
        self.assertFalse(self.checked(value)['complete'])
        value['entries'][0]['reproduction']['evidence_sequences'] = [2]
        self.assertFalse(self.checked(value)['complete'])

    def test_source_change_and_chronology_required(self):
        for mutate in (lambda r: r[3].update(changed_paths=['.git/index']),
                       lambda r: r[3].pop('before'),
                       lambda r: r[3].pop('after'),
                       lambda r: r[3].update(after='seed'),
                       lambda r: r[3].update(type='action_discarded')):
            records = copy.deepcopy(self.records)
            mutate(records)
            self.assertFalse(self.checked(review(), records)['complete'])
        for aspect, sequence in (('reproduction', 3), ('verification', 3), ('diagnosis', 5)):
            value = review()
            value['entries'][0][aspect]['evidence_sequences'] = [sequence]
            self.assertFalse(self.checked(value)['complete'])

    def test_invalid_diagnosis_paths_fail_closed_without_reading_candidate(self):
        for field, location in (('source', '/tmp/mosslight/engine.py'),
                                ('source', 'mosslight/../engine.py'),
                                ('source', 'mosslight/engine.py:0'),
                                ('source', 'mosslight/engine.py:12:13'),
                                ('documentation', '../BEHAVIORS.md'),
                                ('documentation', 'mosslight/engine.py')):
            value = review()
            value['entries'][0]['diagnosis'][field] = [location]
            self.assertFalse(self.checked(value)['complete'])

    def test_action_ids_must_match_and_interrupted_attempts_cannot_pair(self):
        records = action(1, action_id='repro') + action(3, after='fixed', action_id='repair') + action(5, before='fixed', after='fixed', action_id='verify')
        self.assertTrue(self.checked(review(), records)['complete'])
        records[1]['action_id'] = 'someone-else'
        self.assertFalse(self.checked(review(), records)['complete'])
        records = copy.deepcopy(self.records)
        records[1]['action'] = {'tool': 'shell', 'arguments': {'command': 'unrelated action'}}
        self.assertFalse(self.checked(review(), records)['complete'])


if __name__ == '__main__':
    unittest.main()
