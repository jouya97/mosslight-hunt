# Garden histories and corrections

A history keeps the garden you imported and the commands you authored. Use it
to correct an old observation or care action, keep the original interpretation,
and compare an alternative. History databases are local SQLite files. The
ordinary garden file format remains version 2.

```sh
python -m mosslight.history field.sqlite create examples/first-garden.json --label field
python -m mosslight.history field.sqlite append BRANCH command.json
python -m mosslight.history field.sqlite show BRANCH
python -m mosslight.history field.sqlite correct BRANCH corrections.json --label corrected
python -m mosslight.history field.sqlite export CORRECTED_BRANCH corrected-garden.json
```

`create` prints the branch identifier. `append` accepts the ordinary command JSON
and returns its immutable event identifier, revision, full garden and references.
`--revision REVISION` rejects a command authored against an older branch head.
Computation happens before a short optimistic publication transaction. Another
writer's successful append cannot be overwritten by an older candidate.

Every revision retains the exact ordered authored events and its materialized
garden. Appending advances one branch head; earlier revisions remain available
through the Python `snapshot(branch, revision=...)` API. Fork, correction,
cherry-pick and rebase create new branches. Their original branches remain
available. A branch records the immutable revision from which it was forked.
The operation provenance records the exact input revisions and selected events,
so a later moving branch name does not erase the original request.

## Object references

Garden collection numbers are local to one replay. An earlier correction can
change the numbers assigned to later notes, tasks, specimens, beds, plans, rules
and nursery batches. A history binds an integer `ident` to the object selected
when the command was authored. The persisted command then uses a logical
reference. A created object's reference belongs to its creating event and
collection; imported objects belong to the imported root and collection.

For example, remove an unrelated earlier note from a history that subsequently
creates and edits a nursery batch. The edit still reaches that batch even if its
numeric ID changes. Replacing a creator with a command that creates another kind
of object does not transfer the original object's identity.

`references BRANCH` lists logical references, current local IDs and presence.
Python and command JSON can also pass an explicit reference:

```json
{"op":"edit_note","args":{"ident":{"$ref":"event:EVENT_ID:notes"},"content":"Revised observation"}}
```

An object's deleted reference never becomes a reference to a different object
that later receives the same numeric ID. All current commands that target a
collection object support logical references. Coordinate-based tools continue
to use coordinates.

## Corrections and conflicts

`corrections.json` maps existing event IDs to replacement ordinary commands.
Use `null` to remove an event. Multiple replacements are replayed together.
Replacement integer IDs bind in the original event's preceding state; an object
deleted later in the history can still be referenced when correcting its earlier
edit. The branch's final garden is not the authoring context for that replacement.
Explicit logical references are preferable when resolving a conflicted history.

```json
{
  "EVENT_TO_REMOVE": null,
  "EVENT_TO_REVISE": {"op":"note","args":{"content":"Corrected observation"}}
}
```

A replacement retains its authored event ID. All subsequent commands resolve
their object references again during replay. Checkpoints are only reusable when
the complete preceding history and interpreter identity match.

If a dependency was removed, replay stops at that command and returns a
`conflicted` branch with the missing reference and event ID. An invalid care
command similarly records an `invalid-command` conflict. The returned garden is
explicitly the last successful prefix; it is not a completed alternative.
Commands after the conflict remain in the history. Correct or remove the
conflicting command to continue replay. Append and complete-garden export are
unavailable until the conflict is resolved.

## Fork, select and rebase

```sh
python -m mosslight.history field.sqlite fork BRANCH --label trial
python -m mosslight.history field.sqlite pick TARGET SOURCE EVENT_ONE EVENT_TWO --label combined
python -m mosslight.history field.sqlite rebase CHILD UPDATED_PARENT --label rebased
```

Cherry-pick transfers selected authored events in source order. A shared event
already present in the target is applied once. Independently authored equal
commands remain independent actions: two separately recorded waterings both
apply. Picking the same event with conflicting content reports a conflict.
Object-using commands require their creating event to be selected or already
present. Picking a consumer alone produces a missing-reference conflict.

Rebase performs a three-way comparison between the child's recorded fork base,
the child's current history and the destination history. It preserves local
corrections and deletions while accepting unrelated destination changes. Two
different edits to one event, or an edit opposed by a deletion, report
`concurrent-edit`. Local insertions are anchored after their preceding base
event; a removed anchor reports `missing-anchor`. Destination insertions within
the same gap precede local insertions, and each side keeps its authored order.
Events that both sides acquired after the fork, for example through separate
cherry-picks, retain both sides' ordering constraints. An otherwise unconstrained
insertion follows the destination-first rule. A shared event can require another
insertion to move before it; rebase preserves that authored dependency. If one
history orders the same shared events A then B and the other orders B then A,
rebase reports `order-conflict` and creates no output branch. This matters for
noncommuting actions such as planting and clearing the same tile.

Rebase compares authored command meaning separately from audit metadata.
Original numeric bindings document what the author saw. Different numeric
bindings for the same logical reference and command are not different authored
edits and must not create a conflict with a real correction on the other side.
Rebase never silently chooses between incompatible authored changes.

Histories must share the same imported root for cherry-pick and rebase. There is
no inference that independently imported byte-identical files share an origin.

## Python API and verification

`HistoryStore(path)` provides `create`, `append`, `fork`, `correct`, `cherry_pick`,
`rebase`, `snapshot`, `references`, `verify` and `close`. Mutation methods return
an independent snapshot dictionary. Use a separate store connection per worker.
`HistoryConflict` provides structured `details` for interactive applications.
The CLI reports errors as JSON on stderr and returns exit status 2.

`verify BRANCH` recomputes its authoritative history without reading checkpoints
and compares the stored result. Stored snapshots remain readable when an
interpreter is unavailable. Replay and edits require the exact recorded
interpreter fingerprint; the integrated versioned runtime selects the saved
release. There is no automatic cross-release reinterpretation.

This implementation stores complete immutable events, references and worlds.
It makes no bounded-latency promise for arbitrary long histories, and does not
infer the intent of conflicting edits. The supplied tests exercise numeric ID
reallocation, missing producers, nursery references, repeated operations,
three-way rebases, independent writers, persistence and CLI export.
