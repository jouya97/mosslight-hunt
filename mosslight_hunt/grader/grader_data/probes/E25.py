from mosslight.engine import create
from mosslight.planning import add_bed
w = create(28, 4, 4)
add_bed(w, 'North', [[0, 0]])
error=None
try:
    add_bed(w,"north",[[1,0]])
except Exception as exc:
    error=type(exc).__name__
result=error
