"""Complete offline history parcels and causal publication reconciliation."""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys
import uuid

from .history import HistoryConflict, HistoryStore, _digest, _json, _rebase_events, _version_info
from .model import World


def _label(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise ValueError(name + " must be nonblank text of at most 100 characters")
    return value.strip()


class HistoryExchange:
    def __init__(self, path):
        self.history = HistoryStore(path)
        self.db = self.history.db
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS exchange_channels (
                id TEXT PRIMARY KEY, root TEXT NOT NULL REFERENCES history_roots(id), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS exchange_publications (
                id TEXT PRIMARY KEY, channel TEXT NOT NULL REFERENCES exchange_channels(id), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS exchange_checkouts (
                branch TEXT PRIMARY KEY REFERENCES history_branches(id),
                channel TEXT NOT NULL REFERENCES exchange_channels(id), parents TEXT NOT NULL);
        """)

    def close(self):
        self.history.close()

    @contextmanager
    def _atomic(self, *, write=True):
        self.db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _channel(self, ident):
        row = self.db.execute("SELECT body FROM exchange_channels WHERE id = ?", (ident,)).fetchone()
        if row is None:
            raise ValueError("Unknown exchange channel")
        return json.loads(row[0])

    def _publication(self, ident):
        row = self.db.execute("SELECT body FROM exchange_publications WHERE id = ?", (ident,)).fetchone()
        if row is None:
            raise ValueError("Unknown history publication")
        return json.loads(row[0])

    def _graph(self, channel):
        return {row["id"]: json.loads(row["body"]) for row in self.db.execute(
            "SELECT id, body FROM exchange_publications WHERE channel = ?", (channel,))}

    @staticmethod
    def _ancestors(ident, graph):
        found, pending = set(), [ident]
        while pending:
            current = pending.pop()
            if current not in found:
                if current not in graph:
                    raise ValueError("Publication ancestry is incomplete")
                found.add(current)
                pending.extend(graph[current]["parents"])
        return found

    @staticmethod
    def _frontier(graph):
        parents = {parent for publication in graph.values() for parent in publication["parents"]}
        return sorted(set(graph) - parents)

    def heads(self, channel):
        self._channel(channel)
        return self._frontier(self._graph(channel))

    def _materialize(self, root, events):
        result = self.history._replay(root, copy.deepcopy(events), use_cache=False)
        if result["conflicts"]:
            conflict = result["conflicts"][0]
            raise HistoryConflict(conflict["kind"], conflict["message"],
                                  event=conflict.get("event"), reference=conflict.get("reference"))
        return result

    def _checked_revision(self, branch):
        description = self.history._branch(branch)
        revision = self.history._revision(description["head"])
        root = self.history._root(description["root"])
        fresh = self._materialize(root, revision["events"])
        if fresh != revision["result"]:
            raise ValueError("Stored history differs from its authoritative replay; verify it before publishing")
        return revision

    @staticmethod
    def _new_publication(channel, revision, parents, author):
        body = {"channel": channel, "revision": revision, "parents": sorted(set(parents)),
                "author": _label(author, "Author"), "nonce": uuid.uuid4().hex}
        return _digest(body), body

    def _put_publication(self, ident, body):
        if _digest(body) != ident:
            raise ValueError("Publication identity does not match its content")
        encoded = _json(body)
        old = self.db.execute("SELECT body FROM exchange_publications WHERE id = ?", (ident,)).fetchone()
        if old is not None and old[0] != encoded:
            raise ValueError("Conflicting immutable publication")
        self.db.execute("INSERT OR IGNORE INTO exchange_publications VALUES (?, ?, ?)",
                        (ident, body["channel"], encoded))

    def announce(self, branch, *, author, name="garden"):
        revision = self._checked_revision(branch)
        channel = uuid.uuid4().hex
        ident, publication = self._new_publication(channel, revision["id"], [], author)
        body = {"id": channel, "root": revision["root"], "genesis": ident, "name": _label(name, "Channel name")}
        with self._atomic():
            self.db.execute("INSERT INTO exchange_channels VALUES (?, ?, ?)", (channel, revision["root"], _json(body)))
            self._put_publication(ident, publication)
        return {"channel": channel, "publication": ident, "revision": revision["id"], "branch": branch}

    def _checkout(self, publication, label=None):
        node = self._publication(publication)
        channel = self._channel(node["channel"])
        revision = self.history._revision(node["revision"])
        branch = uuid.uuid4().hex
        self.db.execute("INSERT INTO history_branches VALUES (?, ?, ?, ?, NULL, ?)",
                        (branch, label or channel["name"], channel["root"], revision["id"], revision["id"]))
        self.db.execute("INSERT INTO history_origins VALUES (?, ?)", (branch, _json({
            "operation": "exchange-checkout", "publication": publication, "source_revision": revision["id"]})))
        self.db.execute("INSERT INTO exchange_checkouts VALUES (?, ?, ?)",
                        (branch, channel["id"], _json([publication])))
        return {**self.history.snapshot(branch), "channel": channel["id"], "publication": publication}

    def checkout(self, publication, label=None):
        if label is not None:
            label = _label(label, "Branch label")
        with self._atomic():
            return self._checkout(publication, label)

    def publish(self, branch, *, checkout, author):
        receipt = self.db.execute("SELECT * FROM exchange_checkouts WHERE branch = ?", (checkout,)).fetchone()
        if receipt is None:
            raise ValueError("Choose the checkout from which this line of work started")
        channel = self._channel(receipt["channel"])
        revision = self._checked_revision(branch)
        if revision["root"] != channel["root"]:
            raise ValueError("Published history belongs to another imported root")
        ident, publication = self._new_publication(channel["id"], revision["id"], json.loads(receipt["parents"]), author)
        with self._atomic():
            cursor = self.db.execute("UPDATE exchange_checkouts SET parents = ? WHERE branch = ? AND parents = ?",
                                     (_json([ident]), checkout, receipt["parents"]))
            if cursor.rowcount != 1:
                raise HistoryConflict("stale-checkout", "Another publication advanced this checkout")
            self._put_publication(ident, publication)
        return {"channel": channel["id"], "publication": ident, "revision": revision["id"],
                "branch": branch, "heads": self.heads(channel["id"])}

    def export(self, channel, *, heads=None):
        with self._atomic(write=False):
            descriptor = self._channel(channel)
            graph = self._graph(channel)
            selected = self._frontier(graph) if heads is None else sorted(set(heads))
            if not selected or any(ident not in graph for ident in selected):
                raise ValueError("Select known publications from this channel")
            needed = set().union(*(self._ancestors(ident, graph) for ident in selected))
            publications = {ident: graph[ident] for ident in sorted(needed)}
            revisions = {node["revision"]: self.history._revision(node["revision"])
                         for node in publications.values()}
            body = {"format": 1, "channel": descriptor, "root": self.history._root(descriptor["root"]),
                    "publications": publications, "revisions": revisions, "selected": selected}
            return {"body": body, "checksum": _digest(body)}

    def _validate_graph(self, channel, graph):
        if channel["genesis"] not in graph:
            raise ValueError("Parcel omits its channel genesis")
        remaining = {}
        successors = {ident: [] for ident in graph}
        for ident, node in graph.items():
            if node["channel"] != channel["id"] or not isinstance(node["parents"], list):
                raise ValueError("Publication belongs to another channel")
            if len(node["parents"]) != len(set(node["parents"])):
                raise ValueError("Publication repeats a parent")
            if (ident == channel["genesis"]) != (not node["parents"]):
                raise ValueError("Only the channel genesis may lack parents")
            revision = self.history._revision(node["revision"])
            if revision["root"] != channel["root"]:
                raise ValueError("Publication revision belongs to another root")
            remaining[ident] = len(node["parents"])
            for parent in node["parents"]:
                if parent not in graph:
                    raise ValueError("Parcel has incomplete publication ancestry")
                successors[parent].append(ident)
        ready = [ident for ident, count in remaining.items() if count == 0]
        visited = 0
        while ready:
            current = ready.pop()
            visited += 1
            for child in successors[current]:
                remaining[child] -= 1
                if remaining[child] == 0:
                    ready.append(child)
        if visited != len(graph):
            raise ValueError("Publication ancestry contains a cycle")

    def receive(self, parcel):
        # Own the whole input before validation and before any database writes.
        parcel = json.loads(_json(parcel))
        if set(parcel) != {"body", "checksum"} or _digest(parcel["body"]) != parcel["checksum"]:
            raise ValueError("Parcel checksum is invalid")
        body = parcel["body"]
        if body.get("format") != 1:
            raise ValueError("Unsupported history parcel format")
        try:
            channel, root = body["channel"], body["root"]
            if root["id"] != channel["root"] or root["world"] != World.from_dict(root["world"]).to_dict():
                raise ValueError("Invalid original history root")
            if root["engine"] != _version_info(root["engine"]["id"]):
                raise ValueError("Parcel needs its recorded interpreter installation")
            _label(channel["name"], "Channel name")
            with self._atomic():
                existing = self.db.execute("SELECT body FROM history_roots WHERE id = ?", (root["id"],)).fetchone()
                if existing is not None and existing[0] != _json(root):
                    raise ValueError("Conflicting immutable history root")
                self.db.execute("INSERT OR IGNORE INTO history_roots VALUES (?, ?)", (root["id"], _json(root)))
                existing = self.db.execute("SELECT body FROM exchange_channels WHERE id = ?", (channel["id"],)).fetchone()
                if existing is not None and existing[0] != _json(channel):
                    raise ValueError("Conflicting immutable channel")
                self.db.execute("INSERT OR IGNORE INTO exchange_channels VALUES (?, ?, ?)",
                                (channel["id"], channel["root"], _json(channel)))
                for ident, revision in body["revisions"].items():
                    if revision["id"] != ident or revision["root"] != root["id"]:
                        raise ValueError("Revision has an inconsistent identity")
                    if _digest({"root": root["id"], "events": revision["events"]}) != ident:
                        raise ValueError("Revision hash does not match its authored events")
                    event_ids = [event["id"] for event in revision["events"]]
                    if len(event_ids) != len(set(event_ids)):
                        raise ValueError("Revision repeats an authored event")
                    fresh = self._materialize(root, revision["events"])
                    if fresh != revision["result"]:
                        raise ValueError("Revision result differs from its authored replay")
                    old = self.db.execute("SELECT result FROM history_revisions WHERE id = ?", (ident,)).fetchone()
                    if old is not None and old[0] != _json(fresh):
                        raise ValueError("Conflicting immutable revision")
                    self.history._store_revision(root["id"], revision["events"], fresh)
                # A parcel is self-contained even when this receiver knows more.
                for ident, node in body["publications"].items():
                    if node["revision"] not in body["revisions"]:
                        raise ValueError("Parcel omits a referenced revision")
                    _label(node["author"], "Author")
                    self._put_publication(ident, node)
                self._validate_graph(channel, body["publications"])
                if not body["selected"] or any(ident not in body["publications"] for ident in body["selected"]):
                    raise ValueError("Parcel selects absent publications")
                self._validate_graph(channel, self._graph(channel["id"]))
                result = {"channel": channel["id"], "heads": self.heads(channel["id"])}
            return result
        except (KeyError, TypeError, IndexError) as error:
            raise ValueError("Malformed history parcel") from error

    @staticmethod
    def _common_bases(left_ancestors, right_ancestors, ancestors):
        common = left_ancestors & right_ancestors
        maximal = sorted(ident for ident in common
                         if not any(ident != other and ident in ancestors[other] for other in common))
        return maximal

    def _merge_events(self, left, right, graph):
        ancestors = {ident: self._ancestors(ident, graph) for ident in graph}
        events = {ident: self.history._revision(node["revision"])["events"] for ident, node in graph.items()}
        memo = {}

        def comparison(bases):
            key = tuple(sorted(bases))
            if not key:
                raise HistoryConflict("unrelated-publications", "Publications have no common origin")
            if key not in memo:
                result, tips = events[key[0]], {key[0]}
                for ident in key[1:]:
                    try:
                        result = merge(result, tips, events[ident], {ident})
                    except HistoryConflict as error:
                        raise HistoryConflict("ambiguous-ancestry", "Common histories conflict: " + str(error)) from error
                    tips.add(ident)
                memo[key] = result
            return memo[key]

        def merge(left_events, left_tips, right_events, right_tips):
            left_seen = set().union(*(ancestors[ident] for ident in left_tips))
            right_seen = set().union(*(ancestors[ident] for ident in right_tips))
            if left_tips <= right_seen:
                return copy.deepcopy(right_events)
            if right_tips <= left_seen:
                return copy.deepcopy(left_events)
            bases = self._common_bases(left_seen, right_seen, ancestors)
            base = comparison(bases)
            return _rebase_events(base, left_events, right_events)

        return merge(events[left], {left}, events[right], {right})

    def reconcile(self, left, right, *, author):
        left_node, right_node = self._publication(left), self._publication(right)
        if left_node["channel"] != right_node["channel"]:
            raise ValueError("Reconciliation requires one shared history channel")
        channel = self._channel(left_node["channel"])
        graph = self._graph(channel["id"])
        if left in self._ancestors(right, graph):
            return {**self.checkout(right), "status": "fast-forward"}
        if right in self._ancestors(left, graph):
            return {**self.checkout(left), "status": "fast-forward"}
        events = self._merge_events(left, right, graph)
        root = self.history._root(channel["root"])
        result = self._materialize(root, events)
        with self._atomic():
            revision = self.history._store_revision(root["id"], events, result)
            ident, node = self._new_publication(channel["id"], revision, [left, right], author)
            self._put_publication(ident, node)
            checked = self._checkout(ident)
        return {**checked, "status": "merged", "revision": revision}

    def resolve(self, channel, branch, *, author, expected_heads=None):
        descriptor = self._channel(channel)
        observed = self.heads(channel) if expected_heads is None else sorted(set(expected_heads))
        if not observed or observed != self.heads(channel):
            raise HistoryConflict("stale-resolution", "Channel heads changed before resolution")
        revision = self._checked_revision(branch)
        if revision["root"] != descriptor["root"]:
            raise ValueError("Resolution belongs to another imported root")
        ident, publication = self._new_publication(channel, revision["id"], observed, author)
        with self._atomic():
            if self.heads(channel) != observed:
                raise HistoryConflict("stale-resolution", "Channel heads changed during resolution")
            self._put_publication(ident, publication)
            checked = self._checkout(ident)
        return {**checked, "status": "resolved"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Exchange authored garden histories offline")
    parser.add_argument("database")
    sub = parser.add_subparsers(dest="operation", required=True)
    announce = sub.add_parser("announce")
    announce.add_argument("branch"); announce.add_argument("--author", required=True)
    announce.add_argument("--name", default="garden")
    export = sub.add_parser("export")
    export.add_argument("channel"); export.add_argument("output")
    export.add_argument("--heads", nargs="+")
    receive = sub.add_parser("receive"); receive.add_argument("parcel")
    checkout = sub.add_parser("checkout"); checkout.add_argument("publication")
    checkout.add_argument("--label")
    publish = sub.add_parser("publish"); publish.add_argument("branch")
    publish.add_argument("--checkout", required=True); publish.add_argument("--author", required=True)
    heads = sub.add_parser("heads"); heads.add_argument("channel")
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("left"); reconcile.add_argument("right"); reconcile.add_argument("--author", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("channel"); resolve.add_argument("branch"); resolve.add_argument("--author", required=True)
    args = parser.parse_args(argv)
    store = HistoryExchange(args.database)
    try:
        if args.operation == "announce":
            result = store.announce(args.branch, author=args.author, name=args.name)
        elif args.operation == "export":
            parcel = store.export(args.channel, heads=args.heads)
            Path(args.output).write_text(json.dumps(parcel, ensure_ascii=False, indent=2) + "\n")
            result = {"output": args.output, "checksum": parcel["checksum"]}
        elif args.operation == "receive":
            result = store.receive(json.loads(Path(args.parcel).read_text()))
        elif args.operation == "checkout":
            result = store.checkout(args.publication, args.label)
        elif args.operation == "publish":
            result = store.publish(args.branch, checkout=args.checkout, author=args.author)
        elif args.operation == "heads":
            result = store.heads(args.channel)
        elif args.operation == "reconcile":
            result = store.reconcile(args.left, args.right, author=args.author)
        else:
            result = store.resolve(args.channel, args.branch, author=args.author)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(_json(error.details if isinstance(error, HistoryConflict) else {"error": str(error)}), file=sys.stderr)
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
