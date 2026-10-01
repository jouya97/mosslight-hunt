from mosslight.engine import create
from mosslight.experiments import experiment
w=create(6,4,4); w.cells[0].species=None; w.cells[0].age=w.cells[0].vitality=0; w.cells[0].nutrients=50
r=experiment(w,1,[{"name":"plant","events":[{"offset":0,"command":{"op":"tend","args":{"x":0,"y":0,"action":"plant_moss"}}}]}])
assert r["branches"][1]["against_control"]["population_delta"]["moss"]==1
