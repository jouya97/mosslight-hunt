"""Stage the pinned public application history, never the experiment repository."""
from pathlib import Path
import hashlib
import json
import subprocess

BUNDLE = Path(__file__).resolve().parents[1] / 'host_only/fixtures/mosslight.bundle'
PUBLIC_ORIGIN = 'https://github.com/jouya97/mosslight.git'
SUBMISSION_NOTICE = Path(__file__).resolve().parents[1] / 'agent_data/SUBMISSION.md'


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          capture_output=True, text=True, timeout=30).stdout.strip()


def inventory(root):
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlink in Git seed')
        if path.is_file():
            data = path.read_bytes()
            files.append({'path':path.relative_to(root).as_posix(), 'size':len(data),
                          'sha256':hashlib.sha256(data).hexdigest()})
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'format_version':1, 'tree_sha256':digest, 'files':files}


def build_git_seed(destination):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    subprocess.run(['git', 'clone', '--quiet', '--template=', '--branch', 'main',
                    str(BUNDLE), str(destination)], check=True, capture_output=True, timeout=30)
    git(destination, 'remote', 'set-url', 'origin', PUBLIC_ORIGIN)
    git(destination, 'config', 'user.name', 'Mosslight Maintainer')
    git(destination, 'config', 'user.email', 'maintainer@mosslight.invalid')
    head = git(destination, 'rev-parse', 'HEAD')
    pristine = git(destination, 'rev-parse', 'v0.1.0^{commit}')
    if head != git(destination, 'rev-parse', 'v0.2.0^{commit}'):
        raise ValueError('Git seed must start at the pinned buggy release')
    if git(destination, 'status', '--porcelain'):
        raise ValueError('Git seed must have a clean working tree')
    # The host-maintained submission notice is authoritative for each fresh run.
    # Keep application commits intact and inventory the visible working-tree edit.
    if SUBMISSION_NOTICE.is_symlink() or not SUBMISSION_NOTICE.is_file():
        raise ValueError('Submission notice must be a regular host file')
    notice = SUBMISSION_NOTICE.read_bytes()
    notice.decode('utf-8')
    (destination / 'SUBMISSION.md').write_bytes(notice)
    result = inventory(destination)
    result['git'] = {'origin':PUBLIC_ORIGIN, 'buggy_commit':head, 'pristine_commit':pristine,
                     'bundle_sha256':hashlib.sha256(BUNDLE.read_bytes()).hexdigest(),
                     'submission_notice_sha256':hashlib.sha256(notice).hexdigest(),
                     'condition':'pristine_history_visible'}
    return result
