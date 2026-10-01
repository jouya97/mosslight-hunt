# Reconcile raw garden saves

Use this workflow when two devices edit copies of a saved garden without using
the event-history workspace. Keep the original common save, then supply both
descendants and distinct replica labels. Version 1 saves migrate to the current
schema before comparison. Inputs remain untouched.

```sh
python3 -B -m mosslight.save_merge original.json desk.json field.json merged.json \
  --left-origin desk --right-origin field
```

The output is a reviewable JSON package. A `ready` package contains `world`, which
is an ordinary version 2 save, and a receipt with input hashes, entity allocation
mapping and result hash. Save the `world` object separately to open it in the
studio. `verify_receipt` independently recomputes a package from the originals.

## Identity and ancestry

The original must actually be the shared ancestor. A common seed and matching
dimensions alone cannot prove ancestry. Replica labels are explicit provenance
provided by the user; the tool never infers common authorship from matching text.
A label stays attached to its descendant when inputs are swapped.

Identifiers present in the ancestor retain their identity. Newly allocated
numbers belong to a replica. Two devices can independently allocate note 7,
including notes with identical text; both survive. New objects receive unique
numbers after the highest input allocation counter, in replica-label then
original numeric order. Inherited objects keep their original numbers. Receipts
map these logical identities to output numbers. A descendant must follow normal
Mosslight allocation rules: deleted identifiers are never recycled, and an
existing note cannot silently become a task with the same number.

## Conflict rules

Unchanged fields accept the other side's change. Equal changes to an inherited
object coalesce. Different fields of one inherited notebook/planning record
merge. Arrays such as tags and tile selections are atomic values. Deleting a
record that the other side edited requires a choice; the tool retains all three
values in a `conflict` package. Two new records never coalesce merely because
their values match.

Ecology is one coupled snapshot: day, weather, cells, habitat settings, supplies,
nursery, journal and survey history. Different ecological changes require an
explicit choice of a complete snapshot. This avoids creating a garden that mixes
a pond from one simulation with a living fern from another. Notebook and care
records can merge alongside the selected snapshot.

Conflict paths are JSON pointers. A resolutions file maps each current conflict
path to `{"choose":"left"}`, `{"choose":"right"}` or `{"choose":"base"}`.
Pass it with `--resolutions choices.json`. A stale or misspelled resolution is
rejected. An unresolved merge never contains a usable output world.

The complete result must also satisfy save invariants. Incompatible independent
bed names, or notes dated after a selected ecological snapshot, produce an
`incompatible` result with the validation reason. Resolve the underlying input
edit and run again. No partial garden is published.

Receipts establish reproducibility from supplied inputs, not external identity
verification. Keep the common ancestor and both originals with the package.
