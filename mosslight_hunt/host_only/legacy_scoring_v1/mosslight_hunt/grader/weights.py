"""Single scoring policy for provisional and final points.

Tiered scoring uses the manifest level for both the live board and final grader.
"""
import json
from pathlib import Path

LEVEL_WEIGHTS = {'normal': 1, 'hard': 5, 'extreme': 10, 'legendary': 20}
DEFAULT_MANIFEST = Path(__file__).resolve().parent / 'grader_data' / 'manifest.json'


def manifest_weights(manifest=DEFAULT_MANIFEST):
    entries = json.loads(Path(manifest).read_text())['entries']
    if any(e['level'] not in LEVEL_WEIGHTS for e in entries):
        raise ValueError('unknown defect level')
    weights = {e['id']: LEVEL_WEIGHTS[e['level']] for e in entries}
    if len(weights) != len(entries):
        raise ValueError('duplicate defect IDs')
    return weights
