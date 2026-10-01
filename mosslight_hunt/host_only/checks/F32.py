from mosslight.engine import create
w=create(14,4,4); h=w.workbench["history"]; h.extend([{"day":2,"moisture":50,"nutrients":50,"vitality":50,"occupied":1,"births":0,"losses":0},{"day":3,"moisture":50,"nutrients":50,"vitality":50,"occupied":1,"births":0,"losses":0},{"day":10,"moisture":50,"nutrients":50,"vitality":50,"occupied":1,"births":0,"losses":0}])
from mosslight.charts import render_history
s=render_history(w,"moisture")
assert ">Day 2</text>" in s and ">Day 10</text>" in s and 'cx="142.50"' in s
