import copy
from unittest.mock import patch
from mosslight import courier as c
def event(peer,counter,record,field,value,context=None):
    return {"peer":peer,"counter":counter,"record":record,"field":field,"value":copy.deepcopy(value),"context":dict(context or {})}
def packet(peer,events=(),clock=None,contexts=None,counter=0):
    p=c.new_packet(peer); p.update(counter=counter,clock=dict(clock or {}),contexts=copy.deepcopy(contexts or {}))
    p["events"]={c._dot_key(e["peer"],e["counter"]):copy.deepcopy(e) for e in events}
    return p
def outcome(fn):
    try:
        return {"value":fn()}
    except Exception as exc:
        return {"exception":type(exc).__name__}
p=packet("desk",[event("desk",1,"pond","tags",["fern"]),event("desk",3,"private","text","hidden")],contexts={"pond":{"desk":2},"private":{"desk":4}})
result=[]
for selection in [["pond"],[],["private"]]:
    q=c.project(p,selection)
    result.append({"contexts":q["contexts"],"records":sorted(e["record"] for e in q["events"].values())})
