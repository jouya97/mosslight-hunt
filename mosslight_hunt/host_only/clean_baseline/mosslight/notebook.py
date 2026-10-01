"""Searchable personal observations, a specimen cabinet, and dated tasks."""
from __future__ import annotations
from .state import identifier
from .validation import boolean, integer, tags, text


def _room(world, collection):
    if len(world.workbench[collection]) >= 500:
        raise ValueError(f"The {collection} collection is full")


def find_entry(world, collection, ident):
    integer(ident, "Identifier", 1)
    for entry in world.workbench[collection]:
        if entry["id"] == ident:
            return entry
    raise ValueError(f"No {collection} entry with id {ident}")


def add_note(world, content, labels=None, tile=None):
    content = text(content, "Note", 2000)
    labels = tags(labels or [])
    if tile is not None:
        if not isinstance(tile, (list, tuple)) or len(tile) != 2:
            raise ValueError("Tile must be [x, y]")
        world.index(*tile)
    _room(world, "notes")
    entry = {"id": identifier(world.workbench), "day": world.day, "text": content,
             "tags": labels, "tile": list(tile) if tile is not None else None}
    world.workbench["notes"].append(entry)
    world.revision += 1
    return entry.copy()


def edit_note(world, ident, content=None, labels=None):
    entry = find_entry(world, "notes", ident)
    new_text = entry["text"] if content is None else text(content, "Note", 2000)
    new_tags = entry["tags"] if labels is None else tags(labels)
    entry.update(text=new_text, tags=new_tags)
    world.revision += 1
    return entry.copy()


def delete_entry(world, collection, ident):
    if collection not in ("notes", "tasks", "specimens"):
        raise ValueError("Only notes, tasks and specimens can be removed here")
    entry = find_entry(world, collection, ident)
    world.workbench[collection].remove(entry)
    world.revision += 1


def search_notes(world, query="", tag=None, start=0, end=None):
    import copy
    query = text(query, "Search", 2000, blank=True).casefold()
    integer(start, "Start day")
    end = world.day if end is None else integer(end, "End day")
    if end < start:
        raise ValueError("End day precedes start day")
    if tag is not None:
        tag = text(tag, "Tag", 32).casefold()
    return copy.deepcopy([n for n in world.workbench["notes"] if start <= n["day"] <= end
                          and query in n["text"].casefold() and (tag is None or tag in n["tags"])])


def press_specimen(world, x, y, label=None):
    cell = world.cell(x, y)
    if not cell.species:
        raise ValueError("Select a living plant for the specimen cabinet")
    label = text(label or cell.species, "Specimen label", 100)
    _room(world, "specimens")
    entry = {"id": identifier(world.workbench), "day": world.day, "label": label,
             "tile": [x, y], **cell.to_dict()}
    world.workbench["specimens"].append(entry)
    world.revision += 1
    return entry.copy()


def add_task(world, content, due):
    content = text(content, "Task", 240)
    integer(due, "Due day")
    _room(world, "tasks")
    entry = {"id": identifier(world.workbench), "day": world.day, "text": content, "due": due, "done": False}
    world.workbench["tasks"].append(entry)
    world.revision += 1
    return entry.copy()


def complete_task(world, ident, done=True):
    boolean(done, "Completed")
    entry = find_entry(world, "tasks", ident)
    entry["done"] = done
    world.revision += 1


def task_list(world, status="open"):
    import copy
    if status not in ("all", "open", "done", "due", "overdue"):
        raise ValueError("Unknown task filter")
    tasks = world.workbench["tasks"]
    selected = [t for t in tasks if status == "all"
                or (status == "done" and t["done"])
                or (not t["done"] and (status == "open" or
                    (status == "due" and t["due"] <= world.day) or
                    (status == "overdue" and t["due"] < world.day)))]
    return copy.deepcopy(sorted(selected, key=lambda t: (t["due"], t["id"])))


def rename_garden(world, title):
    world.workbench["title"] = text(title, "Garden title", 100)
    world.revision += 1


def journal_search(world, query="", start=0, end=None):
    integer(start, "Start day")
    end = world.day if end is None else integer(end, "End day")
    if end < start:
        raise ValueError("End day precedes start")
    query = text(query, "Search", 240, blank=True).casefold()
    return [dict(e) for e in world.journal if start <= e["day"] <= end and query in e["text"].casefold()]
