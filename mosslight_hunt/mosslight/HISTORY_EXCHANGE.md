# Offline exchange of authored garden histories

History exchange shares work from [garden histories](HISTORY.md) between
disconnected installations. A parcel is a local JSON file carrying the selected
work and its ancestry. It can be received on a fresh installation without a
network service or a separate copy of the original garden.

A channel names a shared line of work. A publication records a contribution and
which earlier contributions it includes. Author names are labels; each
contribution retains its own identity even when two people reach equal gardens.

## Share a line of work

```sh
python -m mosslight.history_exchange desk.sqlite announce HISTORY_BRANCH --author desk --name pond
python -m mosslight.history_exchange desk.sqlite export CHANNEL pond-parcel.json
python -m mosslight.history_exchange field.sqlite receive pond-parcel.json
python -m mosslight.history_exchange field.sqlite checkout PUBLICATION --label field-work
```

Use the returned local branch with the ordinary history commands. After making
changes, publish and send a new parcel:

```sh
python -m mosslight.history_exchange field.sqlite publish HISTORY_BRANCH --checkout CHECKOUT_BRANCH --author field
python -m mosslight.history_exchange field.sqlite export CHANNEL field-parcel.json
python -m mosslight.history_exchange desk.sqlite receive field-parcel.json
python -m mosslight.history_exchange desk.sqlite heads CHANNEL
```

A checkout tracks the starting publication and subsequent publications from
that line of work. Use separate checkouts for parallel work. Receiving a parcel
makes its publications available without replacing any local editable branch.
Object identities survive the trip; local branch names need not match.

## Delivery and reconciliation

Parcels may be delayed, repeated or delivered in different orders. Already
received work stays received, and an older parcel does not undo newer work.
`heads` lists the latest received contributions that still need to be considered.
Concurrent contributions remain available until reconciled or explicitly resolved.

```sh
python -m mosslight.history_exchange desk.sqlite reconcile LEFT_PUBLICATION RIGHT_PUBLICATION --author desk
```

Reconciliation combines compatible authored changes using their shared history.
If one contribution already includes the other, the newer contribution suffices.
Incompatible changes produce a structured conflict for review. Repeated rounds
of independent collaboration must retain later edits and reversions, including
when both collaborators previously combined the same work.

When the history does not support an unambiguous automatic result, review the
heads and publish a chosen history explicitly:

```sh
python -m mosslight.history_exchange desk.sqlite resolve CHANNEL HISTORY_BRANCH --author desk
```

A resolution records the heads it resolves. If those heads change before the
resolution is accepted, review the new work before trying again.

## Integrity and Python API

Invalid or incomplete parcels are rejected without partially importing work.
The checksum detects accidental changes; it does not authenticate the sender.
Received histories require their recorded interpreter release. Independently
imported raw garden saves do not acquire a shared history merely by matching.

`HistoryExchange(path)` provides `announce`, `checkout`, `publish`, `export`,
`receive`, `heads`, `reconcile`, `resolve` and `close`. Its `history` property is a
`HistoryStore` on the same connection. Checkout and reconciliation results include
a local branch. Errors use `HistoryConflict.details`, and method inputs and
returned data can be edited independently of the stored work.

Keep parcels as authored garden records. Exchange is local and offline, with no
sender account or device registry required.
