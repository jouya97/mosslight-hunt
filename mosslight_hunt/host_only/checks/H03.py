from mosslight.history import HistoryStore
from mosslight.model import World, Cell

def command(op, **args):
    return {"op": op, "args": args}

store = HistoryStore(":memory:")
world = World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)])
branch = store.create(world)["branch"]
store.append(branch, command("note", content="shared"))
child = store.fork(branch)["branch"]
local = store.append(child, command("tend", x=0, y=0, action="water"))
parent = store.append(branch, command("tend", x=1, y=0, action="compost"))
store.db.execute("DELETE FROM history_checkpoints")
rebased = store.rebase(child, branch)
assert len(rebased["events"]) == 3
assert rebased["world"]["cells"][0]["moisture"] == 32
assert rebased["world"]["cells"][1]["nutrients"] == 82
assert store.snapshot(child) == local and store.snapshot(branch) == parent
store.close()
