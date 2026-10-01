# Field courier

An observation packet carries a notebook between a desktop and a field laptop
without a server. It provides a separate notebook workflow for sharing and
reconciling observations.

```sh
python -m mosslight.courier export garden.json --peer desk --notebook pond --output desk.json
python -m mosslight.courier merge desk.json field.json --output joined.json
python -m mosslight.courier inspect joined.json
```

A writer name identifies an export or editing device. A notebook name identifies
the source garden. Copies of one garden can share `--notebook pond`; independently
created gardens should use different notebook names. Each fresh export needs an
unused writer name. To continue editing a device's work, retain its packet and
use `put` or `remove`.

When `--notebook` is omitted, the writer name becomes the notebook name, so the
export keeps its observations in a separate namespace. To join exports across
writers, give known copies of the same garden the same `--notebook` name.
Existing version 1 and version 2 saves are accepted unchanged.

## Edit and combine observations

The Python function `from_garden(world, peer, notebook=None)` follows the same
naming rules. For example:

```python
from mosslight.courier import from_garden, put

packet = from_garden(world, peer="field", notebook="pond")
put(packet, "pond-note", {"text": "Fern unfurled", "tags": ["fern"]})
```

`put` updates the supplied fields and `remove` deletes an observation. A later
edit replaces values the writer has already seen. Concurrent different values
remain available through `observations` for the gardener to review. Text retains
its exact spelling and case. To resolve a disagreement, merge the packets and
write the desired value. A simultaneous edit and deletion keeps the observation
visible until a gardener reviews it.

Repeated delivery is harmless, and merging must preserve the same notebook
meaning across delivery orders. Old packets cannot bring back work already
superseded by newer observations. A merged packet keeps the left writer and can
be used to continue that writer's work. Conflicting reuse of a writer's event
identity is rejected.

## Share a selection or keep a compact packet

`project(packet, ["pond-note"])` shares selected observations. Merging a selection
into a complete notebook preserves the observations it did not include. Sharing
one observation does not imply that the recipient has seen another observation's
edits or deletions.

`checkpoint(packet)` produces a compact packet suitable for continued editing
and exchange. Compacting or selecting work preserves its meaning when it later
meets older or partial copies. `record_clock(packet, record)` reports coverage
for an individual observation. `acknowledged(acks, peers)` reports progress seen
by every named active device; a missing acknowledgement supplies no progress.

`merge`, `checkpoint` and `project` return independent packets. Supplied field
values remain owned by the caller. Packets are local JSON documents and make no
network requests.

## Paper recovery slips

`receipt(note)` produces an ASCII recovery slip; `recover(slip)` restores the
exact original Unicode note. Notes may contain 1–2,000 characters. Keep the whole
slip: recovery works offline on a fresh installation using the slip alone.
Damaged slips produce a clear error.
