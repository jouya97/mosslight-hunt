from mosslight.engine import create
from mosslight.weather import almanac
w=create(1,4,4); r=almanac(w,days=20)
manual=best=0
for e in r["days"]:
 manual=manual+1 if e["weather"]=="clear" else 0; best=max(best,manual)
assert r["longest_dry_spell"]==best
