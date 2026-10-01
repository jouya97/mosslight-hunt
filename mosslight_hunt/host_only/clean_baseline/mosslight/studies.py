"""Durable staged treatment screening with immutable cohort decisions."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sqlite3
import sys
import time
import uuid

from .ensemble_compute import digest, encoded
from .ensemble_reports import METRICS
from .model import World
from .runtime import DEFAULT_VERSION, version_info
from .study_compute import advance, progress, readiness
from .validation import integer, mapping, sequence, text


def _events(events, horizon):
    sequence(events, "Treatment events", 100)
    for event in events:
        mapping(event, "Treatment event")
        integer(event.get("offset"), "Event offset", 0, horizon)
        command = mapping(event.get("command"), "Treatment command")
        if command.get("op") == "grow":
            raise ValueError("Study events cannot advance time")
    encoded(events)


class StudyStore:
    """One local SQLite connection per process; computation holds no write lock."""

    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = FULL")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS study_workspaces (
                id TEXT PRIMARY KEY, definition TEXT NOT NULL, future_plans TEXT NOT NULL,
                plan_revision INTEGER NOT NULL, current_stage INTEGER NOT NULL, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS study_plan_revisions (
                study TEXT NOT NULL REFERENCES study_workspaces(id), revision INTEGER NOT NULL,
                plans TEXT NOT NULL, PRIMARY KEY (study, revision));
            CREATE TABLE IF NOT EXISTS study_stages (
                study TEXT NOT NULL REFERENCES study_workspaces(id), stage INTEGER NOT NULL,
                description TEXT NOT NULL, PRIMARY KEY (study, stage));
            CREATE TABLE IF NOT EXISTS study_jobs (
                study TEXT NOT NULL, stage INTEGER NOT NULL, replicate TEXT NOT NULL,
                treatment TEXT NOT NULL, state TEXT NOT NULL, parent TEXT,
                status TEXT NOT NULL, generation INTEGER NOT NULL, owner TEXT,
                lease_until REAL, error TEXT,
                PRIMARY KEY (study, stage, replicate, treatment),
                FOREIGN KEY (study, stage) REFERENCES study_stages(study, stage));
            CREATE TABLE IF NOT EXISTS study_reports (
                study TEXT NOT NULL, stage INTEGER NOT NULL, envelope TEXT NOT NULL,
                PRIMARY KEY (study, stage),
                FOREIGN KEY (study, stage) REFERENCES study_stages(study, stage));
        """)

    def close(self):
        self.db.close()

    def create(self, sources, treatments, stages, every=1, metric="coverage", version=DEFAULT_VERSION):
        mapping(sources, "Sources")
        sequence(treatments, "Treatments", 8)
        sequence(stages, "Stages", 120)
        integer(every, "Sample interval", 1, 120)
        if not sources or len(sources) > 64 or not treatments or not stages:
            raise ValueError("Supply 1–64 sources, 1–8 treatments and at least one stage")
        if metric not in METRICS:
            raise ValueError("Unknown selection metric")
        previous_day, previous_keep = 0, len(treatments)
        for stage in stages:
            mapping(stage, "Stage")
            previous_day = integer(stage.get("until"), "Stage horizon", previous_day + 1, 120)
            previous_keep = integer(stage.get("keep"), "Promoted count", 1, previous_keep)
        names, plans = {"control"}, {}
        for treatment in treatments:
            mapping(treatment, "Treatment")
            name = text(treatment.get("name"), "Treatment name", 80)
            if name != treatment["name"] or name.casefold() in names:
                raise ValueError("Treatment names must be unique; control is reserved")
            names.add(name.casefold())
            events = treatment.get("events", [])
            _events(events, previous_day)
            plans[name] = copy.deepcopy(events)
        saved = {}
        for label, world in sources.items():
            if text(label, "Source label", 80) != label:
                raise ValueError("Source labels cannot have surrounding whitespace")
            value = copy.deepcopy(world.to_dict() if isinstance(world, World) else world)
            saved[label] = copy.deepcopy(World.from_dict(value).to_dict())
        definition = {"sources": saved, "replicates": list(saved), "treatments": list(plans),
                      "stages": copy.deepcopy(stages), "every": every, "metric": metric,
                      "runtime": version_info(version)}
        ident = uuid.uuid4().hex
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT INTO study_workspaces VALUES (?, ?, ?, 0, 0, 'running')", (ident, encoded(definition), encoded(plans)))
            self.db.execute("INSERT INTO study_plan_revisions VALUES (?, 0, ?)", (ident, encoded(plans)))
            self._start_stage(ident, 0, list(saved), list(plans))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return ident

    def _workspace(self, study):
        row = self.db.execute("SELECT * FROM study_workspaces WHERE id = ?", (study,)).fetchone()
        if row is None:
            raise ValueError("Unknown study")
        return {**dict(row), "definition": json.loads(row["definition"]), "future_plans": json.loads(row["future_plans"])}

    def _stage(self, study, index):
        row = self.db.execute("SELECT description FROM study_stages WHERE study = ? AND stage = ?", (study, index)).fetchone()
        if row is None:
            raise ValueError("Study stage has not been dispatched")
        return json.loads(row[0])

    def _jobs(self, study, index):
        rows = self.db.execute("SELECT * FROM study_jobs WHERE study = ? AND stage = ? ORDER BY rowid", (study, index)).fetchall()
        return [{**dict(row), "state": json.loads(row["state"]), "parent": json.loads(row["parent"]) if row["parent"] else None} for row in rows]

    def _job_statuses(self, study, index):
        return [dict(row) for row in self.db.execute(
            "SELECT replicate, treatment, status, generation, error FROM study_jobs WHERE study = ? AND stage = ? ORDER BY rowid", (study, index))]

    def _start_stage(self, study, index, cohort, treatments):
        workspace = self._workspace(study)
        definition = workspace["definition"]
        treatments = [name for name in definition["treatments"] if name in treatments]
        description = {"index": index, **definition["stages"][index], "cohort": cohort,
                       "treatments": treatments, "plans": workspace["future_plans"],
                       "plan_revision": workspace["plan_revision"]}
        self.db.execute("INSERT INTO study_stages VALUES (?, ?, ?)", (study, index, encoded(description)))
        for replicate in cohort:
            for treatment in ["control", *treatments]:
                if index:
                    parent = self.checkpoint(study, index - 1, replicate, treatment)
                    state = copy.deepcopy(parent["state"])
                    anchor = {key: parent[key] for key in ("study", "stage", "replicate", "treatment", "digest")}
                else:
                    state = {"next_offset": 0, "world": definition["sources"][replicate], "samples": []}
                    anchor = None
                self.db.execute("INSERT INTO study_jobs VALUES (?, ?, ?, ?, ?, ?, 'ready', 0, NULL, NULL, NULL)",
                                (study, index, replicate, treatment, encoded(state), encoded(anchor) if anchor else None))
        self.db.execute("UPDATE study_workspaces SET current_stage = ? WHERE id = ?", (index, study))

    def edit_future(self, study, changes, expected_revision=None):
        mapping(changes, "Future plan changes")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            workspace = self._workspace(study)
            if workspace["status"] != "running":
                raise ValueError("A finished study cannot be edited")
            if expected_revision is not None and expected_revision != workspace["plan_revision"]:
                raise ValueError("Care plans changed; reload before editing")
            stage = self._stage(study, workspace["current_stage"])
            plans = workspace["future_plans"]
            original = encoded(plans)
            for name, events in changes.items():
                if name not in plans:
                    raise ValueError("Unknown treatment")
                _events(events, workspace["definition"]["stages"][-1]["until"])
                old_prefix = [event for event in plans[name] if event["offset"] <= stage["until"]]
                new_prefix = [event for event in events if event["offset"] <= stage["until"]]
                if old_prefix != new_prefix:
                    raise ValueError("Dispatched care is immutable; edit events after the active horizon")
                plans[name] = copy.deepcopy(events)
            revision = workspace["plan_revision"]
            if original != encoded(plans):
                revision += 1
                self.db.execute("INSERT INTO study_plan_revisions VALUES (?, ?, ?)", (study, revision, encoded(plans)))
                self.db.execute("UPDATE study_workspaces SET future_plans = ?, plan_revision = ? WHERE id = ?", (encoded(plans), revision, study))
            self.db.execute("COMMIT")
            return revision
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def claim(self, study, lease_seconds=30):
        if type(lease_seconds) not in (int, float) or not 0 < lease_seconds <= 3600:
            raise ValueError("Lease duration must be positive and at most one hour")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            workspace = self._workspace(study)
            row = None
            if workspace["status"] == "running":
                row = self.db.execute("""SELECT * FROM study_jobs WHERE study = ? AND stage = ?
                    AND (status = 'ready' OR (status = 'running' AND lease_until <= ?)) ORDER BY rowid LIMIT 1""",
                                      (study, workspace["current_stage"], self.clock())).fetchone()
            if row is None:
                self.db.execute("COMMIT")
                return None
            owner, generation = uuid.uuid4().hex, row["generation"] + 1
            self.db.execute("""UPDATE study_jobs SET status = 'running', owner = ?, generation = ?, lease_until = ?
                WHERE study = ? AND stage = ? AND replicate = ? AND treatment = ?""",
                            (owner, generation, self.clock() + lease_seconds, study, row["stage"], row["replicate"], row["treatment"]))
            stage = self._stage(study, row["stage"])
            result = {"study": study, "stage": row["stage"], "replicate": row["replicate"], "treatment": row["treatment"],
                      "owner": owner, "generation": generation, "state": json.loads(row["state"]),
                      "definition": workspace["definition"], "plans": stage["plans"], "until": stage["until"]}
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    @staticmethod
    def compute(claim, offsets=1):
        return advance(claim, offsets)

    def _publish(self, claim, state, error):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            status = "failed" if error is not None else "complete" if state["next_offset"] > claim["until"] else "ready"
            cursor = self.db.execute("""UPDATE study_jobs SET state = ?, status = ?, error = ?, owner = NULL, lease_until = NULL
                WHERE study = ? AND stage = ? AND replicate = ? AND treatment = ?
                AND generation = ? AND owner = ? AND status = 'running'""",
                                    (encoded(state), status, str(error) if error is not None else None,
                                     claim["study"], claim["stage"], claim["replicate"], claim["treatment"], claim["generation"], claim["owner"]))
            accepted = cursor.rowcount == 1
            if accepted:
                self._advance_if_ready(claim["study"], claim["stage"])
            self.db.execute("COMMIT")
            return accepted
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def publish(self, claim, state):
        return self._publish(claim, state, None)

    def fail(self, claim, error):
        return self._publish(claim, claim["state"], error)

    def work_once(self, study, offsets=1):
        claim = self.claim(study)
        if claim is None:
            return None
        try:
            state = self.compute(claim, offsets)
        except ValueError as error:
            return {"accepted": self.fail(claim, error), "failed": True}
        return {"accepted": self.publish(claim, state), "failed": False}

    def _save_report(self, study, index, envelope):
        self.db.execute("INSERT INTO study_reports VALUES (?, ?, ?)", (study, index, encoded(envelope)))

    def _advance_if_ready(self, study, index):
        workspace = self._workspace(study)
        if workspace["current_stage"] != index or workspace["status"] != "running":
            return
        stage = self._stage(study, index)
        support = readiness(stage, self._job_statuses(study, index))
        if not support["terminal"]:
            return
        jobs = self._jobs(study, index)
        preview = progress(stage, jobs, workspace["definition"]["metric"])
        common = preview["common"]
        promoted = [row["treatment"] for row in preview["ranking"][:stage["keep"]]] if common else []
        decision = {**preview, "promoted": promoted, "error": None if common else "No source has a complete control and every active treatment"}
        outcomes = [{"replicate": job["replicate"], "treatment": job["treatment"], "status": job["status"],
                     "state": job["state"], "state_digest": digest(job["state"]), "parent": job["parent"], "error": job["error"]} for job in jobs]
        envelope = {"study": study, "stage": index, "until": stage["until"], "cohort": stage["cohort"],
                    "treatments": stage["treatments"], "plan_revision": stage["plan_revision"], "plans": stage["plans"],
                    "runtime": workspace["definition"]["runtime"], "decision": decision, "outcomes": outcomes}
        envelope["digest"] = digest(envelope)
        self._save_report(study, index, envelope)
        if not common:
            self.db.execute("UPDATE study_workspaces SET status = 'failed' WHERE id = ?", (study,))
        elif index + 1 == len(workspace["definition"]["stages"]):
            self.db.execute("UPDATE study_workspaces SET status = 'complete' WHERE id = ?", (study,))
        else:
            self._start_stage(study, index + 1, common, promoted)

    def status(self, study):
        self.db.execute("BEGIN")
        try:
            workspace = self._workspace(study)
            result = {"study": study, "status": workspace["status"], "stage": workspace["current_stage"],
                      "plan_revision": workspace["plan_revision"], "jobs": self._job_statuses(study, workspace["current_stage"])}
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def preview(self, study):
        self.db.execute("BEGIN")
        try:
            workspace = self._workspace(study)
            index = workspace["current_stage"]
            result = {"study": study, "stage": index, **progress(self._stage(study, index), self._jobs(study, index), workspace["definition"]["metric"])}
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def report(self, study, stage=None):
        workspace = self._workspace(study)
        if stage is None:
            stage = workspace["current_stage"]
        row = self.db.execute("SELECT envelope FROM study_reports WHERE study = ? AND stage = ?", (study, stage)).fetchone()
        if row is None:
            raise ValueError("This stage has no committed report")
        return json.loads(row[0])

    def checkpoint(self, study, stage, replicate, treatment):
        row = self.db.execute("SELECT state, parent FROM study_jobs WHERE study = ? AND stage = ? AND replicate = ? AND treatment = ? AND status = 'complete'",
                              (study, stage, replicate, treatment)).fetchone()
        if row is None:
            raise ValueError("Completed study checkpoint is unavailable")
        state = json.loads(row["state"])
        return {"study": study, "stage": stage, "replicate": replicate, "treatment": treatment,
                "state": state, "digest": digest(state), "parent": json.loads(row["parent"]) if row["parent"] else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run durable staged treatment studies")
    parser.add_argument("database")
    sub = parser.add_subparsers(dest="operation", required=True)
    create = sub.add_parser("create")
    create.add_argument("specification")
    for name in ("work", "status", "preview", "report", "edit"):
        command = sub.add_parser(name)
        command.add_argument("study")
        if name == "work":
            command.add_argument("--steps", type=int, default=1000)
            command.add_argument("--offsets", type=int, default=1)
        elif name == "report":
            command.add_argument("--stage", type=int)
        elif name == "edit":
            command.add_argument("changes")
            command.add_argument("--expected-revision", type=int)
    args = parser.parse_args(argv)
    store = StudyStore(args.database)
    try:
        if args.operation == "create":
            result = store.create(**json.loads(Path(args.specification).read_text()))
        elif args.operation == "work":
            integer(args.steps, "Work steps", 1, 100000)
            integer(args.offsets, "Work offsets", 1, 121)
            for _ in range(args.steps):
                if store.work_once(args.study, args.offsets) is None:
                    break
            result = store.status(args.study)
        elif args.operation == "edit":
            result = store.edit_future(args.study, json.loads(Path(args.changes).read_text()), args.expected_revision)
        elif args.operation == "report":
            result = store.report(args.study, args.stage)
        else:
            result = getattr(store, args.operation)(args.study)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
