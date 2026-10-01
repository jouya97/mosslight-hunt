from mosslight.history import HistoryStore
from mosslight.model import World, Cell

def command(op, **args):
    return {"op": op, "args": args}

store = HistoryStore(":memory:")
world = World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)])
branch = store.create(world)["branch"]
first = store.append(branch, command("note", content="unrelated"))
store.append(branch, command("note", content="target"))
store.append(branch, command("note", content="bystander"))
source = store.append(branch, command("edit_note", ident=2, content="correct target"))
store.db.execute("DELETE FROM history_checkpoints")
result = store.correct(branch, {first["events"][0]["id"]: None})
assert result["status"] == "ready", result["conflicts"]
assert [(n["id"], n["text"]) for n in result["world"]["workbench"]["notes"]] == [(1, "correct target"), (2, "bystander")]
assert store.snapshot(branch) == source
store.close()
