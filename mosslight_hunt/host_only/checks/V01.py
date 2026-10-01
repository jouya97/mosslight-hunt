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
    now=[100]
    store=CampaignStore(Path(temp)/"workspace.sqlite",clock=lambda:now[0])
    ident=store.create(garden(),2,[{"name":"Observe","events":[]}])
    old=store.claim(ident,lease_seconds=10); computed=store.compute(old)
    now[0]=111; replacement=store.claim(ident,lease_seconds=10)
    assert replacement["ordinal"]==old["ordinal"]
    assert replacement["generation"]>old["generation"]
    assert store.publish(old,computed) is False, "retired worker published into a reclaimed branch"
    store.close()
