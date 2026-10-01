"""Editable experiment ensembles and published reports."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sqlite3
import sys
import uuid

from .ensemble_compute import digest, encoded, evaluate
from .ensemble_reports import METRICS, summarize
from .model import World
from .runtime import DEFAULT_VERSION, version_info
from .validation import integer, mapping, sequence, text


def _validate_inputs(inputs, days):
    for key, item in inputs.items():
        value = item["value"]
        if key.startswith("source:"):
            World.from_dict(value)
        elif key.startswith("plan:"):
            mapping(value, "Care plan")
            for event in sequence(value.get("events"), "Plan events", 100):
                mapping(event, "Plan event")
                integer(event.get("offset"), "Event offset", 0, days)
                command = mapping(event.get("command"), "Plan command")
                if command.get("op") == "grow":
                    raise ValueError("Care plans cannot advance time")
        elif key.startswith("route:"):
            mapping(value, "Care route")
            plans = [text(value.get("plan"), "Plan name", 80)]
            condition = value.get("when")
            if condition is not None:
                mapping(condition, "Care condition")
                if condition.get("metric") not in METRICS:
                    raise ValueError("Unknown care metric")
                below = condition.get("below")
                if type(below) not in (int, float):
                    raise ValueError("Care threshold must be numeric")
                plans.append(text(condition.get("plan"), "Conditional plan name", 80))
            if any("plan:" + plan not in inputs for plan in plans):
                raise ValueError("Care route references an unknown plan")
        else:
            raise ValueError("Unknown input category")
        if digest(value) != item["digest"]:
            raise ValueError("Input fingerprint changed")


class EnsembleStore:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = FULL")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS ensemble_workspaces (
                id TEXT PRIMARY KEY, definition TEXT NOT NULL, head INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS ensemble_snapshots (
                ensemble TEXT NOT NULL REFERENCES ensemble_workspaces(id),
                revision INTEGER NOT NULL, inputs TEXT NOT NULL,
                PRIMARY KEY (ensemble, revision));
            CREATE TABLE IF NOT EXISTS ensemble_nodes (
                ensemble TEXT NOT NULL REFERENCES ensemble_workspaces(id),
                node TEXT NOT NULL, spec TEXT NOT NULL, generation INTEGER NOT NULL,
                dirty INTEGER NOT NULL, reads TEXT NOT NULL, outcome TEXT,
                PRIMARY KEY (ensemble, node));
            CREATE TABLE IF NOT EXISTS ensemble_cache (
                key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ensemble_reports (
                ensemble TEXT NOT NULL REFERENCES ensemble_workspaces(id),
                revision INTEGER NOT NULL, envelope TEXT NOT NULL,
                PRIMARY KEY (ensemble, revision));
        """)

    def close(self):
        self.db.close()

    def create(self, sources, days, plans, routes, treatments, every=1, version=DEFAULT_VERSION):
        integer(days, "Experiment days", 1, 120)
        integer(every, "Sample interval", 1, 120)
        mapping(sources, "Source gardens")
        mapping(plans, "Care plans")
        mapping(routes, "Care routes")
        sequence(treatments, "Treatments", 8)
        if not sources or len(sources) > 64 or not treatments:
            raise ValueError("Supply 1–64 source gardens and 1–8 treatments")
        for label in [*sources, *plans, *routes]:
            if text(label, "Input label", 80) != label:
                raise ValueError("Input labels cannot have surrounding whitespace")
        names = {"control"}
        for treatment in treatments:
            mapping(treatment, "Treatment")
            name = text(treatment.get("name"), "Treatment name", 80)
            if name != treatment["name"] or name.casefold() in names:
                raise ValueError("Treatment names must be unique; control is reserved")
            names.add(name.casefold())
            if treatment.get("route") not in routes:
                raise ValueError("Treatment references an unknown care route")
        values = {"source:" + name: source.to_dict() if isinstance(source, World) else source
                  for name, source in sources.items()}
        values.update({"plan:" + name: value for name, value in plans.items()})
        values.update({"route:" + name: value for name, value in routes.items()})
        inputs = {name: {"value": value, "digest": digest(value)} for name, value in values.items()}
        _validate_inputs(inputs, days)
        definition = {"replicates": list(sources), "treatments": treatments, "days": days,
                      "every": every, "runtime": version_info(version)}
        ident = uuid.uuid4().hex
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT INTO ensemble_workspaces VALUES (?, ?, 0)", (ident, encoded(definition)))
            self.db.execute("INSERT INTO ensemble_snapshots VALUES (?, 0, ?)", (ident, encoded(inputs)))
            branches = [{"name": "control", "route": None}, *treatments]
            for replicate in sources:
                for treatment in branches:
                    spec = {"replicate": replicate, "treatment": treatment["name"], "route": treatment["route"]}
                    node = digest(spec)
                    self.db.execute("INSERT INTO ensemble_nodes VALUES (?, ?, ?, 0, 1, '{}', NULL)",
                                    (ident, node, encoded(spec)))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return ident

    def _workspace(self, ensemble):
        row = self.db.execute("SELECT * FROM ensemble_workspaces WHERE id = ?", (ensemble,)).fetchone()
        if row is None:
            raise ValueError("Unknown ensemble")
        return {"definition": json.loads(row["definition"]), "head": row["head"]}

    def _inputs(self, ensemble, revision):
        row = self.db.execute("SELECT inputs FROM ensemble_snapshots WHERE ensemble = ? AND revision = ?",
                              (ensemble, revision)).fetchone()
        if row is None:
            raise ValueError("Unknown input revision")
        return json.loads(row[0])

    def inputs(self, ensemble, revision=None):
        if revision is None:
            revision = self._workspace(ensemble)["head"]
        return {key: item["value"] for key, item in self._inputs(ensemble, revision).items()}

    def edit(self, ensemble, changes, expected_revision=None):
        mapping(changes, "Input changes")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            workspace = self._workspace(ensemble)
            if expected_revision is not None and workspace["head"] != expected_revision:
                raise ValueError("Ensemble was edited; reload before applying this change")
            inputs = self._inputs(ensemble, workspace["head"])
            changed = set()
            for key, value in changes.items():
                if key not in inputs:
                    raise ValueError("Edits must name existing inputs")
                fingerprint = digest(value)
                if fingerprint != inputs[key]["digest"]:
                    inputs[key] = {"value": copy.deepcopy(value), "digest": fingerprint}
                    changed.add(key)
            if not changed:
                self.db.execute("COMMIT")
                return workspace["head"]
            _validate_inputs(inputs, workspace["definition"]["days"])
            revision = workspace["head"] + 1
            self.db.execute("INSERT INTO ensemble_snapshots VALUES (?, ?, ?)", (ensemble, revision, encoded(inputs)))
            self.db.execute("UPDATE ensemble_workspaces SET head = ? WHERE id = ?", (revision, ensemble))
            for row in self.db.execute("SELECT node, reads FROM ensemble_nodes WHERE ensemble = ?", (ensemble,)).fetchall():
                if changed.intersection(json.loads(row["reads"])):
                    self.db.execute("UPDATE ensemble_nodes SET dirty = 1, generation = generation + 1 WHERE ensemble = ? AND node = ?",
                                    (ensemble, row["node"]))
            self._archive_if_ready(ensemble)
            self.db.execute("COMMIT")
            return revision
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def status(self, ensemble):
        workspace = self._workspace(ensemble)
        rows = self.db.execute("SELECT node, spec, generation, dirty, outcome FROM ensemble_nodes WHERE ensemble = ? ORDER BY rowid",
                               (ensemble,)).fetchall()
        return {"ensemble": ensemble, "revision": workspace["head"], "nodes": [
            {"node": row["node"], **json.loads(row["spec"]), "generation": row["generation"],
             "status": "pending" if row["dirty"] else json.loads(row["outcome"])["payload"]["status"]}
            for row in rows]}

    def prepare(self, ensemble, node=None):
        self.db.execute("BEGIN")
        try:
            workspace = self._workspace(ensemble)
            rows = self.db.execute("SELECT * FROM ensemble_nodes WHERE ensemble = ? AND dirty = 1 ORDER BY rowid", (ensemble,)).fetchall()
            row = next((r for r in rows if node is None or r["node"] == node), None)
            if row is None:
                ticket = None
            else:
                ticket = {"ensemble": ensemble, "node": row["node"], "revision": workspace["head"],
                          "generation": row["generation"], "definition": workspace["definition"],
                          "spec": json.loads(row["spec"]), "known_reads": json.loads(row["reads"]),
                          "inputs": self._inputs(ensemble, workspace["head"])}
            self.db.execute("COMMIT")
            return ticket
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _cached(self, key):
        row = self.db.execute("SELECT value FROM ensemble_cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def compute(self, ticket, use_cache=True):
        return evaluate(ticket, self._cached if use_cache else lambda key: None)

    def publish(self, ticket, computed):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            ensemble = ticket["ensemble"]
            workspace = self._workspace(ensemble)
            current = self._inputs(ensemble, workspace["head"])
            row = self.db.execute("SELECT generation, dirty FROM ensemble_nodes WHERE ensemble = ? AND node = ?",
                                  (ensemble, ticket["node"])).fetchone()
            checked_reads = {key: ticket["inputs"][key]["digest"] for key in ticket["known_reads"]}
            valid = (row is not None and row["dirty"] and row["generation"] == ticket["generation"]
                     and all(key in current and current[key]["digest"] == fingerprint
                             for key, fingerprint in checked_reads.items()))
            if valid:
                outcome = {"identity": computed["identity"], "payload": computed["payload"],
                           "selected_plan": computed["selected_plan"], "reads": computed["reads"],
                           "cache_key": computed["cache_key"], "cache_origin": computed["cache_origin"]}
                self.db.execute("UPDATE ensemble_nodes SET dirty = 0, reads = ?, outcome = ? WHERE ensemble = ? AND node = ?",
                                (encoded(computed["reads"]), encoded(outcome), ensemble, ticket["node"]))
                cache_value = {"payload": computed["payload"], "origin": computed["cache_origin"]}
                self.db.execute("INSERT OR IGNORE INTO ensemble_cache VALUES (?, ?)", (computed["cache_key"], encoded(cache_value)))
                self._archive_if_ready(ensemble)
            self.db.execute("COMMIT")
            return bool(valid)
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def work_once(self, ensemble, use_cache=True):
        ticket = self.prepare(ensemble)
        if ticket is None:
            return None
        computed = self.compute(ticket, use_cache=use_cache)
        return {"node": ticket["node"], "accepted": self.publish(ticket, computed),
                "cache_hit": computed["cache_hit"], "status": computed["payload"]["status"]}

    def _outcomes(self, ensemble):
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT outcome FROM ensemble_nodes WHERE ensemble = ? AND dirty = 0 ORDER BY rowid", (ensemble,))]

    def _archive_if_ready(self, ensemble):
        if self.db.execute("SELECT 1 FROM ensemble_nodes WHERE ensemble = ? AND dirty = 1", (ensemble,)).fetchone():
            return
        workspace = self._workspace(ensemble)
        inputs = self._inputs(ensemble, workspace["head"])
        result = summarize(workspace["definition"], self._outcomes(ensemble))
        envelope = {"ensemble": ensemble, "revision": workspace["head"], "runtime": workspace["definition"]["runtime"],
                    "input_digest": digest(inputs), "result": result, "result_digest": digest(result)}
        self.db.execute("INSERT OR IGNORE INTO ensemble_reports VALUES (?, ?, ?)",
                        (ensemble, workspace["head"], encoded(envelope)))

    def report(self, ensemble, revision=None):
        workspace = self._workspace(ensemble)
        if revision is None:
            revision = workspace["head"]
        row = self.db.execute("SELECT envelope FROM ensemble_reports WHERE ensemble = ? AND revision = ?",
                              (ensemble, revision)).fetchone()
        if row is None:
            raise ValueError("This revision has no complete published report")
        envelope = json.loads(row[0])
        envelope["result"] = summarize(workspace["definition"], self._outcomes(ensemble))
        envelope["result_digest"] = digest(envelope["result"])
        return envelope

    def replay(self, ensemble, revision=None):
        workspace = self._workspace(ensemble)
        if revision is None:
            revision = workspace["head"]
        inputs = self._inputs(ensemble, revision)
        outcomes = []
        for row in self.db.execute("SELECT node, spec FROM ensemble_nodes WHERE ensemble = ? ORDER BY rowid", (ensemble,)):
            ticket = {"ensemble": ensemble, "revision": revision, "node": row["node"],
                      "definition": workspace["definition"], "inputs": inputs, "spec": json.loads(row["spec"])}
            computed = evaluate(ticket)
            outcomes.append({key: computed[key] for key in ("identity", "payload", "selected_plan", "reads", "cache_key", "cache_origin")})
        return summarize(workspace["definition"], outcomes)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Edit and recompute paired garden ensembles")
    parser.add_argument("database")
    sub = parser.add_subparsers(dest="operation", required=True)
    create = sub.add_parser("create")
    create.add_argument("specification", help="JSON with sources, days, plans, routes and treatments")
    edit = sub.add_parser("edit")
    edit.add_argument("ensemble")
    edit.add_argument("changes", help="JSON mapping source:/plan:/route: keys to replacement values")
    edit.add_argument("--expected-revision", type=int)
    for name in ("work", "status", "inputs", "report", "replay"):
        command = sub.add_parser(name)
        command.add_argument("ensemble")
        if name == "work":
            command.add_argument("--steps", type=int, default=1000)
            command.add_argument("--no-cache", action="store_true")
        elif name != "status":
            command.add_argument("--revision", type=int)
    args = parser.parse_args(argv)
    store = EnsembleStore(args.database)
    try:
        if args.operation == "create":
            result = store.create(**json.loads(Path(args.specification).read_text()))
        elif args.operation == "edit":
            result = store.edit(args.ensemble, json.loads(Path(args.changes).read_text()), args.expected_revision)
        elif args.operation == "work":
            integer(args.steps, "Work limit", 1, 100000)
            for _ in range(args.steps):
                if store.work_once(args.ensemble, use_cache=not args.no_cache) is None:
                    break
            result = store.status(args.ensemble)
        elif args.operation == "status":
            result = store.status(args.ensemble)
        else:
            result = getattr(store, args.operation)(args.ensemble, args.revision)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
