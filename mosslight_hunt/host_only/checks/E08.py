from mosslight.engine import create
from mosslight.habitat import effective_shade
w=create(11,4,4); i=w.index(1,1); w.cells[i].shade=40
w.workbench["tiles"][w.index(1,2)]["structure"]="shade_cloth"
assert effective_shade(w,i) == 55
