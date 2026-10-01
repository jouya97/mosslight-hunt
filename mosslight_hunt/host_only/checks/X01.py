import copy, json, tempfile
from pathlib import Path
from unittest.mock import patch
from mosslight.campaigns import CampaignStore
from mosslight.model import World, Cell
from mosslight.runtime import step_for

def garden():
    return World(7,4,4,cells=[Cell(68,50,50) for _ in range(16)])
def finish(store, ident):
    while store.work_once(ident):
        pass
    return store.result(ident)
with tempfile.TemporaryDirectory() as temp:
    w=garden()
    for tile in w.workbench["tiles"]: tile["structure"]="rain_barrel"
    store=CampaignStore(Path(temp)/"workspace.sqlite")
    ident=store.create(w,1,[{"name":"Observe","events":[]}],version="classic-1")
    store.work_once(ident)
    finish(store,ident)
    expected=copy.deepcopy(w); step_for("classic-1",expected)
    actual=store.checkpoint(ident,0,1)["state"]["world"]
    assert actual==expected.to_dict(), "resumed branch used another release"
    assert store.report(ident)["runtime"]["id"]=="classic-1"
    store.close()
