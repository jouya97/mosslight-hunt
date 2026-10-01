"""Typed three-way reconciliation of raw garden saves with explicit provenance."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from .model import World

COLLECTIONS = ("notes", "specimens", "tasks", "beds", "plans", "rules", "nursery")
MISSING = object()


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(value):
    return hashlib.sha256(_encoded(value).encode()).hexdigest()


def _pointer(path):
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in path)


def _visible(value):
    return {"present": value is not MISSING, "value": None if value is MISSING else copy.deepcopy(value)}


def _clone(value):
    return MISSING if value is MISSING else copy.deepcopy(value)


def _merge(base, left, right, path, resolutions, conflicts, used):
    if left == right:
        return _clone(left)
    if left == base:
        return _clone(right)
    if right == base:
        return _clone(left)
    if all(isinstance(value, dict) for value in (base, left, right)):
        result = {}
        for key in sorted(set(base) | set(left) | set(right)):
            value = _merge(base.get(key, MISSING), left.get(key, MISSING), right.get(key, MISSING),
                           path + (key,), resolutions, conflicts, used)
            if value is not MISSING:
                result[key] = value
        return result
    pointer = _pointer(path)
    if pointer in resolutions:
        decision = resolutions[pointer]
        used.add(pointer)
        if set(decision) == {"choose"} and decision["choose"] in ("base", "left", "right"):
            return _clone({"base": base, "left": left, "right": right}[decision["choose"]])
        raise ValueError("A conflict resolution must choose base, left or right")
    conflicts.append({"path": pointer, "base": _visible(base), "left": _visible(left), "right": _visible(right)})
    return _clone(base)


def _logical_id(ident, origin, base_ids):
    return _encoded(["base", ident])


def _normalize(save, origin, base_ids):
    wb = save["workbench"]
    records = {}
    for collection in COLLECTIONS:
        records[collection] = {}
        for entry in wb[collection]:
            value = copy.deepcopy(entry)
            ident = value.pop("id")
            records[collection][_logical_id(ident, origin, base_ids)] = value
    snapshot = {key: copy.deepcopy(save[key]) for key in ("day", "weather", "cells", "journal")}
    snapshot["habitat"] = {key: copy.deepcopy(wb[key]) for key in
                           ("tiles", "inventory", "seeds", "history", "visitors", "nursery")}
    snapshot["habitat"]["nursery"] = records.pop("nursery")
    return {"ecology": _encoded(snapshot), "title": wb["title"], "records": records}


def reconcile(base, left, right, *, left_origin, right_origin, resolutions=None):
    for origin in (left_origin, right_origin):
        if not isinstance(origin, str) or not origin.strip() or len(origin) > 100 or origin == "base":
            raise ValueError("Replica origins must be nonempty labels other than 'base'")
    if left_origin == right_origin:
        raise ValueError("Independent replicas need distinct origin labels")
    if resolutions is None:
        resolutions = {}
    if not isinstance(resolutions, dict) or any(not isinstance(v, dict) for v in resolutions.values()):
        raise ValueError("Resolutions must map conflict paths to choices")
    source = [World.from_dict(copy.deepcopy(value)).to_dict() for value in (base, left, right)]
    base, left, right = source
    if any((value["seed"], value["width"], value["height"]) !=
           (base["seed"], base["width"], base["height"]) for value in (left, right)):
        raise ValueError("Saves must descend from the same garden and canvas")
    base_types = {entry["id"]: collection for collection in COLLECTIONS for entry in base["workbench"][collection]}
    base_ids = set(base_types)
    if any(value["workbench"]["next_id"] < base["workbench"]["next_id"] for value in (left, right)):
        raise ValueError("A replica allocation counter precedes its ancestor")
    for value in (left, right):
        for collection in COLLECTIONS:
            for entry in value["workbench"][collection]:
                if entry["id"] in base_types and base_types[entry["id"]] != collection:
                    raise ValueError("A replica changed an inherited entity's collection")
                if entry["id"] < base["workbench"]["next_id"] and entry["id"] not in base_ids:
                    raise ValueError("A replica recycled an identifier deleted before the ancestor")
    normalized = [_normalize(value, origin, base_ids) for value, origin in
                  zip(source, ("base", left_origin, right_origin))]
    conflicts, used = [], set()
    merged = _merge(*normalized, (), resolutions, conflicts, used)
    unused = set(resolutions) - used
    if unused:
        raise ValueError("Resolution does not match a current conflict: " + ", ".join(sorted(unused)))
    receipt = {"format": "mosslight-save-merge", "version": 1,
               "sources": {"base": _digest(base), left_origin: _digest(left), right_origin: _digest(right)},
               "resolutions": copy.deepcopy(resolutions)}
    if conflicts:
        return {"status": "conflict", "conflicts": conflicts, "receipt": receipt}
    ecology = json.loads(merged["ecology"])
    result = copy.deepcopy(base)
    for key in ("day", "weather", "cells", "journal"):
        result[key] = ecology[key]
    wb = result["workbench"]
    for key in ("tiles", "inventory", "seeds", "history", "visitors"):
        wb[key] = ecology["habitat"][key]
    merged["records"]["nursery"] = ecology["habitat"]["nursery"]
    wb["title"] = merged["title"]
    logical = [key for collection in COLLECTIONS for key in merged["records"][collection]]
    if len(logical) != len(set(logical)):
        raise ValueError("A replica moved an identifier between entity collections")
    allocation = {}
    next_id = max(value["workbench"]["next_id"] for value in source)
    for key in sorted(logical, key=lambda item: tuple(json.loads(item))):
        origin, ident = json.loads(key)
        if origin == "base":
            allocation[key] = ident
        else:
            allocation[key] = next_id
            next_id += 1
    for collection in COLLECTIONS:
        wb[collection] = sorted([dict(copy.deepcopy(value), id=allocation[key])
                                 for key, value in merged["records"][collection].items()], key=lambda item: item["id"])
    wb["next_id"] = next_id
    result["revision"] = max(left["revision"], right["revision"], base["revision"]) + 1
    try:
        result = World.from_dict(copy.deepcopy(result)).to_dict()
    except ValueError as error:
        return {"status": "incompatible", "reason": str(error), "receipt": receipt}
    receipt["allocation"] = allocation
    receipt["result_sha256"] = _digest(result)
    return {"status": "ready", "world": result, "receipt": receipt}


def verify_receipt(result, base, left, right, *, left_origin, right_origin):
    if result.get("status") != "ready":
        return False
    reproduced = reconcile(base, left, right, left_origin=left_origin, right_origin=right_origin,
                           resolutions=result.get("receipt", {}).get("resolutions", {}))
    return reproduced == result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "left", "right", "output"):
        parser.add_argument(name)
    parser.add_argument("--left-origin", required=True)
    parser.add_argument("--right-origin", required=True)
    parser.add_argument("--resolutions")
    args = parser.parse_args()
    read = lambda name: json.loads(Path(name).read_text(encoding="utf-8"))
    result = reconcile(read(args.base), read(args.left), read(args.right),
                       left_origin=args.left_origin, right_origin=args.right_origin,
                       resolutions=read(args.resolutions) if args.resolutions else None)
    output = Path(args.output)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(result["status"])


if __name__ == "__main__":
    main()
