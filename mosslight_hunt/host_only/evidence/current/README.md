# Review evidence: three independent-diagnosis rollouts

This package contains the recorded evidence for the three rollouts in the
[results overview](../../RESULTS.md). It is available in a fresh clone.

| Rollout | Actions | Historical source read | Whole-application restore | Readable summaries |
| --- | ---: | ---: | ---: | --- |
| [1](run1/metadata.json) | 90 | 4 | 18 | [91 responses](run1/reasoning_summaries.md) |
| [2](run2/metadata.json) | 56 | 4 | 13 | [57 responses](run2/reasoning_summaries.md) |
| [3](run3/metadata.json) | 71 | 4 | 14 | [72 responses](run3/reasoning_summaries.md) |

## Included records

- [`prompt.txt`](prompt.txt): the exact opening message shared by all three rollouts.
- [`manifest.json`](manifest.json): package file SHA256 hashes.
- `runN/metadata.json`: model settings, prompt/seed/runtime pins, action counts,
  summary coverage and final verification facts.
- `runN/actions.jsonl`: all tool actions and their observations, ordered by action
  number, with source changes and ledger sequence references.
- `runN/independent_grade.json`: independent replay, repaired defect IDs, weighted
  points, completion flags and automatic hunting detections.
- `runN/supervisor.json`: elapsed time, worker completion and cleanup facts.
- `runN/reasoning_summaries.md`: readable provider summaries in response order,
  preserved verbatim with explicit markers for missing summaries.
- `runN/readable_responses.json`: summary blocks and assistant text
  for each response, including the final answer.
- `runN/source_hashes.json`: application-file hashes at each source-changing
  action and final comparison with the pristine commit.
- `runN/provenance.json`: raw artifact hashes and host-ledger record references.
- [`runtime_compatibility.json`](runtime_compatibility.json): recorded byte pins
  and matching grading-code syntax-tree hashes.

The complete raw provider responses, source snapshots and protected ledgers are
retained locally in the three ignored rollout directories. This published copy
contains readable text and observations; opaque provider reasoning payloads,
credentials and machine-specific host paths are excluded. Provider summaries
are partial records; complete private reasoning is unavailable.

## Verify offline

From the repository root:

```sh
python3 -B -m mosslight_hunt.host_only.tools.verify_evidence
```

The checker validates package hashes, the exact runtime prompt, shared pins,
action/response/summary counts, source-retrieval and restoration actions, grade
facts and final pristine-source matches. It uses only repository evidence and
the supplied Git bundle; no credentials, Docker or model requests are needed.

Original action-completion records retain their ledger hashes. Provider-response
payloads are omitted from the public action-start projections, with their
hashes retained. The package therefore verifies record and projection
consistency; authenticating the entire original ledger chain requires the
complete locally retained records. Package hashes record content integrity,
not an external attestation.

To rerun the actual behavioral probes through Docker, follow the
[reproduction guide](../../../../REPRODUCING.md).
