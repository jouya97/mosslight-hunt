from mosslight.engine import create
from mosslight.experiments import experiment
w=create(7,4,4)
try: experiment(w,1,[{"name":"fern","events":[]},{"name":"Fern","events":[]}])
except ValueError: pass
else: raise AssertionError("case-folded duplicate was accepted")
