from mosslight.engine import create
import mosslight.weather as weather
rainfall=[0,0,8,0,0,0,18,0,8,8]
names={0:"clear",8:"drizzle",18:"rain"}
weather.weather_on=lambda seed,day: {"day":day,"weather":names[rainfall[day]],"rainfall":rainfall[day]}
w=create(1,4,4)
r=weather.almanac(w,days=len(rainfall),start=0)
result=[r["longest_dry_spell"],r["total_rainfall"],r["weather_days"]]
