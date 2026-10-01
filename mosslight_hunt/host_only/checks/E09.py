from mosslight.engine import create
from mosslight.habitat import water_balance
w=create(12,4,4); i=0; w.workbench["tiles"][i]["structure"]="rain_barrel"
assert water_balance(w,i,50,50,0,3) == 47
