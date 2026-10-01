# Staged experiment studies

A study screens treatments across saved gardens over several horizons. For
example, compare six treatments for seven days, continue three to fourteen days,
then continue one to twenty-eight days. Untreated controls continue alongside
the selected gardens. This helps focus longer runs on promising care plans.

Early performance need not predict the eventual outcome. Study rankings describe
the supplied gardens and selected metric; they are not significance tests. Every
stage exposes its results and selection for review.

## Start and inspect a study

```sh
python3 -B -m mosslight.studies workspace.sqlite create examples/study.json
python3 -B -m mosslight.studies workspace.sqlite work STUDY_ID --steps 50 --offsets 2
python3 -B -m mosslight.studies workspace.sqlite status STUDY_ID
python3 -B -m mosslight.studies workspace.sqlite report STUDY_ID --stage 0
```

Creation JSON contains `sources` (labels mapped to full garden saves),
`treatments` (named event schedules), and `stages`, for example
`[{"until": 7, "keep": 3}, {"until": 14, "keep": 1}]`. Optional fields are
`every` for sampling, `metric` for selection, and `version` for the simulation
release. Studies accept 1–64 sources and 1–8 treatments. Horizons increase up to
120 days; each positive keep count cannot exceed the preceding stage's count.

Schedules use absolute experiment offsets and ordinary experiment event timing.
Every stage endpoint is sampled. `work` bounds one invocation by work units and
offsets per unit. Repeat it to continue, or use multiple worker processes with
separate connections to the same local SQLite database. Saved progress remains
available after restart.

## Read a stage decision

Scores describe average improvement over each garden's own untreated control.
All active treatments are compared on the same eligible gardens, where both the
control and all candidates succeeded. Higher scores rank first, with original
treatment order breaking exact ties. Supported metrics are coverage, richness,
diversity, vitality, moisture, nutrients and shade. Choose the metric appropriate
to the question being studied.

`preview` can show a provisional ranking with `terminal` and pending information.
Selection becomes final only when all stage trials have finished or failed.
Worker completion order must not determine which treatment advances. If no
garden remains eligible, the study records a failed decision and stops. Trial
failures remain inspectable alongside other results.

Later stages continue the promoted treatments and eligible gardens with their
controls. They extend the same experiments, preserving earlier care and results.
Reports identify the selected gardens, scores, exclusions, care plans and
continuation checkpoints so the progression can be reviewed.

## Adjust future care

```sh
python3 -B -m mosslight.studies workspace.sqlite edit STUDY_ID changes.json --expected-revision 0
```

The changes file maps treatment names to replacement event lists. Changes can
adjust care beyond the current stage's horizon; care through that horizon must
stay identical, including event order. An accepted edit applies to future stages.
A stage already under way keeps the plan it started with. The expected revision
protects an edit against intervening changes; refresh status if it is rejected.
Create another study to change past care or source membership.

Published reports remain fixed after later edits and work. In Python,
`checkpoint` identifies a completed trial by study, stage, source and treatment.
Returned data and supplied sources can be edited independently of stored work.
Interrupted or concurrent workers must preserve completed progress and coherent
stage decisions. Studies can share a local SQLite file with other workspaces.
