from mosslight.engine import create
from mosslight.notebook import add_note,search_notes
w=create(10,4,4); add_note(w,"field note",["fern"] )
assert search_notes(w,tag="fer",start=0,end=1)==[]
