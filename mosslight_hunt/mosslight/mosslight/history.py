"""Garden histories, corrections and rebasing."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import uuid

from .commands import execute
from .model import World, load


COLLECTIONS = ("notes", "tasks", "specimens", "beds", "plans", "rules", "nursery")
CREATES = {"note": "notes", "task": "tasks", "specimen": "specimens",
           "bed": "beds", "schedule": "plans", "rule": "rules",
           "nursery_seed": "nursery", "cutting": "nursery"}
TARGETS = {"edit_note": "notes", "complete_task": "tasks", "delete_bed": "beds",
           "cancel_plan": "plans", "enable_rule": "rules", "delete_rule": "rules",
           "nursery_water": "nursery", "plant_out": "nursery", "nursery_discard": "nursery"}


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _version_info(version):
    try:
        from .runtime import version_info
    except ModuleNotFoundError as error:
        if error.name != __package__ + ".runtime":
            raise
        if version != "classic-1":
            raise ValueError("This standalone history build supports classic-1")
        names = ("engine", "model", "state", "commands", "planning", "gardening",
                 "habitat", "weather", "nursery", "notebook", "exchange", "validation")
        files = {name: (Path(__file__).parent / (name + ".py")).read_text() for name in names}
        return {"id": version, "schema": 2, "fingerprint": _digest(files)}
    return version_info(version)


def _execute(version, world, command):
    try:
        from .runtime import execute_for
    except ModuleNotFoundError as error:
        if error.name != __package__ + ".runtime":
            raise
        _version_info(version)
        return execute(world, command)
    return execute_for(version, world, command)


class HistoryConflict(ValueError):
    def __init__(self, kind, message, *, event=None, reference=None):
        super().__init__(message)
        self.details = {"kind": kind, "message": message}
        if event is not None:
            self.details["event"] = event
        if reference is not None:
            self.details["reference"] = reference


def _target(command):
    op = command.get("op")
    return command.get("args", {}).get("collection") if op == "delete_entry" else TARGETS.get(op)


def _present(state, entity):
    return any(item["id"] == entity["id"]
               for item in state["world"]["workbench"][entity["collection"]])


def _canonical_command(command, state):
    if not isinstance(command, dict) or set(command) - {"op", "args"}:
        raise ValueError("A history command accepts only op and args")
    if not isinstance(command.get("op"), str):
        raise ValueError("A history command needs a string operation")
    result = copy.deepcopy(command)
    args = result.setdefault("args", {})
    if not isinstance(args, dict):
        raise ValueError("Command arguments must be an object")
    collection = _target(result)
    bindings = {}
    if collection is not None:
        value = args.get("ident")
        if isinstance(value, dict) and set(value) == {"$ref"} and isinstance(value["$ref"], str):
            entity = state["entities"].get(value["$ref"])
            bindings["ident"] = entity["id"] if entity else None
        elif type(value) is int:
            matches = [ref for ref, entity in state["entities"].items()
                       if entity["collection"] == collection and entity["id"] == value and _present(state, entity)]
            if len(matches) != 1:
                raise HistoryConflict("missing-reference", "No live object has that local ID")
            args["ident"] = {"$ref": matches[0]}
            bindings["ident"] = value
        else:
            raise ValueError("Object identifiers must be local integers or {$ref: logical-id}")
    _json(result)
    return result, bindings


def _resolved_command(event, state):
    command = copy.deepcopy(event["command"])
    collection = _target(command)
    if collection is not None:
        ref = command["args"]["ident"]["$ref"]
        entity = state["entities"].get(ref)
        if entity is None or not _present(state, entity):
            raise HistoryConflict("missing-reference", "The referenced object is absent in this history",
                                  event=event["id"], reference=ref)
        if entity["collection"] != collection:
            raise HistoryConflict("reference-type", "The reference belongs to another collection",
                                  event=event["id"], reference=ref)
        command["args"]["ident"] = event["bindings"].get("ident", entity["id"])
    return command


def _event(command, state, ident=None):
    command, bindings = _canonical_command(command, state)
    return {"id": ident or uuid.uuid4().hex, "command": command, "bindings": bindings}


def _same_action(left, right):
    return left == right


def _pick_identity(event):
    return _digest(event["command"])


def _respect_shared_order(candidate, local, target):
    by_id = {event["id"]: event for event in candidate}
    rank = {event["id"]: index for index, event in enumerate(candidate)}
    following = {ident: set() for ident in by_id}
    incoming = {ident: 0 for ident in by_id}
    for sequence in (target,):
        retained = [event["id"] for event in sequence if event["id"] in by_id]
        for before, after in zip(retained, retained[1:]):
            if after not in following[before]:
                following[before].add(after)
                incoming[after] += 1
    ready = [ident for ident in by_id if incoming[ident] == 0]
    result = []
    while ready:
        ident = min(ready, key=rank.__getitem__)
        ready.remove(ident)
        result.append(by_id[ident])
        for successor in following[ident]:
            incoming[successor] -= 1
            if incoming[successor] == 0:
                ready.append(successor)
    if len(result) != len(candidate):
        blocked = next(ident for ident in by_id if incoming[ident])
        raise HistoryConflict("order-conflict", "Shared events impose contradictory authored orders", event=blocked)
    return result


def _rebase_events(base, local, target):
    original = {event["id"]: event for event in base}
    ours = {event["id"]: event for event in local}
    theirs = {event["id"]: event for event in target}
    replacements, removed = {}, set()
    for ident, before in original.items():
        own, other = ours.get(ident), theirs.get(ident)
        changed_here = own is None or not _same_action(own, before)
        changed_there = other is None or not _same_action(other, before)
        if changed_here and changed_there:
            same = own is None and other is None or own is not None and other is not None and _same_action(own, other)
            if not same:
                raise HistoryConflict("concurrent-edit", "Both histories changed the same authored event", event=ident)
        if not changed_here:
            continue
        if own is None:
            removed.add(ident)
        elif other is not None:
            replacements[ident] = own
    result = [copy.deepcopy(replacements.get(event["id"], event))
              for event in target if event["id"] not in removed]
    groups, anchor = {}, None
    for event in local:
        ident = event["id"]
        if ident in original:
            anchor = ident
        elif ident in theirs:
            if not _same_action(event, theirs[ident]):
                raise HistoryConflict("concurrent-edit", "A shared insertion has different content", event=ident)
        else:
            groups.setdefault(anchor, []).append(copy.deepcopy(event))
    for anchor, events in groups.items():
        if anchor is None:
            position = 0
        else:
            found = [index for index, event in enumerate(result) if event["id"] == anchor]
            if not found:
                raise HistoryConflict("missing-anchor", "An insertion's historical anchor was removed", event=anchor)
            position = found[0] + 1
        while position < len(result) and result[position]["id"] not in original:
            position += 1
        result[position:position] = events
    return _respect_shared_order(result, local, target)


class HistoryStore:

    def __init__(self, path):
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS history_roots (id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history_revisions (
                id TEXT PRIMARY KEY, root TEXT NOT NULL REFERENCES history_roots(id),
                events TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history_branches (
                id TEXT PRIMARY KEY, label TEXT NOT NULL, root TEXT NOT NULL REFERENCES history_roots(id),
                head TEXT NOT NULL REFERENCES history_revisions(id),
                parent TEXT REFERENCES history_branches(id),
                base_revision TEXT REFERENCES history_revisions(id));
            CREATE TABLE IF NOT EXISTS history_checkpoints (
                key TEXT PRIMARY KEY, root TEXT NOT NULL REFERENCES history_roots(id), result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history_origins (
                branch TEXT PRIMARY KEY REFERENCES history_branches(id), body TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    def _root(self, ident):
        row = self.db.execute("SELECT body FROM history_roots WHERE id = ?", (ident,)).fetchone()
        if row is None:
            raise ValueError("Unknown history root")
        return json.loads(row[0])

    def _branch(self, ident):
        row = self.db.execute("SELECT * FROM history_branches WHERE id = ?", (ident,)).fetchone()
        if row is None:
            raise ValueError("Unknown history branch")
        return dict(row)

    def _revision(self, ident):
        row = self.db.execute("SELECT * FROM history_revisions WHERE id = ?", (ident,)).fetchone()
        if row is None:
            raise ValueError("Unknown history revision")
        return {"id": row["id"], "root": row["root"], "events": json.loads(row["events"]),
                "result": json.loads(row["result"])}

    def _initial(self, root):
        entities = {"root:" + root["id"] + ":" + collection + ":" + str(item["id"]):
                    {"collection": collection, "id": item["id"]}
                    for collection in COLLECTIONS for item in root["world"]["workbench"][collection]}
        return {"world": copy.deepcopy(root["world"]), "entities": entities, "applied": 0, "conflicts": []}

    @staticmethod
    def _checkpoint_key(root, events):
        return _digest({"root": root["id"], "engine": root["engine"], "events": events[-1:]})

    def _replay(self, root, events, *, use_cache=True):
        if root["engine"] != _version_info(root["engine"]["id"]):
            raise ValueError("This history needs its original engine installation")
        state = self._initial(root)
        start = 0
        if use_cache:
            for end in range(len(events), 0, -1):
                prefix = events[:end]
                key = self._checkpoint_key(root, prefix)
                cached = self.db.execute("SELECT result FROM history_checkpoints WHERE key = ?", (key,)).fetchone()
                if cached:
                    state, start = json.loads(cached[0]), end
                    break
        for index in range(start, len(events)):
            event = events[index]
            world = World.from_dict(state["world"])
            try:
                command = _resolved_command(event, state)
                output = _execute(root["engine"]["id"], world, command)
                collection = CREATES.get(command["op"])
                if collection:
                    logical = "event:" + event["id"] + ":" + collection
                    state["entities"][logical] = {"collection": collection, "id": output["id"]}
                state["world"] = world.to_dict()
                state["applied"] = index + 1
            except ValueError as error:
                detail = error.details if isinstance(error, HistoryConflict) else {
                    "kind": "invalid-command", "message": str(error), "event": event["id"]}
                state["conflicts"] = [detail]
                return state
            prefix = events[:index + 1]
            key = self._checkpoint_key(root, prefix)
            self.db.execute("INSERT OR IGNORE INTO history_checkpoints VALUES (?, ?, ?)",
                            (key, root["id"], _json(state)))
        return state

    def _store_revision(self, root, events, result):
        ident = _digest({"root": root, "events": events})
        self.db.execute("INSERT OR IGNORE INTO history_revisions VALUES (?, ?, ?, ?)",
                        (ident, root, _json(events), _json(result)))
        return ident

    def create(self, world, label="main", version="classic-1"):
        root = {"id": uuid.uuid4().hex, "world": World.from_dict(world.to_dict()).to_dict(),
                "engine": _version_info(version)}
        branch = uuid.uuid4().hex
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT INTO history_roots VALUES (?, ?)", (root["id"], _json(root)))
            revision = self._store_revision(root["id"], [], self._initial(root))
            self.db.execute("INSERT INTO history_branches VALUES (?, ?, ?, ?, NULL, NULL)",
                            (branch, label, root["id"], revision))
            self.db.execute("INSERT INTO history_origins VALUES (?, ?)",
                            (branch, _json({"operation": "import", "root": root["id"]})))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.snapshot(branch)

    def snapshot(self, branch, revision=None):
        description = self._branch(branch)
        record = self._revision(revision or description["head"])
        if record["root"] != description["root"]:
            raise ValueError("Revision belongs to another imported garden")
        result = record["result"]
        origin = self.db.execute("SELECT body FROM history_origins WHERE branch = ?", (branch,)).fetchone()
        return {"branch": branch, "label": description["label"], "revision": record["id"],
                "parent": description["parent"], "base_revision": description["base_revision"],
                "origin": json.loads(origin[0]) if origin else None,
                "events": record["events"], "status": "conflicted" if result["conflicts"] else "ready",
                **result}

    def references(self, branch):
        state = self.snapshot(branch)
        return [{"reference": ref, **entity, "present": _present(state, entity)}
                for ref, entity in sorted(state["entities"].items())]

    def _new_branch(self, source, base_revision, events, result, label, origin=None):
        branch = uuid.uuid4().hex
        self.db.execute("BEGIN IMMEDIATE")
        try:
            revision = self._store_revision(source["root"], events, result)
            self.db.execute("INSERT INTO history_branches VALUES (?, ?, ?, ?, ?, ?)",
                            (branch, label, source["root"], revision, source["id"], base_revision))
            self.db.execute("INSERT INTO history_origins VALUES (?, ?)", (branch, _json(origin or {
                "operation": "fork", "source_revision": base_revision})))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.snapshot(branch)

    def fork(self, branch, label="fork", revision=None):
        source = self._branch(branch)
        original = self._revision(revision or source["head"])
        if source["root"] != original["root"]:
            raise ValueError("Revision belongs to another imported garden")
        return self._new_branch(source, original["id"], original["events"], original["result"], label)

    def append(self, branch, command, expected_revision=None):
        source = self._branch(branch)
        if expected_revision is not None and expected_revision != source["head"]:
            raise HistoryConflict("stale-head", "Branch changed before the command was authored")
        original = self._revision(source["head"])
        if original["result"]["conflicts"]:
            raise HistoryConflict("unresolved-history", "Resolve this history's conflict before appending")
        event = _event(command, original["result"])
        events = original["events"] + [event]
        result = self._replay(self._root(source["root"]), events)
        if result["conflicts"]:
            conflict = result["conflicts"][0]
            raise HistoryConflict(conflict["kind"], conflict["message"], event=event["id"], reference=conflict.get("reference"))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            revision = self._store_revision(source["root"], events, result)
            update = self.db.execute("UPDATE history_branches SET head = ? WHERE id = ? AND head = ?",
                                     (revision, branch, source["head"]))
            if update.rowcount != 1:
                raise HistoryConflict("stale-head", "Branch changed while the command was replaying")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.snapshot(branch)

    def correct(self, branch, replacements, label="correction"):
        source = self._branch(branch)
        original = self._revision(source["head"])
        if not isinstance(replacements, dict) or not replacements:
            raise ValueError("Supply a nonempty event-to-command correction object")
        known = {event["id"] for event in original["events"]}
        if set(replacements) - known:
            raise ValueError("Correction names an event outside this history")
        root = self._root(source["root"])
        events = []
        for index, event in enumerate(original["events"]):
            if event["id"] not in replacements:
                events.append(copy.deepcopy(event))
            elif replacements[event["id"]] is not None:
                before = original["result"]
                events.append(_event(replacements[event["id"]], before, event["id"]))
        result = self._replay(root, events)
        return self._new_branch(source, original["id"], events, result, label, {
            "operation": "correct", "source_revision": original["id"], "replacements": replacements})

    def cherry_pick(self, source_branch, target_branch, event_ids, label="picked"):
        source, target = self._branch(source_branch), self._branch(target_branch)
        if source["root"] != target["root"]:
            raise ValueError("Cherry-pick needs histories of the same imported garden")
        source_revision, target_revision = self._revision(source["head"]), self._revision(target["head"])
        if not isinstance(event_ids, list) or len(event_ids) != len(set(event_ids)):
            raise ValueError("Select distinct authored event IDs")
        selected = set(event_ids)
        if selected - {event["id"] for event in source_revision["events"]}:
            raise ValueError("Selected event is absent from the source")
        events = copy.deepcopy(target_revision["events"])
        existing = {_pick_identity(event): event for event in events}
        for event in source_revision["events"]:
            if event["id"] not in selected:
                continue
            ident = _pick_identity(event)
            if ident in existing:
                if not _same_action(existing[ident], event):
                    raise HistoryConflict("concurrent-edit", "An already present event has different content", event=event["id"])
                continue
            events.append(copy.deepcopy(event))
            existing[ident] = event
        result = self._replay(self._root(target["root"]), events)
        return self._new_branch(target, target_revision["id"], events, result, label, {
            "operation": "cherry-pick", "source_revision": source_revision["id"],
            "target_revision": target_revision["id"], "selected_events": event_ids})

    def rebase(self, branch, onto, label="rebased"):
        source, target = self._branch(branch), self._branch(onto)
        if source["root"] != target["root"]:
            raise ValueError("Rebase needs histories of the same imported garden")
        if source["base_revision"] is None:
            raise ValueError("Only a fork has a recorded base for rebasing")
        base_revision = self._branch(source["parent"])["head"]
        base = self._revision(base_revision)
        local, destination = self._revision(source["head"]), self._revision(target["head"])
        events = _rebase_events(base["events"], local["events"], destination["events"])
        result = self._replay(self._root(source["root"]), events)
        return self._new_branch(target, destination["id"], events, result, label, {
            "operation": "rebase", "source_revision": local["id"], "base_revision": base["id"],
            "target_revision": destination["id"]})

    def verify(self, branch):
        source = self._branch(branch)
        revision = self._revision(source["head"])
        fresh = self._replay(self._root(source["root"]), revision["events"], use_cache=False)
        return {"revision": source["head"], "matches": fresh == revision["result"],
                "fresh": fresh}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Correct and compare preserved garden histories")
    parser.add_argument("database")
    commands = parser.add_subparsers(dest="operation", required=True)
    create = commands.add_parser("create")
    create.add_argument("garden")
    create.add_argument("--version", default="classic-1")
    create.add_argument("--label", default="main")
    for name in ("show", "references", "verify", "fork", "append", "correct", "pick", "rebase", "export"):
        command = commands.add_parser(name)
        command.add_argument("branch")
        if name in ("fork", "correct", "pick", "rebase"):
            command.add_argument("--label", default=name)
        if name in ("append", "correct"):
            command.add_argument("input", help="JSON command or event-to-command correction file")
        if name == "append":
            command.add_argument("--revision")
        if name == "pick":
            command.add_argument("source")
            command.add_argument("events", nargs="+")
        if name == "rebase":
            command.add_argument("onto")
        if name == "export":
            command.add_argument("output")
    args = parser.parse_args(argv)
    store = HistoryStore(args.database)
    try:
        op = args.operation
        if op == "create":
            result = store.create(load(args.garden), args.label, args.version)
        elif op == "show":
            result = store.snapshot(args.branch)
        elif op == "references":
            result = store.references(args.branch)
        elif op == "verify":
            result = store.verify(args.branch)
        elif op == "fork":
            result = store.fork(args.branch, args.label)
        elif op == "append":
            result = store.append(args.branch, json.loads(Path(args.input).read_text()), args.revision)
        elif op == "correct":
            result = store.correct(args.branch, json.loads(Path(args.input).read_text()), args.label)
        elif op == "pick":
            result = store.cherry_pick(args.source, args.branch, args.events, args.label)
        elif op == "rebase":
            result = store.rebase(args.branch, args.onto, args.label)
        else:
            result = store.snapshot(args.branch)
            if result["status"] != "ready":
                raise ValueError("Resolve the history conflict before exporting a complete garden")
            Path(args.output).write_text(json.dumps(result["world"], ensure_ascii=False, indent=2) + "\n")
            result = {"revision": result["revision"], "output": args.output}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(_json(error.details if isinstance(error, HistoryConflict) else {"error": str(error)}), file=sys.stderr)
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
