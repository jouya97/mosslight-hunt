from mosslight.engine import create
import mosslight.weather as weather
weather.weather_on=lambda seed,day: {"day":day,"weather":"rain" if day % 2 == 0 else "clear","rainfall":18 if day % 2 == 0 else 0}
w=create(2,4,4)
result=[]
for kind,within in [("rain",1),("rain",2),("clear",1)]:
    r=weather.next_weather(w,kind,within)
    result.append(None if r is None else r["day"])
