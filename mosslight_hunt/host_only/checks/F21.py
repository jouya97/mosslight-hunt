from mosslight.engine import create
from mosslight.experiments import experiment
w=create(4,4,4); w.cells[0].moisture=0
r=experiment(w,1,[{"name":"water once","events":[{"offset":0,"command":{"op":"tend","args":{"x":0,"y":0,"action":"water"}}}]}])
a,b=r["branches"][0]["samples"][-1]["averages"]["moisture"],r["branches"][1]["samples"][-1]["averages"]["moisture"]
assert 0 < b-a <= 3
