import copy, json, tempfile
from pathlib import Path
from mosslight.studies import StudyStore
from mosslight.model import World, Cell

def garden(seed=7):
    return World(seed,4,4,cells=[Cell(40,50,50) for _ in range(16)])
def note(content):
    return {"offset":0,"command":{"op":"note","args":{"content":content}}}
def treatments():
    return [{"name":"Moist shelter","events":[note("Moist shelter")]},
            {"name":"Fern edge","events":[note("Fern edge")]}]
def finish(store,ident):
    for _ in range(1000):
        if store.work_once(ident,offsets=4) is None:
            return store.status(ident)
    raise AssertionError("study did not quiesce")

# The same ordinary stage is completed with different sources first. A saved
# preview may become available, but every claimed slow member is still owed a
# place in the final cohort. Reopening preserves that distinction.
for first, reopen in (("north",False),("south",False),("north",True)):
  with tempfile.TemporaryDirectory() as temp:
    path=Path(temp)/"workspace.sqlite"
    store=StudyStore(path,clock=lambda:100)
    ident=store.create({"north":garden(7),"south":garden(11)},treatments(),
                       [{"until":2,"keep":1}],metric="moisture")
    claims=[]
    while (claim:=store.claim(ident,lease_seconds=30)) is not None:
        claims.append(claim)
    assert len(claims)==6
    for claim in reversed(claims):
        if claim["replicate"]==first:
            assert store.publish(claim,store.compute(claim,offsets=3))
    if reopen:
        store.close(); store=StudyStore(path,clock=lambda:100)
    preview=store.preview(ident)
    assert preview["common"]==[first] and not preview["terminal"]
    assert store.status(ident)["status"]=="running", "partial preview committed a final promotion before slow cohort members finished"
    try:
        store.report(ident,0)
    except ValueError:
        pass
    else:
        raise AssertionError("partial cohort acquired an immutable stage report")
    for claim in claims:
        if claim["replicate"]!=first:
            assert store.publish(claim,store.compute(claim,offsets=3))
    report=store.report(ident,0)
    assert report["decision"]["terminal"] and report["decision"]["pending"]==0
    assert report["decision"]["common"]==["north","south"]
    assert all(row["status"]=="complete" for row in report["outcomes"])
    store.close()
