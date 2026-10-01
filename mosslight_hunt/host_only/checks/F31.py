from mosslight.engine import create
from mosslight.charts import render_map
w=create(13,4,4)
for c in w.cells: c.shade=40
w.workbench["tiles"][5]["structure"]="shade_cloth"
s=render_map(w,"shade")
assert ">55</text>" in s
