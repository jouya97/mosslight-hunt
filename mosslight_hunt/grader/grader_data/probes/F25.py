from mosslight.engine import create
from mosslight.experiments import experiment
w = create(7, 4, 4)
error=None
try:
    experiment(w,1,[{"name":"fern","events":[]},{"name":"Fern","events":[]}])
except Exception as exc:
    error=type(exc).__name__
result=error
