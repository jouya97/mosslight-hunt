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
source=c.new_packet("desk"); c.put(source,"R",{"text":"old"})
receiver=copy.deepcopy(source); receiver["peer"]="field"; receiver["counter"]=0
c.put(source,"R",{"text":"new"}); c.put(source,"Q",{"text":"weather"})
q=copy.deepcopy(source); q["events"]={k:v for k,v in q["events"].items() if v["record"]=="Q"}; q["contexts"]={}
receiver=c.merge(receiver,q)
correct=lambda a,b:all(a.get(k,0)<=b.get(k,0) for k in a.keys()|b.keys())
with patch.object(c,"precedes",side_effect=correct):
    compact=c.checkpoint(receiver)
    edited=copy.deepcopy(receiver); c.put(edited,"R",{"text":"field edit"})
    text_event=max((e for e in edited["events"].values() if e["peer"]=="field" and e["field"]=="text"),key=lambda e:e["counter"])
result=[compact["contexts"],text_event["context"],receiver["clock"]]
