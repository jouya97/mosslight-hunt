# Editable experiment ensembles

An ensemble compares each care treatment with an untreated control over 1–64
saved source gardens. The source labels are stable replicate identities. Each
trial supports the same 1–120 day horizon and at most 100 events as a campaign;
an ensemble has 1–8 treatments. A plan is shared across treatments and gardens.
Editing one plan recomputes the affected trials while retaining other completed
work. This is useful when comparing watering schedules over a collection of
gardens, including gardens from different starting days or with different sizes.

Use `python3 -B -m mosslight.ensembles workspace.sqlite create ensemble.json`.
`examples/ensemble.json` is a complete runnable example with two saved gardens.
The returned identifier is used by `work`, `status`, `inputs`, `edit`, `report`
and `replay`. `work --steps 20` bounds a worker invocation; repeat it to finish.
Each process opens its own store. An interrupted worker can be replaced by
another invocation without reclaiming a lease. `work --no-cache` performs all
pending simulations afresh. The cache is optional and has no correctness role.

The input JSON has this shape; replace the source placeholders with full saves:

```json
{
  "sources": {"north bed": {}, "south bed": {}},
  "days": 14,
  "every": 3,
  "plans": {
    "observe": {"events": []},
    "water": {"events": [{"offset": 0,
      "command": {"op": "tend", "args": {"x": 0, "y": 0, "action": "water"}}}]}
  },
  "routes": {
    "dry gardens": {"plan": "observe",
      "when": {"metric": "moisture", "below": 45, "plan": "water"}}
  },
  "treatments": [{"name": "Targeted watering", "route": "dry gardens"}],
  "version": "classic-1"
}
```

A route selects its conditional plan if the source garden's initial census is
below the stated threshold, otherwise its primary plan. Conditions support
coverage, richness, diversity, vitality, moisture, nutrients and shade. Only
the selected plan is executed. Condition evaluation precedes all treatment
events. Events at an offset execute in authored order before that day's step;
offset zero executes before the initial sample. Samples include offset zero,
each multiple of `every`, and the terminal offset. A failed command produces a
named failed trial and no partial samples. Other trials continue.

`inputs` returns editable keys such as `plan:water`, `source:north bed` and
`route:dry gardens`. To replace inputs, save a JSON object mapping these keys to
their new values and run `edit ID changes.json --expected-revision 0`. Each edit
batch creates one immutable revision, or keeps the revision if every value is
unchanged. The optional expected revision prevents overwriting concurrent
authoring. Existing input names, source membership, treatment membership,
simulation release and horizon are fixed for a workspace; create another
ensemble to change those. Source garden files are never modified.

Every report identifies one immutable input revision and its complete digest.
`report ID --revision 0` returns exactly the previously published report, even
after edits, process restarts or cache reuse. A revision superseded before all
trials finish has no published report; `replay ID --revision 0` still recomputes
its retained inputs. The current report is unavailable while any trial is
pending. A failed trial is a terminal, inspectable outcome and does not block
the report. Reports include full numerical outcomes, selected plans, actual
input reads, runtime identity and content-cache origin. Cache origin records
where the shared computation was first published; it never replaces the
requested replicate or treatment identity. Identical saves with different
source labels remain separate cohort members.

Comparison curves match treatment and control by the same replicate label.
They use elapsed offsets, so a day-30 source can be compared with a day-90 source.
Only complete pairs contribute to that treatment's means; excluded replicate
labels are explicit. Each mean is the arithmetic mean of the per-garden
treatment-minus-control differences. Missing pairs never cause a different
garden's control to be substituted. No confidence interval or claim of
statistical independence is inferred from this descriptive average.

Computation can continue while editing. A worker reads a complete immutable
snapshot, discovers the source, route and selected plan it actually used, and
publishes only if those inputs still match the current head. Unrelated edits
can reuse the work. An edit to a newly selected plan must reject older work
even when the previously published dependency list did not mention that plan.
Output, actual reads, cache insertion and a completed report commit in one
SQLite transaction. Concurrent duplicate work is allowed; at most one result
for the same dirty generation is accepted. Errors during publication leave the
node pending and safely retryable. Local SQLite storage is required.

Full replay, a coarse lock and revision-wide retries are valid implementation
strategies. This feature has no promised latency or throughput threshold.
Selective reuse is an optimization that should preserve the same results.
