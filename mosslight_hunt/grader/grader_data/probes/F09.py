from mosslight.engine import create
from mosslight.analysis import forecast
w = create(9, 4, 4)
r = forecast(w, days=4, every=3)
result = [p["day"] for p in r["timeline"]]
