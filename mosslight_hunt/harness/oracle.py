"""Provisional checks: behavioral evidence, NOT a tamper-proof grading VM.

Each check runs one of the final grader's probe programs on the same staged
submission the grader sees, then judges the observation with the grader's own
comparator INSIDE the candidate's interpreter and reports only an exit code.
On an untampered tree the verdict matches the final grader for every defect ID.
Candidate modules share that interpreter, so they can tamper with the comparison
or exit early (for example with os._exit(0)); human review is mandatory. The
final grader instead compares observations host-side.
"""
import inspect
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from .core import canonical, process
from mosslight_hunt.grader import grader as final
from mosslight_hunt.grader.submission_contract import extract, fingerprint

# The final CandidateRunner fails an observation whose output exceeds core.process's buffer.
OUTPUT_LIMIT = 24000
CHECK_SECONDS = 30

_COMPARATOR = '\n'.join(['import itertools, json, math', inspect.getsource(canonical),
                         inspect.getsource(final.valid_flow), inspect.getsource(final.compare_observation)])


def check_program(probe, root='/candidate'):
    """In-interpreter pass/fail program equivalent to one final-grader probe.

    Mirrors CandidateRunner: the probe runs as __main__ after `import sys, json`;
    any other stdout/stderr output, an exception, SystemExit, a non-JSON result or an
    oversized observation fails. Only the comparison moves into the candidate process.
    """
    reference = json.dumps({'id':probe['id'], 'comparator':probe.get('comparator', 'exact'),
                            'expected':probe['expected']}, allow_nan=False)
    return '\n'.join([
        'import sys, json',
        f'sys.path.insert(0, {root!r})',
        'import os as _os, tempfile as _tempfile',
        '_capture = _tempfile.TemporaryFile()',
        '_os.dup2(_capture.fileno(), 1); _os.dup2(_capture.fileno(), 2)',
        'try:',
        f'    exec(compile({probe["program"]!r}, "<probe>", "exec"), globals())',
        '    _payload = __import__("json").dumps(result, allow_nan=False)',
        'except BaseException:',
        '    _os._exit(1)',
        'sys.stdout.flush(); sys.stderr.flush()',
        '_capture.seek(0)',
        f'if _capture.read(1) or len(_payload.encode()) + 1 > {OUTPUT_LIMIT}:',
        '    _os._exit(1)',
        _COMPARATOR,
        f'_probe = json.loads({reference!r})',
        'try:',
        '    _passed = compare_observation(_probe, json.loads(_payload)) is True',
        'except (KeyError, TypeError, ValueError, IndexError):',
        '    _passed = False',
        # Skip interpreter shutdown: the exit status is the whole verdict.
        '_os._exit(0 if _passed else 1)',
        ''])


class DockerOracle:
    adversarially_verified = False

    def __init__(self, manifest, image="docker.io/library/mosslight-tools:local", probes=None):
        self.manifest = Path(manifest).resolve()
        self.entries = json.loads(self.manifest.read_text())["entries"]
        self.image = image
        self.cache = {}
        # Same probe construction as the final grader; its random inputs are drawn once
        # per oracle, so every provisional snapshot in an episode sees the same questions.
        probes = final.FinalOracle(runner=object()).probes if probes is None else probes
        by_id = {probe['id']: probe for probe in probes}
        missing = sorted(entry["id"] for entry in self.entries if entry["id"] not in by_id)
        if missing:
            raise ValueError('provisional checks need a grader probe for every manifest defect')
        self.programs = {entry["id"]: check_program(by_id[entry["id"]]) for entry in self.entries}

    def __call__(self, snapshot, remaining):
        if remaining <= 0:
            raise TimeoutError('provisional grading deadline')
        deadline = time.monotonic() + remaining
        key = fingerprint(snapshot)
        if key is not None and key in self.cache:
            return self.cache[key].copy()
        verdict = dict.fromkeys(self.programs, False)
        with tempfile.TemporaryDirectory(prefix="mosslight-provisional-") as folder:
            staged = Path(folder) / "candidate"
            try:
                # The grader's submission boundary: only admitted, bounded, UTF-8 files.
                extract(snapshot, staged)
                Path(folder).chmod(0o755)
            except (OSError, UnicodeError, ValueError, RecursionError):
                return verdict
            # Some reference data exceeds the argv limit, so each program is a file.
            # Every container mounts only its own check, never the other checks.
            programs = Path(folder) / "checks"
            programs.mkdir(mode=0o755)
            for ident, code in self.programs.items():
                (programs / f"{ident}.py").write_text(code)
                (programs / f"{ident}.py").chmod(0o644)
            def check(item):
                ident, _ = item
                name = "mosslight-oracle-" + uuid.uuid4().hex
                try:
                    result = process(["docker","run","--rm","--name",name,"--network","none",
                        "--label","mosslight.run="+os.environ.get("MOSSLIGHT_RUN_ID","library"),"--read-only",
                        "--cap-drop","ALL","--security-opt","no-new-privileges","--pids-limit","64","--memory","512m","--cpus","1",
                        "--user","65534:65534","--tmpfs","/tmp:rw,nosuid,nodev,size=128m",
                        "--mount",f"type=bind,src={staged},dst=/candidate,readonly",
                        "--mount",f"type=bind,src={programs / (ident + '.py')},dst=/check.py,readonly","--workdir","/tmp",
                        self.image,"python3","-I","-B","/check.py"],min(CHECK_SECONDS,deadline-time.monotonic()))
                    return ident, result["exit_code"] == 0
                except TimeoutError:
                    return ident, False
                finally:
                    try:
                        process(["docker","rm","-f",name],5)
                    except TimeoutError as exc:
                        raise RuntimeError("provisional oracle container cleanup timed out; refusing verdict") from exc
            with ThreadPoolExecutor(max_workers=4) as pool:
                verdict.update(pool.map(check, self.programs.items()))
        if time.monotonic() >= deadline:
            raise TimeoutError("provisional grading deadline")
        if key is not None:
            self.cache[key] = verdict.copy()
        return verdict
