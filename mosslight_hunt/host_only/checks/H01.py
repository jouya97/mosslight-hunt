from mosslight.history import HistoryStore
from mosslight.model import World, Cell

def command(op, **args):
    return {"op": op, "args": args}

store = HistoryStore(":memory:")
world = World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)])
branch = store.create(world)["branch"]
first = store.append(branch, command("tend", x=0, y=0, action="water"))
source = store.append(branch, command("tend", x=1, y=0, action="compost"))
result = store.correct(branch, {first["events"][0]["id"]: command("tend", x=2, y=0, action="water")})
assert result["world"]["cells"][0]["moisture"] == 0
assert result["world"]["cells"][2]["moisture"] == 32
assert store.verify(result["branch"])["matches"]
assert store.snapshot(branch) == source
store.close()
