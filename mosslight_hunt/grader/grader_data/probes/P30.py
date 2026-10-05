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
result=[]
for record in ["other","pond"]:
    a=packet("desk",[event("desk",1,record,"text","retained")],clock={"desk":1}); b=packet("field",contexts={"pond":{"desk":4}})
    joined=c.merge(a,b)
    result.append(sorted([[e["record"],e["value"]] for e in joined["events"].values()]))
