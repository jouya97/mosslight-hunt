from mosslight.engine import create
from mosslight.weather import next_weather
w=create(2,4,4); today=__import__("mosslight.weather",fromlist=["weather_on"]).weather_on(w.seed,w.day)["weather"]
r=next_weather(w,today,within=1)
assert r is None
