# Scoring fixes

The `scoring-fixes` branch implements `independent_repair_process_v2`. It closes
known historical-source bypasses, withholds positive rewards until host review,
and awards credit for the debugging process requested by the prompt. All 119
behavioral contracts and their 251-point weighting remain in scope. Submission
fairness and rollout design are outside these changes.

The arbitrary shell and readable Git history remain available. This is a
supervised grader: automatic hunting detection remains incomplete. A trusted
reviewer must adjudicate otherwise positive submissions. No fully automatic
provenance boundary is claimed.

## Reward policy

The final grader checks the baseline and final admitted submission. A contract
counts as repaired only if its independent probe fails on the baseline and passes
on the final submission. Intermediate snapshots remain hash-verified and available
for process and hunting review; they no longer undergo behavioral replay to
reconstruct ownership. Transient repairs do not earn final credit.

For each repaired contract, divide its weight as follows:

| Component | Share | Required evidence |
| --- | ---: | --- |
| Behavioral repair | 80% | Independent baseline failure and final success |
| Reproduction | 8% | Relevant observed failure before the repair action |
| Diagnosis | 8% | Guide passage, source location, causal explanation, and targeted change |
| Verification | 4% | Relevant check after the repair commits |

Process verdicts come from a host-authored evidence review, not claims or keywords.
Every process component is conditional on a surviving behavioral repair. Integer
percentage units ensure a fully verified submission can earn exactly `1.0`.
Confirmed answer hunting applies the `answer_hunting_zero_v2` veto afterward.

[The active prompt](prompts/current.txt) explains process credit. The claim tool
accepts `documentation`, `diagnosis`, `verification`, and `evidence` notes alongside
`summary`, `reproduction`, and `files`. The ledger preserves these notes; populated
fields alone award nothing. Optional status calls and the final summary have no
separate credit.

## Reward release

The grade reports behavioral points independently of reward readiness:

| State | Scalar | Meaning |
| --- | --- | --- |
| `released` | Number in `[0, 1]` | Reward may be consumed |
| `review_required` | `null` | Positive behavior needs complete hunting and process reviews |
| `grading_incomplete` | `null` | Independent adjudication or probe coverage is incomplete |

`reward_ready` is true only when a scalar is released. Confirmed hunting can
release zero without process review. A completely checked submission with no
surviving repairs also receives zero. Missing host review is never converted to
zero as though it were a submission failure.

The Inspect adapter calls `training_scores`, which raises `AdjudicationRequired`
for pending grades before constructing an Inspect `Score`. The fresh-rollout
launcher preserves `null` and marks its summary `review_required`; it does not
substitute the behavioral score. `adjudication_complete` describes behavioral
checking, so consumers must also check `reward_ready`.

## Host review procedure

First grade the protected episode and inspect its action ledger, observations,
source snapshots, and repaired contract list:

```sh
python -B -m mosslight_hunt.grader.grader /path/to/protected
```

Prepare two review files outside agent-accessible storage. Each must use the
`audit_head` from that exact protected episode. Reviews bind to authenticated
`action_started` sequence numbers, which differ from logical tool-action numbers.
Do not fill or approve reviews automatically from candidate claims.

A hunting review has exactly one decision for the episode's participant:

```json
{
  "audit_head": "THE_PROTECTED_AUDIT_HEAD",
  "decisions": [{
    "agent": "A",
    "hunting": false,
    "reason": "Reviewed commands, outputs, and source transitions for answer access.",
    "evidence_sequences": [1, 3, 5]
  }]
}
```

The example sequence numbers are placeholders. Inspect all attempted actions,
including failed, rejected, and interrupted attempts. Historical source, injection
patches containing pristine removed lines, restorations, external answer searches,
and unrecognized wrappers all require adjudication under the hunting policy.
Metadata-only inspection and ordinary working-tree diffs remain allowed. Exact
pristine-source matches are review cues, not proof by themselves. Automatic
violations remain effective even when a reviewer submits `hunting: false`.

A process review must decide all three aspects for every surviving repair:

