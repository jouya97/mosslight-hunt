"""What the grader consumes from each replayed snapshot, declared once.

The shared checkout is the submission. The broker snapshots it after every
committed action; the final grader (and the provisional board) stages each
snapshot through ``extract`` before any probe runs. agent_data/SUBMISSION.md
states the same rules to competitors. Keep this module stdlib-only.

The limits are part of the contract. Competitors can leave anything in the
checkout (tests, caches, notes, claims, a vendored copy of some tool), so only
named source and document types cross the boundary, as regular UTF-8 files under
the caps below. The visible application is 59 admitted files and about 345 KiB,
the largest 25 KiB; the caps leave room for honest growth and no more. Snapshots
are immutable and host-owned, and nothing here imports, executes, unpacks or
follows a candidate symlink. Unadmitted files are ignored. Anything outside the
contract raises ValueError (or OSError/UnicodeError), which the grader turns
into a failed verdict for every probe: 0 points, never an exception.
"""
from pathlib import Path
import os
import stat

SUBMISSION_ROOT = '/workspace'        # the shared checkout inside agent containers
PACKAGE = 'mosslight'                 # application package directory
PACKAGE_SUFFIXES = ('.py', '.js', '.css', '.html')   # admitted anywhere under PACKAGE/
DOCUMENT_SUFFIXES = ('.md', '.toml')  # admitted only at the top level
REQUIRED_FILE = 'mosslight/__init__.py'
MAX_FILE_BYTES = 1024 * 1024
MAX_SUBMISSION_BYTES = 4 * 1024 * 1024
MAX_FILES = 256


def admitted(relative):
    p = Path(relative)
    return (not p.is_absolute() and '..' not in p.parts and
            ((p.parts[0] == PACKAGE and p.suffix in PACKAGE_SUFFIXES) or
             (len(p.parts) == 1 and p.suffix in DOCUMENT_SUFFIXES)))


def extract(source, destination):
    """ANTI-CHEAT (1): copy admitted files to ``destination``; return the inventory or raise."""
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_dir():
        raise ValueError('missing regular submission directory')
    destination.mkdir(parents=True, exist_ok=False)
    inventory, total = [], 0
    for directory, dirs, files in os.walk(source, followlinks=False):
        root = Path(directory)
        if any((root / name).is_symlink() for name in dirs):
            raise ValueError('symlink directory')
        for name in sorted(files):
            path = root / name
            relative = path.relative_to(source).as_posix()
            if not admitted(relative):
                continue
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                    raise ValueError('nonregular or oversized submission file')
                with os.fdopen(fd, 'rb', closefd=False) as stream:
                    data = stream.read(MAX_FILE_BYTES + 1)
                data.decode('utf-8')
            finally:
                os.close(fd)
            total += len(data)
            if len(data) > MAX_FILE_BYTES or total > MAX_SUBMISSION_BYTES or len(inventory) >= MAX_FILES:
                raise ValueError('submission exceeds limits')
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            inventory.append(relative)
    if REQUIRED_FILE not in inventory:
        raise ValueError('missing application package')
    return inventory


def fingerprint(source):
    """Hash exactly the validated files probes consume, excluding Git metadata/tests.

    Invalid submissions return None and must never share a passing cache entry.
    Full snapshot integrity is verified separately against the protected ledger.
    """
    import tempfile
    from .primitives import tree_hash
    with tempfile.TemporaryDirectory(prefix='mosslight-submission-hash-') as folder:
        staged = Path(folder) / 'candidate'
        try:
            extract(source, staged)
        except (OSError, UnicodeError, ValueError, RecursionError):
            return None
        return tree_hash(staged)
