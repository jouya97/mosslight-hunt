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
result=[c.precedes(a,b) for a,b in [({"desk":1},{"field":1}),({"desk":1},{}),({}, {"desk":1}),({"desk":2},{"desk":2}),({"desk":3},{"desk":2}),({"desk":1,"field":2},{"desk":2,"field":3})]]
