"""Process and hashing primitives the grader needs, shared with the harness.

Stdlib only, so the grader does not depend on the broker. ``process`` runs one
command with a wall-clock limit, kills its whole process group, and keeps only
the last 24,000 bytes of combined output.
"""
from __future__ import annotations
import hashlib
import json
import os
import selectors
import signal
import subprocess
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            raise ValueError(f"symlinks forbidden in snapshot: {relative}")
        if path.is_file():
            digest.update(canonical([relative, path.stat().st_mode & 0o777]).encode())
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b""):
                    digest.update(chunk)
        elif not path.is_dir():
            raise ValueError(f"special file forbidden: {relative}")
    return digest.hexdigest()


class CommandTimeout(TimeoutError):
    """A command overran its own time limit; carries the output read before it was killed."""
    def __init__(self, message, output="", truncated=False):
        super().__init__(message)
        self.output, self.truncated = output, truncated


def process(command, seconds, *, cwd=None, env=None):
    if seconds <= 0:
        raise TimeoutError("wall clock exhausted")
    child = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + seconds
    output = bytearray()
    truncated = False
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    def overrun():
        return CommandTimeout("command deadline", output.decode("utf8", "replace"), truncated)
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise overrun()
            for key, _ in selector.select(min(remaining, .1)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    output.extend(chunk)
                    truncated = truncated or len(output) > 24000
                    del output[:-24000]
        try:
            child.wait(timeout=max(.001, deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            # The command closed its output but kept running past its limit.
            raise overrun() from None
        return {"exit_code":child.returncode,"output":output.decode("utf8", "replace"),"truncated":truncated}

    finally:
        # Includes descendants even if the immediate parent has exited.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        selector.close()
        child.stdout.close()
