from mosslight.weather import calendar_day
result=[calendar_day(d)["season_day"] for d in (0,11,12,23,24,35,36,47,48)]
