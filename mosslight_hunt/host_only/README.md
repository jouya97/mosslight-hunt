# Host-only fixtures and tooling

The runner mounts none of this directory into an agent container. The public
application Git bundle contains only Mosslight product files and smoke tests.
See the [root README](../../README.md) and [design](../flaw.md).

- `fixtures/mosslight.bundle`: pinned public pristine and buggy application history.
- `fixtures/fresh_rollout_probes/`: inherited pinned live and independent probe sets.
- `clean_baseline/`, `seeded_snapshot/`, `checks/`, `patches/`: trusted inherited
  fixtures and defect provenance used by offline checks and reference builders.
- `verify.py`: focused checks for trusted trees; never use it to run candidate code
  directly on the host. Final candidate grading uses isolated Docker observations.
- `tools/fresh_rollout.py`: one-shot preparation, dry-check and explicit paid launch.
- `tools/runtime.py`, `live_log.py`, `hunting_evidence.py`: single-agent execution,
  flushed live response logs and post-run cue indexing.
- `rollouts/`: ignored run evidence, one new directory per attempt.
- [VALIDATION.md](VALIDATION.md): local validation and its limits.

Do not edit a prepared run or reuse a launched directory. Runtime, prompt, seed
and probe drift cause the launcher to reject the run before model requests.
