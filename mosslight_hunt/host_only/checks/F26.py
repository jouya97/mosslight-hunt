from mosslight.engine import create
from mosslight.exchange import export_csv,import_csv
w=create(8,4,4); before=w.revision; import_csv(w,export_csv(w))
assert w.revision==before+1
