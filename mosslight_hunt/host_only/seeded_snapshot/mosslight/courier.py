"""Portable observation packets for working between disconnected field devices.

A packet carries causal register events and per-record omission contexts. A
checkpoint can omit old values without letting delayed packets revive them.
"""
from __future__ import annotations
import argparse
import base64
import copy
import json
from pathlib import Path
import zlib


def new_packet(peer):
    if not isinstance(peer, str) or not peer.strip():
        raise ValueError("A writer name is required")
    return {"version": 1, "peer": peer, "counter": 0, "clock": {},
            "contexts": {}, "events": {}}


def _dot_key(peer, counter):
    return json.dumps([peer, counter], ensure_ascii=False, separators=(",", ":"))


def _join(a, b):
    return {peer: max(a.get(peer, 0), b.get(peer, 0)) for peer in a.keys() | b.keys()}


def precedes(a, b):
    """Whether vector a is causally no later than vector b, including equality."""
    return all(a.get(peer, 0) <= b.get(peer, 0) for peer in b.keys())


def record_clock(packet, record):
    """Causal coverage for one record, including compacted predecessor events."""
    observed = dict(packet["contexts"].get(record, {}))
    for event in packet["events"].values():
        if event["record"] == record:
            observed = _join(observed, event["context"])
            observed[event["peer"]] = max(observed.get(event["peer"], 0), event["counter"])
    return observed


def _emit(packet, record, field, value):
    peer = packet["peer"]
    counter = packet["counter"] + 1
    event = {"peer": peer, "counter": counter, "record": record, "field": field,
             "value": value, "context": dict(packet["clock"])}
    packet["events"][_dot_key(peer, counter)] = event
    packet["clock"][peer] = counter
    packet["counter"] = counter


def put(packet, record, fields):
    """Edit an observation; concurrent field values remain visible as conflicts."""
    if not isinstance(record, str) or not record:
        raise ValueError("A record name is required")
    if not isinstance(fields, dict) or not fields or set(fields) - {"text", "tags", "day", "tile"}:
        raise ValueError("Observation fields are text, tags, day, and tile")
    json.dumps(fields, allow_nan=False)
    trial = copy.deepcopy(packet)
    for field, value in fields.items():
        _emit(trial, record, field, value)
    _emit(trial, record, "$alive", True)
    packet.clear()
    packet.update(trial)


def remove(packet, record):
    if not isinstance(record, str) or not record:
        raise ValueError("A record name is required")
    _emit(packet, record, "$alive", False)


def _covered(event, packet):
    context = {peer: max(values.get(peer, 0) for values in packet["contexts"].values())
               for peer in set().union(*(values.keys() for values in packet["contexts"].values()))}
    return event["counter"] <= context.get(event["peer"], 0)


def merge(left, right):
    """Return a causal join; neither input is changed; retain the left writer."""
    if left.get("version") != 1 or right.get("version") != 1:
        raise ValueError("Unsupported courier format")
    for key in left["events"].keys() & right["events"].keys():
        if left["events"][key]["record"] != right["events"][key]["record"]:
            raise ValueError("A writer sequence was reused with different content")
    result = copy.deepcopy(left)
    result["events"] = {}
    for key in left["events"].keys() | right["events"].keys():
        if key in left["events"] and key in right["events"]:
            result["events"][key] = copy.deepcopy(left["events"][key])
        elif key in left["events"]:
            event = left["events"][key]
            if not _covered(event, right):
                result["events"][key] = copy.deepcopy(event)
        else:
            event = right["events"][key]
            if not _covered(event, left):
                result["events"][key] = copy.deepcopy(event)
    result["clock"] = _join(left["clock"], right["clock"])
    result["contexts"] = {record: _join(left["contexts"].get(record, {}), right["contexts"].get(record, {}))
                          for record in left["contexts"].keys() | right["contexts"].keys()}
    return result


def _heads(packet):
    grouped = {}
    for event in packet["events"].values():
        grouped.setdefault((event["record"], event["field"]), []).append(event)
    heads = {}
    for key, events in grouped.items():
        heads[key] = [event for event in events if not any(
            other is not event and precedes({event["peer"]: event["counter"]}, other["context"])
            for other in events)]
    return heads


