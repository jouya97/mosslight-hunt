# Durable experiment campaigns

Run an experiment a few days at a time, leave the application and resume later.
Campaigns retain progress and results in a local SQLite workspace. Several local
workers can advance separate treatments, while the source garden remains
available for other work. Results use the ordinary experiment format.

```sh
python3 -B -m mosslight.campaigns trials.sqlite create examples/first-garden.json examples/treatments.json --days 12 --every 3 --version classic-1
# Use the identifier printed by create for CAMPAIGN_ID.
python3 -B -m mosslight.campaigns trials.sqlite work CAMPAIGN_ID --steps 5
python3 -B -m mosslight.campaigns trials.sqlite status CAMPAIGN_ID
python3 -B -m mosslight.campaigns trials.sqlite work CAMPAIGN_ID --steps 100
python3 -B -m mosslight.campaigns trials.sqlite report CAMPAIGN_ID
```

## Choose an ecological release

`classic-1` uses the ordinary garden ecology. `conservation-2` changes rain-barrel
watering: rainy-day delivery is capped at six and at the previous day's moisture
deficit below 70. This makes it possible to compare a conservative watering policy
with the classic six-point rainy-day delivery.

A campaign retains its release, source, treatment definitions and installation
fingerprint. Resuming it uses those recorded inputs. Repeated creation with the
same source, ordered treatments, duration, sampling interval, release and lineage
returns the existing campaign, including its progress. Change the experiment's
inputs to begin different work.

Archived reports remain readable after an installation changes. Historical
execution and replay require a compatible recorded installation; changes to
shared runtime code or the set of releases can require restoring the earlier
installation. Unsupported historical execution fails clearly.

## Resume work and review results

`work` advances up to its requested step budget and returns without waiting for
other workers. Repeat it to continue an unfinished campaign. Interrupted work can
be resumed from durable progress without repeating care already recorded there.
Failed interventions remain visible with their errors for review.

When all branches finish, `report` provides the archived result with release and
source identity, lineage and result digest. `result` returns the ordinary
experiment result alone. Reports retain the measurements made during the run.
Use `replay CAMPAIGN_ID` to reproduce the campaign from its retained inputs without
changing its published report.

## Continue from an earlier garden

```sh
python3 -B -m mosslight.campaigns trials.sqlite fork CAMPAIGN_ID --branch 1 --offset 6 --days 6 --version conservation-2
python3 -B -m mosslight.campaigns trials.sqlite provenance CHILD_CAMPAIGN_ID
python3 -B -m mosslight.campaigns trials.sqlite compact CAMPAIGN_ID --every 5
```

Branches are numbered in display order, with control at zero. A fork starts from
the garden at the selected checkpoint and leaves its parent intact. It inherits
the parent's release unless another is selected. Future interventions continue
at dates relative to the fork; care already performed at the checkpoint remains
part of its starting garden. Its control begins from that same garden.

The Python `fork` method can supply replacement treatments and a sampling
interval. Provenance records where a continuation came from, so results can be
traced back through earlier campaigns to the original source.

Compaction reduces stored checkpoints while keeping endpoints, periodic history
and the origins of existing descendants. Only retained checkpoints can be used
for new forks. The campaign's retained inputs still support replay after
compaction.

## Operate a local workspace

Workers may share a database on one machine using a local filesystem. If one
stops responding, another `work` call can reclaim its work after 30 seconds.
There is no background worker. Concurrent workers and recovery must preserve a
single coherent history of progress and completed results.

`cancel CAMPAIGN_ID` stops outstanding work while keeping completed branches.
Cancelled or failed campaigns do not restart when the same creation request is
repeated. An unfinished cancelled campaign has no complete final report.

Use SQLite-aware backups, or close all workers before copying a database and any
WAL sidecars. Separate processes should not write the same ordinary garden JSON
file concurrently.
