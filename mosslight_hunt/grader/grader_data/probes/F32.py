from mosslight.engine import create
w = create(14, 4, 4)
h = w.workbench['history']
h.extend([{'day': 2, 'moisture': 50, 'nutrients': 50, 'vitality': 50, 'occupied': 1, 'births': 0, 'losses': 0}, {'day': 3, 'moisture': 50, 'nutrients': 50, 'vitality': 50, 'occupied': 1, 'births': 0, 'losses': 0}, {'day': 10, 'moisture': 50, 'nutrients': 50, 'vitality': 50, 'occupied': 1, 'births': 0, 'losses': 0}])
from mosslight.charts import render_history
s = render_history(w, 'moisture')
import xml.etree.ElementTree as ET
root=ET.fromstring(s)
result={"x":[n.get("cx") for n in root if n.tag.endswith("circle")],"days":[n.text for n in root if n.tag.endswith("text") and (n.text or "").startswith("Day ")]}
