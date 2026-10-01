from mosslight.engine import create
from mosslight.planning import add_rule, run_rules
w=create(32,4,4); w.cells[0].moisture=20; w.cells[0].nutrients=20
add_rule(w,"Water",[[0,0]],"moisture","below",60,"water")
add_rule(w,"Feed",[[0,0]],"moisture","below",40,"compost")
run_rules(w)
assert w.cells[0].nutrients == 52
