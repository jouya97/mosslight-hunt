"""Scoring weights from the small runtime contract scorecard.

The private injection manifest remains an authoring/legacy input. It is never
needed to decide the default final reward. Explicit manifest paths keep their
historical tier conversion for evidence verification and fixture repair tools.
"""
import json
from pathlib import Path

LEVEL_WEIGHTS = {'normal': 1, 'hard': 5, 'extreme': 10, 'legendary': 20}
DATA = Path(__file__).resolve().parent / 'grader_data'
DEFAULT_MANIFEST = DATA / 'manifest.json'
DEFAULT_SCORECARD = DATA / 'scorecard.json'


def manifest_weights(manifest=DEFAULT_SCORECARD):
    entries = json.loads(Path(manifest).read_text())['entries']
    weights = {}
    for entry in entries:
        if 'weight' in entry:
            weight = entry['weight']
            if type(weight) is not int or weight <= 0:
                raise ValueError('contract weights must be positive integers')
        else:
            if entry['level'] not in LEVEL_WEIGHTS:
                raise ValueError('unknown defect level')
            weight = LEVEL_WEIGHTS[entry['level']]
        if not isinstance(entry['id'], str) or not entry['id']:
            raise ValueError('contract IDs must be nonempty strings')
        if entry['id'] in weights:
            raise ValueError('duplicate defect IDs')
        weights[entry['id']] = weight
    if not weights:
        raise ValueError('scorecard cannot be empty')
    return weights
