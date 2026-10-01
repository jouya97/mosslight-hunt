# Field courier

An observation packet carries a notebook between a desktop and a field laptop
without a server. It is a separate notebook workflow: it does not advance a
garden or silently overwrite its local notes.

```sh
python -m mosslight.courier export garden.json --peer desk --notebook pond --output desk.json
python -m mosslight.courier merge desk.json field.json --output joined.json
python -m mosslight.courier inspect joined.json
```

A writer name identifies an export or editing device. A notebook name identifies
the source garden across devices; it is separate from the writer name. For
example, two exports using `--peer desk` and `--peer field` can use the same
`--notebook pond` to join notes from copies of that garden. Give independently
created gardens different notebook names, even when their local note IDs or
contents happen to match. Each fresh export needs an unused writer name because
it creates a concurrent snapshot, not an incremental edit history. To continue
editing on a device, retain its packet and use `put` or `remove`.

Legacy garden exports require an explicit notebook name to join across writers.
When `--notebook` is omitted, the writer name becomes a separate notebook
namespace. Assign the same notebook name only when the source files are known
copies of the same garden; assign distinct names to independently created
gardens. Version 1 and version 2 save files are accepted without alteration.

The Python function `from_garden(world, peer, notebook=None)` follows the export
command's namespace rules. `put` and `remove` edit packets; `merge`, `checkpoint`,
and `project` return independent packets. Inputs and field values remain owned
by the caller. A merged packet keeps the left writer. Resuming that writer must
advance beyond every sequence already observed for it, even from an older copy.

`put(packet, "pond-note", {"text": "Fern unfurled", "tags": ["fern"]})`
updates only supplied fields. Each field is a causal register. Later edits
supersede observed values; concurrent distinct values are all returned by
`observations` in deterministic order. Text is exact and case sensitive. A
record with a concurrent deletion and edit remains visible. Deleting after
observing that edit hides it. The gardener resolves field conflicts by merging
first and then writing the desired value.

Packets store dots (writer and sequence), causal clocks and per-record omission
contexts. Duplicate identical events are harmless; reused writer sequences with
different content are rejected. Causal comparisons treat absent components as
zero. `merge` never alters either input. Checkpoints retain register heads and
context for omitted events, so old packets cannot revive obsolete values. A
checkpoint preserves each record's omission context even when it currently has
no retained events. Record contexts must remain separate: observing one record
does not establish a deletion in another record from the same device.


The packet-wide clock reserves writer sequence numbers, including numbers
learned from selections. It is not a claim that every record from those writers
was received. `record_clock(packet, record)` reports the causal coverage of one
record. Both new edit contexts and checkpoint omission contexts use that record
coverage. Receiving a selection for another record must not mark delayed edits
to this record as observed, superseded, or deleted.

Use `project(packet, ["pond-note"])` to share selected records. A selection
carries neither values nor omission context for unselected observations. Merging
it into a complete notebook preserves those observations. The same rules apply
to empty selections, repeated projections and checkpointed packets.
`acknowledged(acks, peers)` gives the componentwise frontier seen by every named
active device, with zero contributed by a missing device acknowledgement. This
reports how much field work has reached all devices.

For paper copies, `receipt(note)` produces an ASCII recovery slip and
`recover(slip)` restores the exact original Unicode note. Supported notes have
1–2,000 characters. Slips are variable length and carry the full note in the
slip itself. Recovery works on a fresh offline installation without an account,
network, local database, original garden, or additional input. Store the entire
slip as printed. Damaged slips produce a clear error.

Packets are ordinary local JSON documents containing authored notebook content.
The courier does not make network requests.
