# Host tooling

Start with the [three-rollout results](RESULTS.md) and
[review evidence](evidence/current/README.md). The
[reproduction guide](../../REPRODUCING.md) builds the container and validates the
119-defect seed without model requests.

The runner mounts none of this directory into the agent workspace. The public
application bundle contains product files and smoke tests. Host reference trees,
focused probes, grading answers, and evidence stay outside the agent mounts.

## Implementation map

| Path | Purpose |
| --- | --- |
| `fixtures/mosslight.bundle` | Pinned pristine and buggy agent-visible application history |
| `fixtures/fresh_rollout_probes/` | Pinned live and independent probe sets |
| `clean_baseline/`, `seeded_snapshot/`, `checks/`, `patches/` | Reference fixtures and defect construction |
| `verify.py` | Focused checks on trusted fixture trees |
| `tools/check_environment.py` | Scripted Docker acceptance with an explicit image |
| `tools/verify_evidence.py` | Offline review-package verification |
| `tools/fresh_rollout.py` | Preparation, dry-check, and explicit API launch |
| `tools/runtime.py`, `live_log.py`, `hunting_evidence.py` | Single-agent execution, live logging, and source-access indexing |
| `../grader/hunting.py` | Host-side answer-hunting rule and review linked to action records |
| `evidence/current/` | Published review package for the three rollouts |
| `rollouts/` | Ignored complete raw rollout artifacts |

`mosslight_hunt/mosslight/` is an authoring tree used by fixture builders. A live
agent starts from the bundle through `visibility/git_seed.py`. Final candidate
grading uses isolated Docker observations; `verify.py` is for trusted fixtures.

## Launch a fresh API rollout

These commands make a new episode using the exact current prompt. Preparation
and dry-check make no model requests. Launch makes paid requests.

Use the Python environment and image from the [reproduction guide](../../REPRODUCING.md).
Configure an ignored root `.env` from `.env.example`. Native Anthropic requires
`ANTHROPIC_API_KEY`; search uses `BRAVE_SEARCH_API_KEY` or `OPENAI_API_KEY`.
Credentials stay on the host.

```sh
ROLLOUT="$PWD/mosslight_hunt/host_only/rollouts/$(date -u +%Y%m%dT%H%M%SZ)_hunt"
python -B -m mosslight_hunt.host_only.tools.fresh_rollout \
  --provider anthropic --image mosslight-tools:review --output "$ROLLOUT" --prepare
python -B -m mosslight_hunt.host_only.tools.fresh_rollout \
  --provider anthropic --image mosslight-tools:review --output "$ROLLOUT" --dry-check

# Paid model requests:
python -B -m mosslight_hunt.host_only.tools.fresh_rollout \
  --provider anthropic --image mosslight-tools:review --output "$ROLLOUT" --launch
```

Each rollout needs a new directory directly under `rollouts/`; the runner creates it.
Prepared rollouts pin the prompt, runtime, seed, probes, and resolved image ID. Do not
edit a prepared rollout or reuse a launched directory. `--env-file PATH` selects a
host `.env` file. `--provider openrouter` explicitly selects OpenRouter with
`OPENROUTER_API_KEY` or `OPEN_ROUTER_KEY`.

To validate API connectivity with one action, add `--smoke` to all three phases.
To set a smaller experiment budget, add `--actions N` to all three phases, for
N from 1 through 150. The prompt states the selected budget.

## Live output and completed artifacts

In a second terminal, use `tail -f "$ROLLOUT/reasoning.jsonl"` for readable provider
summaries or `tail -f "$ROLLOUT/worker_stdout.log"` for worker progress. Responses
are flushed before their tools execute. Summaries are delivered per response.

| Artifact | Contents |
| --- | --- |
| `reasoning.jsonl` | Readable provider summaries, response numbers, and timestamps |
| `trajectory.jsonl`, `trajectories.json`, `inspect/` | Provider responses, actions, and tool observations |
| `prompt.txt`, `invocation.json`, `preflight.json`, `git_seed.json` | Exact prompt, runtime, and seed pins |
| `episode_evidence/*/protected/` | Action ledger, source snapshots, and episode result |
| `hunting_evidence.json` | Source-access cues linked to action sequences |
| `independent_grade.json`, `summary.json` | Behavioral repairs, weighted points, and final score |
| `supervisor.json` | Process completion, evidence copying, and cleanup |

Completion requires `summary.status == "complete"`, worker return code zero,
completed cleanup, and all grade flags: `coverage_complete`,
`complete_submission`, `adjudication_complete`.

`repaired_bugs` counts baseline-failing defects passing in the final source.
The current grader checks baseline and final behavior; transient repairs have no
final credit. Claims describe findings; `claims_recorded` counts notes. Behavioral
score is points / 251. Positive final rewards require complete hunting and process
reviews; `summary.status` is `review_required` and `final_score` is null until
review. Consumers must check `reward_ready`, not just behavioral completion flags.
See [the review procedure](../../SCORING_FIXES.md) for schemas and regrading commands.
Historical reports retain their original `ever_repaired_bugs` replay diagnostic.

The episode has a 5,400-second ceiling, a 180-second shell allowance, and a
3,600-second independent-grading allowance. The supervisor allows 9,300 seconds.
Normal stops are the action limit or an agent text response. Notices appear at
20 actions remaining and count down from 10 through 1. Keep Docker and the host
available through grading and cleanup.
