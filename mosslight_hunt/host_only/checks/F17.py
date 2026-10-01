import random
from mosslight.weather import weather_on
seed=next(s for s in range(100) if .20 < random.Random(f"{s}:weather:0").random() < .46)
day=0; r=random.Random(f"{seed}:weather:{day}").random(); wet=.46
expected="storm" if r<wet*.12 else "rain" if r<wet*.55 else "drizzle" if r<wet else "clear"
assert weather_on(seed,day)["weather"]==expected
