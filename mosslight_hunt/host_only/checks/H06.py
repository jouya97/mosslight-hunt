import copy
from mosslight.history import _rebase_events

# Valid event envelopes from one creator and a logical edit. A correction that
# removes an unrelated earlier creation changes the observed number from 2 to 1;
# reauthoring the same logical edit updates only its original-binding annotation.
creator = {"id": "creator", "command": {"op": "note", "args": {"content": "target"}}, "bindings": {}}
edit = {"id": "edit", "command": {"op": "edit_note", "args": {
    "ident": {"$ref": "event:creator:notes"}, "content": "same authored content"}}, "bindings": {"ident": 2}}
base = [creator, edit]
local = copy.deepcopy(base)
local[1]["bindings"]["ident"] = 1
target = copy.deepcopy(local)
target[1]["command"]["args"]["content"] = "new remote content"
result = _rebase_events(base, local, target)
assert result == target
assert base[1]["bindings"]["ident"] == 2
assert local[1]["command"]["args"]["content"] == "same authored content"
