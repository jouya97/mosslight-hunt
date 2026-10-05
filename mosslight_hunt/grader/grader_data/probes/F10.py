from mosslight.engine import create
from mosslight.notebook import add_note, search_notes
w = create(10, 4, 4)
add_note(w, 'field note', ['fern'])
result = [len(search_notes(w,tag=t,start=0,end=1)) for t in ("fer","fern","FERN","ferns")]
