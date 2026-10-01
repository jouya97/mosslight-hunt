#!/usr/bin/env python3
"""Host-only manifest audit. No model calls, no network, no Docker.

    python3 host_only/verify.py --check E01 --tree PATH   reproduce one defect check
    python3 host_only/verify.py                           rewrite verification.json

Every manifest check must pass on clean_baseline and fail on seeded_snapshot, and
the clean tree's public test suite must pass. Checks import the tree under test, so
run them only against trusted trees, never against a candidate submission.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HOST = Path(__file__).resolve().parent
MANIFEST = HOST.parent / 'grader' / 'grader_data' / 'manifest.json'
CLEAN, SEEDED = HOST / 'clean_baseline', HOST / 'seeded_snapshot'
ENV = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}


def check(ident, tree):
    source = f'import sys\nsys.path.insert(0, {str(tree)!r})\n' + (HOST / 'checks' / f'{ident}.py').read_text()
    result = subprocess.run([sys.executable, '-B', '-c', source], cwd=tree, env=ENV,
                            text=True, capture_output=True, timeout=60)
    return result.returncode, result.stdout[-3000:], result.stderr[-5000:]


def tree_sha256(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in Path(root).rglob('*') if p.is_file() and '__pycache__' not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def audit():
    ids = [entry['id'] for entry in json.loads(MANIFEST.read_text())['entries']]
    with ThreadPoolExecutor(max_workers=8) as pool:
        clean = dict(zip(ids, pool.map(lambda i: check(i, CLEAN)[0] == 0, ids)))
        seeded = dict(zip(ids, pool.map(lambda i: check(i, SEEDED)[0] != 0, ids)))
    tests = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests'],
                           cwd=CLEAN, env=ENV, text=True, capture_output=True, timeout=600)
    return {
        'count': len(ids),
        'clean_passed': sum(clean.values()),
        'seeded_failed': sum(seeded.values()),
        'clean_public_tests': {'returncode': tests.returncode, 'tail': tests.stderr.strip().splitlines()[-3:]},
        'clean_tree_sha256': tree_sha256(CLEAN),
        'seeded_tree_sha256': tree_sha256(SEEDED),
        'manifest_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        'entries': {i: {'clean_passed': clean[i], 'seeded_failed': seeded[i]} for i in ids},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', metavar='ID')
    parser.add_argument('--tree', type=Path)
    args = parser.parse_args()
    if args.check:
        if args.tree is None:
            parser.error('--check requires --tree')
        code, out, err = check(args.check, args.tree.resolve())
        print(out, end=''); print(err, end='', file=sys.stderr)
        return code
    report = audit()
    (HOST / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    ok = (report['clean_passed'] == report['seeded_failed'] == report['count']
          and report['clean_public_tests']['returncode'] == 0)
    print(json.dumps({k: v for k, v in report.items() if k != 'entries'}, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
