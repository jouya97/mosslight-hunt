from mosslight.engine import create
from mosslight.notebook import add_note, search_notes
w = create(11, 4, 4)
add_note(w, 'today')
result = len(search_notes(w,start=0,end=0))
