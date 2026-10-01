"""Rebuild grader_data/reference_solution/solve.sh from the defect manifest.

Each manifest entry records the clean text (`old`) and the seeded text (`new`)
for every replacement. The reference repair replaces the seeded text with the
clean text in the agent-visible checkout. host_only/patches/*.patch run the
other way: each seeds one defect into host_only/clean_baseline (all 119 apply
there). Reversed against the visible checkout, which also carries the other 118
seeds and omits many docstrings and comments, 21 of them miss their context;
the manifest text applies to all. N01's seed also inlined the centered timestamp
offsets that its `old` text still uses, so its repair restores that setup line.
The build checks that every seeded text occurs exactly once, in order, in a
fresh visible checkout.
"""
import json
from pathlib import Path
import tempfile

from mosslight_hunt.grader.weights import DEFAULT_MANIFEST
from mosslight_hunt.visibility.build import build_agent_tree

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'grader/grader_data/reference_solution/solve.sh'
N01_SETUP = ('    center = math.fsum(t - origin for t, _ in values)/len(values)\n',
             '    xs = [t - origin for t, _ in values]\n    center = math.fsum(xs)/len(xs)\n')
HEADER = '''#!/bin/sh
# Reference solution: repair all 119 seeded defects in the agent-visible checkout.
#   sh solve.sh [CHECKOUT]    (default: $WORKDIR, else /workspace)
# Each EDITS row is [defect, file, seeded text, repaired text]: the manifest's
# `new` -> `old` replacement, plus N01's centered-offset setup line. Every seeded
# text must occur exactly once when its row is applied, so a second run fails.
# Rebuild: python3 -B -m mosslight_hunt.grader.tests.build_reference_solution
set -eu
cd "${1:-${WORKDIR:-/workspace}}"
python3 -B -c '
import json, sys
from pathlib import Path
for ident, name, seeded, repaired in json.load(sys.stdin):
    path = Path(name)
    text = path.read_bytes().decode("utf-8")
    if text.count(seeded) != 1:
        sys.exit(f"{ident}: seeded text is not unique in {name}")
    path.write_bytes(text.replace(seeded, repaired, 1).encode("utf-8"))
' <<'EDITS'
'''


def edits():
    rows = []
    for entry in json.loads(DEFAULT_MANIFEST.read_text())['entries']:
        for change in entry.get('replacements', [entry]):
            rows.append([entry['id'], change['file'], change['new'], change['old']])
        if entry['id'] == 'N01':
            rows.append(['N01', entry['file'], *N01_SETUP])
    return rows


def build():
    rows = edits()
    with tempfile.TemporaryDirectory() as folder:
        tree = Path(folder) / 'visible'
        build_agent_tree(ROOT / 'mosslight', tree)
        for ident, name, seeded, repaired in rows:
            path = tree / name
            text = path.read_text()
            if text.count(seeded) != 1:
                raise ValueError(f'{ident}: seeded text is not unique in the visible {name}')
            path.write_text(text.replace(seeded, repaired, 1))
    body = '[\n' + ',\n'.join(json.dumps(row) for row in rows) + '\n]\n'
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(HEADER + body + 'EDITS\n')
    OUTPUT.chmod(0o755)
    print('solve.sh:', len(rows), 'edits for', len({row[0] for row in rows}), 'defects')


if __name__ == '__main__':
    build()
