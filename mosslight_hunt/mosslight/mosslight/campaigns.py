"""Local experiment campaigns and saved progress."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
import uuid

from .analysis import census, compare
from .runtime import (DEFAULT_VERSION, execute_for, step_for, execution_version,
                      version_info, verify_runtime)
from .model import World, load
from .validation import integer, mapping, sequence, text


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def engine_fingerprint():
    return version_info(DEFAULT_VERSION)["fingerprint"]


def _definition(world, days, treatments, every, version=DEFAULT_VERSION):
    integer(days, "Experiment days", 1, 120)
    integer(every, "Sample interval", 1, 120)
    sequence(treatments, "Treatments", 8)
    if not treatments:
        raise ValueError("Supply at least one treatment")
    branches = [{"name": "control", "events": []}]
    names = {"control"}
    for treatment in treatments:
        mapping(treatment, "Treatment")
        name = text(treatment.get("name"), "Treatment name", 80)
        if name.casefold() in names:
            raise ValueError("Treatment names must be unique; control is reserved")
        names.add(name.casefold())
        events = sequence(treatment.get("events", []), "Treatment events", 100)
        for event in events:
            mapping(event, "Treatment event")
            integer(event.get("offset"), "Event offset", 0, days)
            command = mapping(event.get("command"), "Treatment command")
            if command.get("op") == "grow":
                raise ValueError("Experiment events cannot advance time")
        branches.append({"name": name, "events": copy.deepcopy(events)})
    return {"source": World.from_dict(world.to_dict()).to_dict(), "days": days,
            "every": every, "branches": branches, "engine": engine_fingerprint(),
            "runtime": version_info(version), "lineage": None}


class CampaignStore:

    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY, definition TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS branches (
                campaign TEXT NOT NULL REFERENCES campaigns(id),
                ordinal INTEGER NOT NULL, state TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                generation INTEGER NOT NULL DEFAULT 0,
                owner TEXT, lease_until REAL, error TEXT,
                PRIMARY KEY (campaign, ordinal));
            CREATE TABLE IF NOT EXISTS checkpoints (
                campaign TEXT NOT NULL, ordinal INTEGER NOT NULL, offset INTEGER NOT NULL,
                state TEXT NOT NULL, digest TEXT NOT NULL,
                PRIMARY KEY (campaign, ordinal, offset),
                FOREIGN KEY (campaign, ordinal) REFERENCES branches(campaign, ordinal));
            CREATE TABLE IF NOT EXISTS reports (
                campaign TEXT PRIMARY KEY REFERENCES campaigns(id), envelope TEXT NOT NULL);

        """)

    def close(self):
        self.db.close()

    def create(self, world, days, treatments, every=1, version=DEFAULT_VERSION):
        return self._create_definition(_definition(world, days, treatments, every, version))

    def _create_definition(self, definition, in_transaction=False):
        encoded = _json(definition)
        ident = hashlib.sha256(encoded.encode()).hexdigest()
        if not in_transaction:
            self.db.execute("BEGIN IMMEDIATE")
        try:
            cursor = self.db.execute("INSERT OR IGNORE INTO campaigns VALUES (?, ?)",
                                     (ident, encoded))
            if cursor.rowcount:
                for ordinal in range(len(definition["branches"])):
                    state = {"next_offset": 0, "world": definition["source"], "samples": []}
                    self.db.execute("INSERT INTO branches(campaign, ordinal, state) VALUES (?, ?, ?)",
                                    (ident, ordinal, _json(state)))
                    self._checkpoint(ident, ordinal, state)
            if not in_transaction:
                self.db.execute("COMMIT")
        except BaseException:
            if not in_transaction:
                self.db.execute("ROLLBACK")
            raise
        return ident

    def _definition(self, campaign):
        row = self.db.execute("SELECT definition FROM campaigns WHERE id = ?", (campaign,)).fetchone()
        if row is None:
            raise ValueError("Unknown campaign")
        return json.loads(row[0])

    def claim(self, campaign, lease_seconds=30):
        if not isinstance(lease_seconds, (int, float)) or isinstance(lease_seconds, bool) or not 0 < lease_seconds <= 3600:
            raise ValueError("Lease duration must be positive and at most one hour")
        definition = self._definition(campaign)
        if definition["engine"] != engine_fingerprint():
            raise ValueError("This campaign needs its original engine installation")
        verify_runtime(definition["runtime"])
        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("""SELECT * FROM branches WHERE campaign = ?
                AND (status = 'ready' OR (status = 'running' AND lease_until <= ?))
                ORDER BY ordinal LIMIT 1""", (campaign, now)).fetchone()
            if row is None:
                self.db.execute("COMMIT")
                return None
            owner = uuid.uuid4().hex
            generation = row["generation"] + 1
            self.db.execute("""UPDATE branches SET status = 'running', generation = ?,
                owner = ?, lease_until = ?, error = NULL WHERE campaign = ? AND ordinal = ?""",
                (generation, owner, now + lease_seconds, campaign, row["ordinal"]))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return {"campaign": campaign, "ordinal": row["ordinal"], "owner": owner,
                "generation": generation, "definition": definition,
                "state": json.loads(row["state"])}

    @staticmethod
    def compute(claim):
        definition = claim["definition"]
        state = copy.deepcopy(claim["state"])
        offset = state["next_offset"]
        world = World.from_dict(state["world"])
        version = execution_version(definition)
        for event in definition["branches"][claim["ordinal"]]["events"]:
            if event["offset"] == offset:
                execute_for(version, world, event["command"])
        if offset:
            step_for(version, world)
        if offset % definition["every"] == 0 or offset == definition["days"]:
            state["samples"].append({"offset": offset, "day": world.day, **census(world)})
        state["world"] = world.to_dict()
        state["next_offset"] = offset + 1
        return state

    def _checkpoint(self, campaign, ordinal, state):
        encoded = _json(state)
        self.db.execute("INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?)",
                        (campaign, ordinal, state["next_offset"] - 1, encoded,
                         hashlib.sha256(encoded.encode()).hexdigest()))

    def publish(self, claim, state):
        status = "complete" if state["next_offset"] > claim["definition"]["days"] else "ready"
        self.db.execute("BEGIN IMMEDIATE")
        try:
            cursor = self.db.execute("""UPDATE branches SET state = ?, status = ?,
                owner = NULL, lease_until = NULL WHERE campaign = ? AND ordinal = ?
                AND (generation = ? OR owner != ?) AND status = 'running'""",
                (_json(state), status, claim["campaign"], claim["ordinal"],
                 claim["generation"], claim["owner"]))
            accepted = cursor.rowcount == 1
            if accepted:
                self.db.execute("COMMIT")
                self.db.execute("BEGIN IMMEDIATE")
                self._checkpoint(claim["campaign"], claim["ordinal"], state)
                rows = self.db.execute("SELECT status FROM branches WHERE campaign = ?", (claim["campaign"],)).fetchall()
                if all(row["status"] == "complete" for row in rows):
                    self._archive_report(claim["campaign"])
            self.db.execute("COMMIT")
            return accepted
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def fail(self, claim, error):
        cursor = self.db.execute("""UPDATE branches SET status = 'failed', error = ?,
            owner = NULL, lease_until = NULL WHERE campaign = ? AND ordinal = ?
            AND generation = ? AND owner = ? AND status = 'running'""",
            (str(error), claim["campaign"], claim["ordinal"], claim["generation"], claim["owner"]))
        return cursor.rowcount == 1

    def work_once(self, campaign):
        claim = self.claim(campaign)
        if claim is None:
            return False
        try:
            state = self.compute(claim)
        except Exception as error:
            self.fail(claim, error)
        else:
            self.publish(claim, state)
        return True

    def cancel(self, campaign):
        self._definition(campaign)
        self.db.execute("""UPDATE branches SET status = 'cancelled', generation = generation + 1,
            owner = NULL, lease_until = NULL WHERE campaign = ? AND status IN ('ready', 'running')""",
            (campaign,))

    def status(self, campaign):
        self._definition(campaign)
        return [dict(row) for row in self.db.execute("""SELECT ordinal, status, generation, error
            FROM branches WHERE campaign = ? ORDER BY ordinal""", (campaign,))]

    def checkpoint(self, campaign, ordinal, offset):
        row = self.db.execute("SELECT state, digest FROM checkpoints WHERE campaign = ? AND ordinal = ? AND offset = ?",
                              (campaign, ordinal, offset)).fetchone()
        if row is None:
            raise ValueError("Checkpoint is unavailable")
        return {"campaign": campaign, "ordinal": ordinal, "offset": offset,
                "state": json.loads(row["state"]), "digest": row["digest"]}

    def fork(self, campaign, ordinal, offset, days=None, treatments=None, version=None, every=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            parent = self._definition(campaign)
            checkpoint = self.checkpoint(campaign, ordinal, offset)
            if days is None:
                days = parent["days"] - offset
            if treatments is None:
                remaining = []
                for event in parent["branches"][ordinal]["events"]:
                    if offset <= event["offset"] <= offset + days:
                        remaining.append({"offset": event["offset"] - offset,
                                          "command": copy.deepcopy(event["command"])})
                name = parent["branches"][ordinal]["name"] + " continuation"
                treatments = [{"name": name, "events": remaining}]
            definition = _definition(World.from_dict(checkpoint["state"]["world"]), days, treatments,
                                     parent["every"] if every is None else every,
                                     parent["runtime"]["id"] if version is None else version)
            definition["lineage"] = {key: checkpoint[key] for key in ("campaign", "ordinal", "offset", "digest")}
            result = self._create_definition(definition, in_transaction=True)
            self.db.execute("COMMIT")
            return result

        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def compact(self, campaign, keep_every=5):
        integer(keep_every, "Checkpoint interval", 1, 120)
        definition = self._definition(campaign)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            protected = set()
            for row in self.db.execute("SELECT definition FROM campaigns"):
                lineage = json.loads(row[0]).get("lineage")
                if lineage and lineage["campaign"] == campaign:
                    protected.add((lineage["ordinal"], lineage["offset"]))
            rows = self.db.execute("SELECT ordinal, offset FROM checkpoints WHERE campaign = ?", (campaign,)).fetchall()
            removed = 0
            for row in rows:
                key = (row["ordinal"], row["offset"])
                if row["offset"] in (-1, 0, definition["days"]) or row["offset"] % keep_every == 0:
                    continue
                self.db.execute("DELETE FROM checkpoints WHERE campaign = ? AND ordinal = ? AND offset = ?",
                                (campaign, *key))
                removed += 1
            self.db.execute("COMMIT")
            return removed
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _archive_report(self, campaign):
        definition = self._definition(campaign)
        rows = self.db.execute("SELECT * FROM branches WHERE campaign = ? ORDER BY ordinal", (campaign,)).fetchall()
        states = [json.loads(row["state"]) for row in rows]
        result = self._summarize(definition, states)
        envelope = {"schema": 1, "campaign": campaign, "runtime": definition["runtime"],
                    "source_digest": hashlib.sha256(_json(definition["source"]).encode()).hexdigest(),
                    "lineage": definition["lineage"], "result": result,
                    "result_digest": hashlib.sha256(_json(result).encode()).hexdigest()}
        self.db.execute("INSERT INTO reports VALUES (?, ?)", (campaign, _json(envelope)))

    @staticmethod
    def _summarize(definition, states):
        worlds = [World.from_dict(state["world"]) for state in states]
        branches = []
        for description, state, world in zip(definition["branches"], states, worlds):
            delta = compare(worlds[0], world)
            branches.append({"name": description["name"], "samples": state["samples"],
                             "final": census(world), "against_control": {
                                 key: delta[key] for key in ("changed_tiles", "population_delta", "coverage_delta")}})
        start = definition["source"]["day"]
        return {"start_day": start, "end_day": start + definition["days"], "branches": branches}

    def replay(self, campaign):
        definition = self._definition(campaign)
        verify_runtime(definition["runtime"])
        states = []
        for ordinal in range(len(definition["branches"])):
            state = {"next_offset": 0, "world": copy.deepcopy(definition["source"]), "samples": []}
            for _ in range(definition["days"] + 1):
                state = self.compute({"definition": definition, "ordinal": ordinal, "state": state})
            states.append(state)
        return self._summarize(definition, states)

    def provenance(self, campaign):
        chain = []
        seen = set()
        while campaign not in seen:
            seen.add(campaign)
            definition = self._definition(campaign)
            chain.append({"campaign": campaign, "runtime": definition["runtime"],
                          "source_digest": hashlib.sha256(_json(definition["source"]).encode()).hexdigest()})
            lineage = definition["lineage"]
            if lineage is None:
                return chain
            anchor = self.checkpoint(lineage["campaign"], lineage["ordinal"], lineage["offset"])
            if anchor["digest"] != lineage["digest"]:
                raise ValueError("Historical checkpoint fingerprint changed")
            campaign = lineage["campaign"]
        raise ValueError("Historical lineage contains a cycle")

    def report(self, campaign):
        definition = self._definition(campaign)
        row = self.db.execute("SELECT envelope FROM reports WHERE campaign = ?", (campaign,)).fetchone()
        if row is not None:
            return json.loads(row[0])
        if definition["engine"] != engine_fingerprint():
            raise ValueError("This campaign needs its original engine installation")
        raise ValueError("Campaign is not complete")

    def result(self, campaign):
        return self.report(campaign)["result"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Resume local garden experiment campaigns")
    parser.add_argument("database")
    sub = parser.add_subparsers(dest="operation", required=True)
    create = sub.add_parser("create")
    create.add_argument("garden")
    create.add_argument("treatments")
    create.add_argument("--days", type=int, required=True)
    create.add_argument("--every", type=int, default=1)
    create.add_argument("--version", default=DEFAULT_VERSION)
    fork = sub.add_parser("fork")
    fork.add_argument("campaign")
    fork.add_argument("--branch", type=int, required=True)
    fork.add_argument("--offset", type=int, required=True)
    fork.add_argument("--days", type=int)
    fork.add_argument("--version")
    compact = sub.add_parser("compact")
    compact.add_argument("campaign")
    compact.add_argument("--every", type=int, default=5)
    for name in ("work", "status", "result", "report", "replay", "provenance", "cancel"):
        command = sub.add_parser(name)
        command.add_argument("campaign")
        if name == "work":
            command.add_argument("--steps", type=int, default=100)
    args = parser.parse_args(argv)
    store = CampaignStore(args.database)
    try:
        if args.operation == "create":
            print(store.create(load(args.garden), args.days,
                               json.loads(Path(args.treatments).read_text()), args.every, args.version))
        elif args.operation == "fork":
            print(store.fork(args.campaign, args.branch, args.offset, days=args.days, version=args.version))
        elif args.operation == "compact":
            print(store.compact(args.campaign, args.every))
        elif args.operation in ("report", "replay", "provenance"):
            print(json.dumps(getattr(store, args.operation)(args.campaign), indent=2))
        elif args.operation == "work":
            integer(args.steps, "Work steps", 1, 100000)
            for _ in range(args.steps):
                if not store.work_once(args.campaign):
                    break
            print(json.dumps(store.status(args.campaign), indent=2))
        elif args.operation == "status":
            print(json.dumps(store.status(args.campaign), indent=2))
        elif args.operation == "result":
            print(json.dumps(store.result(args.campaign), indent=2))
        else:
            store.cancel(args.campaign)
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
