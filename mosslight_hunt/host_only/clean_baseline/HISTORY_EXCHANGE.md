# Offline exchange of authored garden histories

History exchange carries a recorded garden history between disconnected
installations. A parcel is one local JSON file containing complete immutable
publication ancestry, the referenced history revisions, and their original
garden. It makes no network requests. It works with event-ledger histories from
`mosslight.history`; it does not infer identity from independently imported raw
garden saves.

A channel identifies one shared line of work. A publication identifies a
particular authored history together with the publications its author observed.
Two equal gardens or equal history revisions can still be different
publications: two people may independently reconcile the same changes before
sharing their work again. Those separate causal histories are retained.

## Local workflow

```sh
python -m mosslight.history_exchange desk.sqlite announce HISTORY_BRANCH --author desk --name pond
python -m mosslight.history_exchange desk.sqlite export CHANNEL pond-parcel.json
python -m mosslight.history_exchange field.sqlite receive pond-parcel.json
python -m mosslight.history_exchange field.sqlite checkout PUBLICATION --label field-work
# Append or correct the returned local branch using mosslight.history.
python -m mosslight.history_exchange field.sqlite publish HISTORY_BRANCH --checkout CHECKOUT_BRANCH --author field
python -m mosslight.history_exchange field.sqlite export CHANNEL field-parcel.json
python -m mosslight.history_exchange desk.sqlite receive field-parcel.json
python -m mosslight.history_exchange desk.sqlite heads CHANNEL
```

`announce` creates a channel and its first publication from a local history
branch. `checkout` creates a local history branch and records the exact starting
publication. `publish` records work from that checkout, including a corrected
branch created from it. It advances that checkout's local publication receipt;
use separate checkouts for separate parallel lines of work. Every publication
retains its parent publication IDs. Author names label the work and do not
determine object identity or overwrite another author's sequence.

Object references remain those of the original imported root and creating
events. Local branch names are local presentation choices. Receiving a parcel
never replaces a local history branch head. It adds immutable objects to the
publication ledger; `checkout` makes selected work locally editable.

## Parcels and delayed delivery

An exported parcel contains all ancestors of its selected heads. It can be
opened on a fresh installation without requesting another file. Exporting a
selected older publication is allowed. The parcel checksum detects accidental
modification, and conflicting definitions of an existing root, revision,
channel or publication are rejected. Checksums are not sender authentication.

Receive validates the complete parcel and publishes it in one SQLite
transaction. A malformed, incomplete or semantically inconsistent parcel leaves
the database unchanged. Revision worlds are checked against the authored events
under their recorded interpreter. Receiving executable history therefore needs
that exact installed interpreter; incompatible installations get a clear error.

Duplicate parcels are harmless. Delivery order does not change the resulting
publication graph or its heads. A head is a publication with no received causal
descendant. A delayed old parcel cannot revive a publication already superseded
by a received descendant. Concurrent heads are preserved until reconciled or
explicitly resolved.

## Reconciliation

```sh
python -m mosslight.history_exchange desk.sqlite reconcile LEFT_PUBLICATION RIGHT_PUBLICATION --author desk
```

If one publication includes the other in its ancestry, reconciliation chooses
the descendant. Concurrent publications are compared using their common
ancestry. Unrelated authored edits merge automatically using the history
three-way rules; incompatible edits or ordering constraints produce a structured
conflict without publishing a new head.

Independent reconciliations can produce a crisscross ancestry graph with several
latest common ancestors. All of those common observations contribute to the
comparison. For example, one person changes note A and another changes note B;
both devices independently merge both changes. If each later reverts one of the
changes, their next reconciliation must retain both reverts. Choosing just one
older branch as the comparison base can incorrectly treat the other revert as
no change. The original common observations remain in every exported parcel.

Compatible common histories are combined into a comparison history before the
current heads are compared. If the common histories themselves cannot be
combined unambiguously, reconciliation reports `ambiguous-ancestry`. The user can
review the preserved heads and explicitly choose a resolved history:

```sh
python -m mosslight.history_exchange desk.sqlite resolve CHANNEL HISTORY_BRANCH --author desk
```

`resolve` publishes that branch as the explicit resolution of the currently
received heads. It records every resolved head as a parent and rejects a stale
resolution if the head set changes during computation. It does not claim that
the chosen content was inferred automatically.

## Python API and limits

`HistoryExchange(path)` provides `announce`, `checkout`, `publish`, `export`,
`receive`, `heads`, `reconcile`, `resolve`, and `close`. Its `history` property is a
`HistoryStore` on the same SQLite connection. Reconciliation and checkout results
include a local branch usable by the ordinary history API. Errors use
`HistoryConflict.details` where a reviewer can act on them. All methods own their
serialized inputs and return independent data.

The publication graph and its referenced revisions are retained in full. No
time-to-live deletion, sender clock heuristic, registry, connectivity requirement
or maximum-latency guarantee is imposed. Whole-ledger transfer and full replay
are valid implementation choices. Local SQLite atomicity covers process crashes;
the format does not claim to repair storage-device failure or authenticate a
malicious sender.
