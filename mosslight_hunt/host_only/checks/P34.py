import copy
from unittest.mock import patch
from mosslight import courier as c
# Record R is edited on a desktop while a remote device only receives the
# newer Q selection. This legitimately advances allocation clock, not R knowledge.
source=c.new_packet("desk")
c.put(source,"R",{"text":"old"})
receiver=copy.deepcopy(source);receiver["peer"]="field";receiver["counter"]=0
c.put(source,"R",{"text":"new"})
c.put(source,"Q",{"text":"weather"})
# Build a valid complete Q packet without using the separate projection path.
q=copy.deepcopy(source);q["events"]={k:v for k,v in q["events"].items() if v["record"]=="Q"};q["contexts"]={}
receiver=c.merge(receiver,q)
# Use the mathematical causal relation so the separate vector-comparison seed
# cannot mask this cross-record coverage regression.
correct=lambda a,b:all(a.get(k,0)<=b.get(k,0) for k in a.keys()|b.keys())
with patch.object(c,"precedes",side_effect=correct):
    compact=c.checkpoint(receiver)
    # This device never saw R's desk:3 text event or desk:4 presence event.
    assert compact["contexts"]["R"].get("desk",0)==2
    edited=copy.deepcopy(receiver);c.put(edited,"R",{"text":"field edit"})
    text_event=max((e for e in edited["events"].values() if e["peer"]=="field" and e["field"]=="text"),key=lambda e:e["counter"])
    assert text_event["context"].get("desk",0)==2
