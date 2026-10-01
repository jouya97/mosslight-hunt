from mosslight.history import HistoryStore
from mosslight.model import World, Cell

def command(op, **args):
    return {"op": op, "args": args}

store = HistoryStore(":memory:")
world = World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)])
branch = store.create(world)["branch"]
left = store.fork(branch)["branch"]
right = store.fork(branch)["branch"]
a = store.append(left, command("tend", x=0, y=0, action="water"))
store.append(right, command("tend", x=0, y=0, action="water"))
store.db.execute("DELETE FROM history_checkpoints")
picked = store.cherry_pick(left, right, [a["events"][0]["id"]])
assert len(picked["events"]) == 2
assert picked["world"]["cells"][0]["moisture"] == 64
store.db.execute("DELETE FROM history_checkpoints")
retried = store.cherry_pick(left, picked["branch"], [a["events"][0]["id"]])
assert retried["world"] == picked["world"]
assert picked["origin"]["selected_events"] == [a["events"][0]["id"]]
store.close()
