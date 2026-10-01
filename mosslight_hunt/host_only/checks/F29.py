from mosslight.engine import create
from mosslight.notebook import add_task
from mosslight.exchange import export_markdown
w=create(11,4,4); add_task(w,"later",9); add_task(w,"soon",2)
s=export_markdown(w); assert s.index("Day 2: soon")<s.index("Day 9: later")
