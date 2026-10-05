from mosslight.engine import create
from mosslight.charts import render_map
w = create(13, 4, 4)
for c in w.cells:
    c.shade = 40
w.workbench['tiles'][5]['structure'] = 'shade_cloth'
s = render_map(w, 'shade')
import xml.etree.ElementTree as ET
root=ET.fromstring(s)
result=[next(n.text for n in group if n.tag.endswith("text")) for group in root if group.tag.endswith("g") and group.get("class")=="tile"]
result = [result[i] for i in (0,4,5,6,9,15)]
