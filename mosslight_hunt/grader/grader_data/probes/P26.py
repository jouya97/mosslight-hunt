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
p=c.new_packet("desk"); tags=["fern"]; tile=[1,2]
c.put(p,"pond",{"tags":tags,"tile":tile}); tags.append("changed"); tile[0]=3
result={e["field"]:e["value"] for e in p["events"].values() if e["field"]!="$alive"}
