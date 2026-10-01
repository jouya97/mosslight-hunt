# Durable, reproducible experiment campaigns

Run an experiment a few days at a time, leave the application, and resume later.
Independent workers make progress on separate treatments in one local SQLite
database. The source garden is retained and never edited. Results have the same
shape as ordinary experiments, and classic campaigns follow the same ecology.

```sh
python3 -B -m mosslight.campaigns trials.sqlite create examples/first-garden.json examples/treatments.json --days 12 --every 3 --version classic-1
# Replace CAMPAIGN_ID below with the printed identifier.
python3 -B -m mosslight.campaigns trials.sqlite work CAMPAIGN_ID --steps 5
python3 -B -m mosslight.campaigns trials.sqlite status CAMPAIGN_ID
python3 -B -m mosslight.campaigns trials.sqlite work CAMPAIGN_ID --steps 100
python3 -B -m mosslight.campaigns trials.sqlite report CAMPAIGN_ID
python3 -B -m mosslight.campaigns trials.sqlite replay CAMPAIGN_ID
```

## Retained releases

Both simulation releases remain available:

- `classic-1`: the original Mosslight ecology. Rain barrels deliver six moisture
  on rainy days.
- `conservation-2`: rain-barrel delivery is limited to the prior-day moisture
  deficit to 70, with a maximum delivery of six. The rainfall and other ecology
  remain the same. This supports comparisons of conservative watering policy.

Every stored campaign records its explicit release, save schema and ecological
kernel fingerprint. Resuming or replaying uses that release even when the
preferred release for new work changes. The releases share a stable ecological
kernel and retain their separate policies. Ordinary garden commands use classic
rules. Unsupported or changed kernel code causes further historical execution to
fail clearly; it cannot silently substitute a different implementation.

The fingerprint is deliberately conservative: adding another release or changing
shared runtime code also changes the installation fingerprint. Campaigns created
under that earlier installation keep readable archived reports, but executing or
replaying them requires restoring that recorded installation. Retaining two
release policies here does not promise arbitrary cross-installation upgrades.

An identical source save, ordered treatment definition, duration, sampling
interval, release and lineage identifies the same campaign. Repeating creation
returns its existing progress. Failed and cancelled campaigns are terminal;
revised treatment inputs create a different campaign.

## Checkpoints, continuation and provenance

Every successful offset commits a complete world, accumulated samples and the
next event offset. Offset zero applies its interventions before the initial
sample; a later offset applies interventions before that day's ecology. A
checkpoint includes all interventions at its offset.

```sh
python3 -B -m mosslight.campaigns trials.sqlite fork CAMPAIGN_ID --branch 1 --offset 6 --days 6 --version conservation-2
python3 -B -m mosslight.campaigns trials.sqlite provenance CHILD_CAMPAIGN_ID
python3 -B -m mosslight.campaigns trials.sqlite compact CAMPAIGN_ID --every 5
```

Branches are numbered in display order, starting with control as zero. A fork
uses the selected checkpoint's complete garden as its new source. By default it
inherits the parent's release; an explicit version starts a comparison under new
rules. Its continuation treatment inherits only events strictly after the chosen
checkpoint, translated into child-relative offsets. Already-applied checkpoint
events are never applied twice. The new control starts from the same historical
garden without the inherited future interventions. The parent is unchanged.

The Python `fork` method also accepts an explicit replacement treatment list and
sample interval. Each child records the exact parent campaign, branch, offset
and checkpoint digest. `provenance` resolves the immutable chain back to a source
garden. Compaction keeps initial, final and periodic checkpoints, plus every
checkpoint referenced by a descendant. Fork creation and compaction coordinate
through a transaction so a published descendant cannot lose its source anchor.
Compacted unreferenced offsets cannot be selected for a future fork; replay can
still reproduce the original final result from retained campaign inputs.

Completing all branches archives an immutable report containing results, release
identity, source digest, parent lineage and result digest. Reading that report
never recalculates historical measurements using a changed installation.
`result` returns only the ordinary experiment result; `report` adds provenance.
`replay` independently reruns the retained source and events using the recorded
release and returns a new result without changing the published report.

## Worker and storage behavior

Workers compute outside short database transactions. Publishing branch progress,
its immutable checkpoint, and a terminal report uses one transaction. A failed
checkpoint or report write leaves the prior branch progress intact. A failed
intervention leaves its preceding checkpoint intact and marks the branch failed
with an error; the complete offset is the unit of recovery.

If a worker disappears, its claim becomes eligible for reclamation after 30
seconds. A replacement gets a new generation. The old worker cannot publish
once a replacement owns that branch, or after cancellation. Lease expiry alone
permits reclamation but does not revoke an unreplaced worker. Poll `work` again
to reclaim abandoned work. There is no background daemon and `work` does not
wait for branches owned by another worker.

Use `cancel CAMPAIGN_ID` to stop outstanding branches. Work already completed is
retained; cancellation of unfinished branches prevents a complete final report.
Identical creation returns that cancelled campaign rather than restarting it.

Workers may share a database only on one machine with a local filesystem. This
does not authorize concurrent writes to normal garden JSON saves. Database
backups must use a SQLite-aware backup operation or be taken while all workers
are closed, including WAL sidecars when applicable.
