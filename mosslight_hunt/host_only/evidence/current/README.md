# Recorded evidence

This package contains the recorded evidence for the three rollouts in the
[results overview](../../../../RESULTS.md). It is available in a fresh clone.

## Rollout prompt

The [rollout prompt](prompt.txt) is the exact opening message used in all
three rollouts: 1,291 UTF-8 bytes with no trailing newline, SHA256
`13c5c581a5f82b260f7bc91d77bdbc298dd71153e3cc8c9ec606d116bce98bd7`.
The offline verifier checks it against the runtime prompt and each
rollout's saved prompt identity.

The [runtime prompt](../../../task.py) matches this recorded text.

## Included records

- [`prompt.txt`](prompt.txt): the exact opening message shared by all three rollouts.
- [`manifest.json`](manifest.json): package file SHA256 hashes.
- `runN/metadata.json`: recorded model settings, prompt/seed/runtime pins, action
  counts, summary coverage, final verification facts, and current grade provenance.
- `runN/actions.jsonl`: all tool actions and their observations, ordered by action
  number, with source changes and ledger sequence references.
- `runN/independent_grade.json`: current-policy independent replay, repaired
  defect IDs, behavioral points, reward readiness, unadjudicated process scores,
  completion flags, and automatic hunting detections.
- `runN/supervisor.json`: elapsed time, worker completion, and cleanup facts.
- `runN/reasoning_summaries.md`: readable provider summaries in response order,
  preserved verbatim with explicit markers for missing summaries.
- `runN/readable_responses.json`: summary blocks and assistant text
  for each response, including the final answer.
- `runN/source_hashes.json`: application-file hashes at each source-changing
  action and final comparison with the pristine commit.
- `runN/provenance.json`: raw artifact hashes and host-ledger record references.
- The [current-policy replay package](../../regrades/20261006T032318Z_scoring_v2/README.md)
  supplies the scoring implementation pins, exact dynamic probe inputs, and
  baseline/final verdicts underlying the published grades.

The complete raw provider responses, source snapshots, and protected ledgers are
retained locally in the three ignored rollout directories. This published copy
contains readable text, observations, and grades from replaying the recorded
submissions with the current scorer; opaque provider reasoning payloads,
credentials, and machine-specific host paths are excluded. Provider summaries
are partial records; complete private reasoning is unavailable.

## Verify offline

From the repository root:

```sh
python3 -B -m mosslight_hunt.host_only.tools.verify_evidence
```

The checker validates package hashes, the exact runtime prompt, shared pins,
action/response/summary counts, source-retrieval and restoration actions, grade
facts, and final pristine-source matches. It uses only repository evidence and
the supplied Git bundle; no credentials, Docker, or model requests are needed.

Recorded runtime hashes and raw-artifact hashes are capture provenance, rather
than a claim that today's scoring code or published replay grade existed during
the model run. The current grades are byte-identical to the grade files in the
replay package. Each retains 251 behavioral points and a released zero reward
for answer hunting; process scores remain unadjudicated.

Action-completion records retain their original ledger hashes. Exported
action-start records omit provider-response payloads but retain their hashes.
The verifier checks consistency of these exports; verifying the full ledger
chain requires the original local records. Package hashes check content
integrity and are not an independent attestation.

To rerun the actual behavioral probes through Docker, follow the
[reproduction guide](../../../../REPRODUCING.md).