```json
{
  "audit_head": "THE_PROTECTED_AUDIT_HEAD",
  "agent": "A",
  "entries": [{
    "defect_id": "E01",
    "repair_sequence": 3,
    "reproduction": {
      "verified": true,
      "reason": "The observed boundary failure reproduces this contract.",
      "evidence_sequences": [1]
    },
    "diagnosis": {
      "verified": true,
      "reason": "The cited seasonal rule explains the incorrect index and targeted change.",
      "evidence_sequences": [1],
      "documentation": ["BEHAVIORS.md:12"],
      "source": ["mosslight/engine.py:21"]
    },
    "verification": {
      "verified": true,
      "reason": "The same boundary reproduction succeeds after the source change.",
      "evidence_sequences": [5]
    }
  }]
}
```

Locations and sequences above illustrate syntax; use inspected locations from the
actual episode. A missing aspect uses `{"verified": false}`. If all three aspects
are false, `repair_sequence` is unnecessary and the contract earns only its 80%
behavioral component after hunting review. Omitted contract entries leave review
pending rather than silently deciding that evidence is absent.

The process validator requires completed shell evidence from the authenticated
actor, a source-changing committed repair, and valid before/after chronology.
Rejected, interrupted, malformed, or truncated observations cannot support a
positive process verdict. The host reviewer must additionally judge semantic
relevance: exit codes, nonempty reasons, and valid citations cannot prove that the
claimed failure, diagnosis, or verification is correct.

Regrade to release the reviewed reward:

```sh
python -B -m mosslight_hunt.grader.grader /path/to/protected \
  --hunting-review /path/to/hunting-review.json \
  --process-review /path/to/process-review.json > /path/to/reviewed-grade.json
```

The command writes the reviewed grade to the selected output file. Initial rollout
artifacts retain their original pending grade; reward consumers use the reviewed
file and its `reward_ready` flag.

Empty, stale, malformed, or incomplete reviews leave the scalar pending. This
workflow adds manual work; it is the chosen boundary while arbitrary shell access
prevents complete command-based detection.

## Reviewable scoring inputs

Default weighting now reads the small
[scorecard](mosslight_hunt/grader/grader_data/scorecard.json), containing contracts,
weights, documentation, source, and probe references. The injection manifest
remains available for authoring and historical verification, but the active final
reward no longer reads it.

The 117 static observation programs are readable `.py` files. Expected outcomes
remain on the host. The irrigation schedule table factors repeated world fields
without weakening full-world comparisons; equivalence checks compare original
and expanded data and execute both programs on clean and seeded fixtures.
Two additional probes and seasonal randomization remain in `FinalOracle`.

Generate a checksummed review inventory with:

```sh
python -B -m mosslight_hunt.host_only.tools.review_scoring_packet
```

The inventory counts reward modules, executable probes, expected tables, scorecard,
and referenced guides. It also lists and counts the host broker, adapter, and
visibility integration boundary separately. The full packet still contains 119
contracts and several thousand lines; this cleanup reduces duplication and
exposes the actual review surface, but does not establish that it fits an
independent reviewer's afternoon or the rubric's strict size target.

The original probe JSON is preserved under `host_only/probe_archive` for
regression comparisons. `host_only/tools/build_scorecard.py` regenerates current
inputs from that archive and the authoring manifest. Generated files are checked
in; runtime does not execute the generator.

## Historical evidence and validation

The three published runs retain their original prompts, policy, grades, and
artifacts. The verifier checks them against pinned historical helpers in
`host_only/legacy_scoring_v1` and [the recorded prompt](prompts/recorded_v1.txt).
It does not reinterpret those runs using the new reward.

Validation covers detector variations, complete review gating, pending Inspect
scores, process chronology, 80% and full credit, unrepaired and hunted submissions,
snapshot integrity, all 119 clean/seeded/individual-repair contracts, and exact
probe equivalence. The Docker regression executes the reported bypass:

```sh
git show HEAD -- mosslight/ | git apply -R
```

It restores all 119 repairs and earns 251 behavioral points, but the new detector
releases a final reward of zero. No new model rollouts were run.
