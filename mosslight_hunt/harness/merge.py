"""Line-based three-way merge for stale-base parallel commits (stdlib only).

base is the file the action's shell started from, theirs is the current head and
ours is the action's result. Non-overlapping hunks from both sides are combined.
Hunks that overlap or touch the same base position conflict unless both sides
made the identical change there. Conflicts are never written into a file: the
caller keeps the head version and reports the conflict.
"""
from __future__ import annotations

from difflib import SequenceMatcher

# Bound quadratic diff work; larger concurrently edited files are reported as conflicts.
MAX_MERGE_BYTES = 1024 * 1024


def _hunks(base, other):
    """Changed base ranges [start, end) with their replacement lines."""
    matcher = SequenceMatcher(None, base, other, autojunk=False)
    return [(i1, i2, other[j1:j2]) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != 'equal']


def _apply(base, start, end, hunks):
    """base[start:end] with hunks (all inside that range) applied."""
    out, position = [], start
    for i1, i2, lines in hunks:
        out.extend(base[position:i1])
        out.extend(lines)
        position = i2
    out.extend(base[position:end])
    return out


def merge_lines(base, ours, theirs):
    """Return merged lines, or None when the two sides' edits conflict."""
    if ours == theirs or theirs == base:
        return list(ours)
    if ours == base:
        return list(theirs)
    tagged = sorted([(i1, i2, lines, 0) for i1, i2, lines in _hunks(base, ours)] +
                    [(i1, i2, lines, 1) for i1, i2, lines in _hunks(base, theirs)],
                    key=lambda hunk: (hunk[0], hunk[1]))
    # Cluster hunks whose base ranges overlap or touch (including insertions at one point).
    clusters = []
    for hunk in tagged:
        if clusters and hunk[0] <= clusters[-1]['end']:
            clusters[-1]['end'] = max(clusters[-1]['end'], hunk[1])
            clusters[-1]['hunks'].append(hunk)
        else:
            clusters.append({'start':hunk[0], 'end':hunk[1], 'hunks':[hunk]})
    merged, position = [], 0
    for cluster in clusters:
        start, end = cluster['start'], cluster['end']
        merged.extend(base[position:start])
        sides = [[(i1, i2, lines) for i1, i2, lines, side in cluster['hunks'] if side == which]
                 for which in (0, 1)]
        if sides[0] and sides[1]:
            mine, head = _apply(base, start, end, sides[0]), _apply(base, start, end, sides[1])
            if mine != head:
                return None
            merged.extend(mine)
        else:
            merged.extend(_apply(base, start, end, sides[0] or sides[1]))
        position = end
    merged.extend(base[position:])
    return merged


def merge_text(base, ours, theirs):
    """Three-way merge of bytes. Returns merged bytes, or None on conflict/undecodable input."""
    if ours == theirs or theirs == base:
        return ours
    if ours == base:
        return theirs
    if max(len(base), len(ours), len(theirs)) > MAX_MERGE_BYTES:
        return None
    try:
        split = [value.decode('utf-8').splitlines(keepends=True) for value in (base, ours, theirs)]
    except UnicodeDecodeError:
        return None
    merged = merge_lines(*split)
    return None if merged is None else ''.join(merged).encode('utf-8')


def merge_mode(base, ours, theirs):
    """Three-way merge of permission bits; None on conflicting mode changes."""
    if ours == theirs or theirs == base:
        return ours
    if ours == base:
        return theirs
    return None
