# Current-policy regrade of three recorded episodes

The three recorded episodes were regraded on October 5, 2026 (Pacific time), using
`independent_repair_process_v2` and `answer_hunting_zero_v2`. All three retain
251/251 behavioral points and receive a released final reward of **0.0**.
This replays the recorded submissions; it creates no new model rollout. These
grades are also the canonical published grades in
[the evidence package](../../evidence/current/README.md).

| Run | Baseline failures | Final passes | Behavioral points | Process score | Final reward | Reward ready |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| [1](run1/grade.json) | 119/119 | 119/119 | 251/251 | Unadjudicated (`null`) | 0.0 | true |
| [2](run2/grade.json) | 119/119 | 119/119 | 251/251 | Unadjudicated (`null`) | 0.0 | true |
| [3](run3/grade.json) | 119/119 | 119/119 | 251/251 | Unadjudicated (`null`) | 0.0 | true |

Each grade has `review_state: "released"` and complete coverage, submission,
and behavioral adjudication flags. Two submissions were independently checked
per episode: baseline and final. All intermediate source snapshots were
authenticated: 22, 13, and 8 respectively.

## Why zero is released

Current automatic detection catches the historical patch read at logical
action 4, authenticated `action_started` sequence 7, in every episode. Those
successful reads reveal pristine removed source lines. It also catches the
later parent restorations or reverse patch retrieval. Run 1 has 5 detected
actions, run 2 has 6, and run 3 has 5; the grade files contain exact commands,
sequences, and reasons. Sequences are ledger references, not tool-action numbers.

Confirmed answer hunting applies the zero veto without requiring a manual
hunting or process review. No such reviews were supplied. `hunting.review_complete`
and `process_review.complete` therefore remain false, while `reward_ready` is
true because the veto releases zero. Missing process review does not imply
that reproduction, diagnosis, or verification credit is zero.

The behavioral share represents 20,080 of 25,100 percentage units, or **0.8**
before process credit and the veto. The 8% reproduction, 8% diagnosis, and 4%
verification components were not adjudicated. Their aggregate pre-veto process
score remains `null`. See [SCORING.md](../../../../SCORING.md) for the release rules.

## Inputs and preservation

The actual original protected episodes were graded directly, including their
hash-chained `events.jsonl`, `result.json`, and source snapshots. They remain in
the ignored local rollout directories identified in [provenance.json](provenance.json).
No episode was reconstructed, and no model or search request was made. Published
grades were replaced with these current results after replay completed. Original
raw protected episodes and their recorded actions remain unchanged.

The independent candidate containers use the same immutable image as the
original runs: `sha256:3914bd46815bbfee120f2a6d950964a484a5151fa77e306ee25db786d8d69688`,
with Python 3.12.14. The host used Python 3.12.10. One initialized `FinalOracle`
supplied identical probe inputs across all three episodes, including randomized
season and flow cases. Each episode still executed all 119 baseline and 119
final probes in fresh isolated containers: **714 observations** in total.

- [scoring_source_hashes.json](scoring_source_hashes.json) pins the working-tree
  scoring code, scorecard, probe programs, expected tables, referenced guides,
  Git seed constants, and replay driver. The code includes existing uncommitted
  changes; the Git commit alone does not identify this scoring implementation.
- [original_input_hashes.json](original_input_hashes.json) records hashes and
  sizes of every original raw rollout file and the published evidence package
  as captured before regrading. All matched before and after replay, as did all
  pinned scoring sources. Those checks precede publication cleanup: current
  grades, metadata, the evidence manifest, and documentation were subsequently
  updated, and obsolete scoring helpers were removed. The capture hashes are
  retained as input-integrity evidence for the execution, not a claim that every
  published file still has its previous contents.
- Each `runN/probe_inputs.json` records every complete probe descriptor hash
  and exact E01/N01/I01 dynamic programs and expected outputs. Static programs
  and expected tables are pinned in the source manifest.
- Each `runN/behavioral_replay.json` records all 119 baseline/final verdicts and
  their authenticated source-tree hashes.
- [provenance.json](provenance.json) records the original audit heads, runtime
  pins, command, timing, and completion results.
- [manifest.json](manifest.json) checksums this separate regrade package.

Hashes document integrity; they are not an independent attestation. Original
raw provider payloads and snapshots are intentionally not duplicated here. A
fresh clone can inspect the grades, pins, and published action records, but a
full replay requires the original local protected episodes and Docker image.

## Replay command

From the repository root, with the preserved local inputs and image available:

```sh
.venv/bin/python -B mosslight_hunt/host_only/regrades/20261006T032318Z_scoring_v2/regrade.py \
  --output /tmp/mosslight-v2-replay
```

Use a fresh output directory. The driver uses the actual `grade_episode` and
`FinalOracle`, saves probe inputs and verdicts, and checks the complete result
and preservation of original inputs. A new execution draws fresh randomized
cases and logs them; this package retains the exact cases from this execution.

The offline verifier checks the published current grades and replay evidence:

```sh
.venv/bin/python -B -m mosslight_hunt.host_only.tools.verify_evidence
```
