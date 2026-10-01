# Staged experiment studies

A study screens care treatments across saved source gardens over several time
horizons. For example, run six treatments for seven days, continue three for
fourteen days, then continue one for twenty-eight days. The untreated control
continues alongside every surviving source garden. This avoids spending the
entire long horizon on treatments the gardener has chosen to screen out.

This is a descriptive screening rule, not an inferential significance test or
a guarantee of finding the treatment with the best eventual outcome. Early
performance need not predict later performance. Every stage exposes its complete
results and decision so the gardener can inspect that tradeoff.

Run `python3 -B -m mosslight.studies workspace.sqlite create examples/study.json`.
Use the returned study ID with `work`, `status`, `preview`, `report` and `edit`.
`work --steps 50 --offsets 2` performs at most fifty work units, each advancing
one trial by at most two experiment offsets. Multiple processes can run workers
against one local SQLite database. A process opens its own store connection.
Reports and checkpoints remain readable after process restart.

The creation JSON contains `sources` (labels mapped to full garden saves),
`treatments` (the ordinary list of named event schedules), and `stages`, e.g.
`[{"until": 7, "keep": 3}, {"until": 14, "keep": 1}]`. It also accepts `every`
for sampling, `metric` for selection, and `version` for retained engine semantics.
There must be 1–64 sources, 1–8 treatments and increasing stage horizons within
120 days. Each stage's keep count is positive and cannot exceed the number kept
by the previous stage. Events use absolute experiment offsets; offset zero runs
before the initial sample and later offsets run before their daily step. Events
at a shared offset run in authored order. All stage endpoints are sampled,
including endpoints that are not multiples of `every`.

At a stage's end, a source is eligible for comparison only if its control and
**every active treatment** succeeded. This common cohort is the same for all
candidate scores. Failed or incomplete source pairs are never substituted with
another source, nor is a treatment ranked on an easier private subset. Each
score is the mean, over that common cohort, of the final treatment metric minus
the same source's final control metric. Higher scores rank first; exact ties
preserve the original treatment order. Supported metrics are coverage, richness,
diversity, vitality, moisture, nutrients and shade. The gardener chooses which
metric to maximize; the software does not assume every one measures health.

**Final promotion waits until every trial in the stage has succeeded or failed.**
`preview` may show a provisional ranking once complete source pairs exist. Its
`terminal` flag and pending count distinguish that preview from a committed
decision. Slow workers may change the eligible cohort and reverse the ranking;
the arrival order of results must not change the final decision. If the terminal
stage has no common source, it records an explicit failed decision and the study
stops. A failed trial does not erase another trial's results.

The next stage contains only the promoted treatments and the preceding stage's
common sources, plus those sources' controls. Each trial resumes from its own
completed checkpoint, identified by study, stage, source and treatment and a
digest of the entire state. A treatment continues its earlier interventions,
random state, notebook and samples. A control checkpoint is only the continuation
of that source's control. Commands at a stage boundary have already executed and
are not repeated. Reports include the checkpoint parent for each continuation,
the frozen plans, eligible cohort, scores, promotion and excluded sources.

Workers claim a trial with a time-limited lease. Each replacement claim changes
the generation. A delayed or crashed worker can never overwrite its replacement.
The last persisted world, next offset and samples are a single checkpoint.
Publication commits that checkpoint, any completed stage report, and the next
stage's complete job set in one transaction. A crash before commit leaves the
previous checkpoint intact; a crash after commit can safely resume from it.
Computation takes place outside the write transaction, so a gardener can inspect
progress and edit future care while a worker is computing.

Each stage freezes a care-plan revision when it is dispatched. To adjust future
care, supply `edit ID changes.json --expected-revision N`, where the changes JSON
maps treatment names to replacement event lists. Events at or before the current
stage's horizon must be identical, including their order. Later events can be
added, changed or removed. An edit commits as one new plan revision and affects
stages dispatched after that edit. A concurrent stage transition may reject an
edit that is no longer in the future; reload status and choose an applicable
change. The current stage and its worker inputs never change midway through
execution. To alter completed care or source membership, create another study.

`report ID --stage 0` returns the exact saved first-stage envelope after all later
edits and work. Reports are never replaced by live previews. `checkpoint` in the
Python API resolves an immutable completed trial by its full identity. All source
save data are copied; source files and caller-owned World instances are untouched.
Studies use `study_*` database tables and can share a local SQLite file with
campaigns, histories and ordinary ensembles.

No speed threshold, worker-count requirement, or cache algorithm is imposed.
Serial execution and replay from retained source inputs are legitimate
implementations when they preserve complete-cohort decisions, future-plan
boundaries, historical reports and full checkpoint identity. The bounded worker
API and visible pending state make slow or interrupted studies understandable.
