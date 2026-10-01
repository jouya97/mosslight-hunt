from mosslight.weather import calendar_day
assert calendar_day(11)["season_day"]==12 and calendar_day(12)["season_day"]==1
