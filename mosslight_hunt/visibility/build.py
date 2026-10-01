"""Build a fresh application-only checkout without copying host evaluation data."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil


# Explicit relative names make newly added host files opt-in, even when they use
# an otherwise legitimate application extension. Keep this list host-side.
MODULES = """__init__ __main__ analysis campaigns catalog charts commands courier
engine ensemble_compute ensemble_reports ensembles exchange experiments field_calibration gardening
habitat history history_exchange irrigation irrigation_flow model notebook nursery planning render runtime
save_merge semantics server state studies study_compute validation weather workspace_catalog""".split()
DOCUMENTS = """README.md SUBMISSION.md LICENSE pyproject.toml BEHAVIORS.md CAMPAIGNS.md COMMANDS.md
COURIER.md DESIGN.md ENSEMBLES.md FIELD_CALIBRATION.md HISTORY.md HISTORY_EXCHANGE.md IRRIGATION.md
SAVE_MERGE.md STUDIES.md WORKSPACE_CATALOG.md GROWING.md WORKBENCH.md
FIELD_GUIDE.md PORTABILITY.md""".split()
EXAMPLES = """ensemble.json first-garden.json first-garden.svg hollow-actions.json
lantern-hollow.json lantern-hollow.svg study.json treatments.json""".split()
ALLOWED_FILES = tuple(sorted(DOCUMENTS + [f"mosslight/{name}.py" for name in MODULES]
                            + [f"examples/{name}" for name in EXAMPLES]
                            + [f"mosslight/static/{name}" for name in ("app.js", "app.css", "index.html")]))
DOCUMENT_OVERRIDES = ("FIELD_CALIBRATION.md", "WORKSPACE_CATALOG.md", "IRRIGATION.md")


def _host_name(name: str) -> bool:
    lower = name.lower()
    return (lower.startswith(".") or lower == "__pycache__"
            or any(word in lower for word in
                   ("host_only", "host_artifact", "manifest", "answer", "oracle", "grader",
                    "snapshot", "archive", "baseline", "clean_", "seeded_", "secret", "patch")))


def _check_new_application_files(source: Path) -> None:
    """Require conscious review when new ordinary application files appear."""
    unknown = []
    for directory, dirs, files in os.walk(source, followlinks=False):
        root = Path(directory)
        dirs[:] = [name for name in dirs if not _host_name(name)
                   and not (root / name).is_symlink()
                   and (root != source or name in ("mosslight", "examples"))]
        for name in files:
            path = root / name
            if _host_name(name) or path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(source)
            if relative.as_posix() in ALLOWED_FILES:
                continue
            application_file = (
                (root == source and path.suffix.lower() in (".md", ".rst", ".toml"))
                or (relative.parts[0] == "mosslight" and path.suffix == ".py")
                or relative.parts[:2] == ("mosslight", "static")
                or relative.parts[0] == "examples")
            if application_file:
                unknown.append(relative.as_posix())
    if unknown:
        raise ValueError("application allowlist update required for: " + ", ".join(sorted(unknown)))


def _safe_file(root: Path, relative: str) -> bool:
    candidate = root
    for part in Path(relative).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            return False
    return candidate.is_file() and candidate.resolve().is_relative_to(root)


def _readme(text: str) -> str:
    start, end = text.find("## Test and inspect"), text.find("## Project map")
    if start >= 0 and end > start:
        text = text[:start] + """## Test and inspect

```sh
python3 -B -m unittest discover -s tests -v
node --check mosslight/static/app.js
```

The smoke suite checks everyday application workflows: creating and saving a
garden, advancing it, exporting artwork and using the command line. Node is
optional and checks browser script syntax. Add regression tests when fixing bugs.

""" + text[end:]
    return text


def build_agent_tree(source: Path, destination: Path) -> dict:
    """Copy approved application files and broad smoke tests to a fresh directory.

    Returns a deterministic host-side content inventory; no inventory is placed
    in the checkout. Symlinks are never copied or followed. Neither argument may
    contain parent traversal, and the destination must be disjoint and absent.
    This is a packaging boundary, not a substitute for process isolation.
    """
    source, destination = Path(source), Path(destination)
    if ".." in source.parts or ".." in destination.parts:
        raise ValueError("parent traversal is not permitted")
    if source.is_symlink() or destination.is_symlink():
        raise ValueError("source and destination must not be symlinks")
    source, destination = source.resolve(strict=True), destination.resolve()
    if not source.is_dir():
        raise ValueError("source must be an application directory")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("source and destination must be disjoint")
    if destination.exists():
        raise FileExistsError(destination)
    for required in ("mosslight/__init__.py", "mosslight/__main__.py", "pyproject.toml", "README.md"):
        if not _safe_file(source, required):
            raise ValueError(f"missing regular application file: {required}")
    _check_new_application_files(source)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for relative in ALLOWED_FILES:
            if not _safe_file(source, relative):
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative == "README.md":
                target.write_text(_readme((source / relative).read_text(encoding="utf-8")), encoding="utf-8")
            elif relative in DOCUMENT_OVERRIDES:
                target.write_bytes((Path(__file__).parent / "templates" / relative).read_bytes())
            else:
                target.write_bytes((source / relative).read_bytes())
        shutil.copyfile(Path(__file__).parents[1] / "agent_data" / "SUBMISSION.md", destination / "SUBMISSION.md")
        tests = destination / "tests"
        tests.mkdir()
        template = Path(__file__).parent / "templates" / "test_smoke.py"
        (tests / "test_smoke.py").write_bytes(template.read_bytes())
        inventory = []
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                data = path.read_bytes()
                inventory.append({"path": path.relative_to(destination).as_posix(),
                                  "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        digest = hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"format_version": 1, "tree_sha256": digest, "files": inventory}
    except BaseException:
        shutil.rmtree(destination)
        raise