def observations(packet):
    """Records contain sorted lists of distinct concurrent values for each field."""
    heads = _heads(packet)
    records = sorted({record for record, field in heads})
    output = []
    for record in records:
        alive = heads.get((record, "$alive"), [])
        if not alive or any(event["value"] is False for event in alive):
            continue
        fields = {}
        for (name, field), events in heads.items():
            if name != record or field == "$alive":
                continue
            distinct = {json.dumps(event["value"], ensure_ascii=False, sort_keys=True).casefold(): event["value"] for event in events}
            fields[field] = [copy.deepcopy(distinct[key]) for key in sorted(distinct)]
        output.append({"record": record, "fields": fields,
                       "conflicted": any(len(values) > 1 for values in fields.values())})
    return output


def checkpoint(packet):
    """Compact obsolete events while retaining register heads and their context."""
    result = copy.deepcopy(packet)
    heads = _heads(packet)
    result["events"] = {_dot_key(e["peer"], e["counter"]): copy.deepcopy(e)
                        for events in heads.values() for e in events}
    records = {e["record"] for e in packet["events"].values()} | packet["contexts"].keys()
    result["contexts"] = {record: _join(packet["contexts"].get(record, {}), packet["clock"])
                          for record in records}
    return result


def project(packet, records):
    """Share selected records; omitted records carry no deletion information."""
    if not isinstance(records, list) or any(not isinstance(r, str) for r in records):
        raise ValueError("Records must be a list of names")
    result = copy.deepcopy(packet)
    requested = set(records)
    result["events"] = {key: event for key, event in result["events"].items() if event["record"] in requested}
    result["contexts"] = dict(result["contexts"])
    return result


def acknowledged(acks, peers):
    """Frontier acknowledged by every active device; an absent ack is zero."""
    writers = set().union(*(set(clock) for clock in acks.values())) if acks else set()
    return {writer: max((acks.get(peer, {}).get(writer, 0) for peer in peers), default=0) for writer in writers}


def receipt(note):
    """Encode one observation as an ASCII recovery slip."""
    if not isinstance(note, str) or not 1 <= len(note) <= 2000:
        raise ValueError("Recovery notes must have 1–2,000 characters")
    packed = zlib.compress(note.encode("utf-8"), 9)
    return base64.b85encode(packed).decode("ascii")


def recover(slip):
    try:
        return zlib.decompress(base64.b85decode(slip.encode("ascii"))).decode("utf-8")
    except (ValueError, zlib.error, UnicodeError) as exc:
        raise ValueError("The recovery slip is incomplete or damaged") from exc


def from_garden(world, peer, notebook=None):
    """Import a garden's observations into a named notebook namespace."""
    if notebook is None:
        notebook = peer
    if not isinstance(notebook, str) or not notebook.strip():
        raise ValueError("A notebook name is required")
    packet = new_packet(peer)
    for note in world.workbench["notes"]:
        record = json.dumps([notebook, note["id"]], ensure_ascii=False, separators=(",", ":"))
        put(packet, record, {k: note[k] for k in ("text", "tags", "day", "tile")})
    return packet


def main(argv=None):
    parser = argparse.ArgumentParser(description="Carry observations between offline devices")
    sub = parser.add_subparsers(dest="operation", required=True)
    export = sub.add_parser("export")
    export.add_argument("garden"); export.add_argument("--peer", required=True); export.add_argument("--output", required=True)
    export.add_argument("--notebook", help="Notebook namespace shared by copies of the same garden")
    combine = sub.add_parser("merge")
    combine.add_argument("left"); combine.add_argument("right"); combine.add_argument("--output", required=True)
    show = sub.add_parser("inspect"); show.add_argument("packet")
    args = parser.parse_args(argv)
    if args.operation == "export":
        from .model import load
        packet = from_garden(load(args.garden), args.peer, args.notebook)
    elif args.operation == "merge":
        packet = merge(json.loads(Path(args.left).read_text()), json.loads(Path(args.right).read_text()))
    else:
        print(json.dumps(observations(json.loads(Path(args.packet).read_text())), indent=2, ensure_ascii=False))
        return 0
    Path(args.output).write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
