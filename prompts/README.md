# Archived prompts

`20261002_docs_first.txt` preserves the exact UTF-8 bytes of the documentation-first
prompt before the targeted-repair revision, with no trailing newline. SHA256:

`476df75256830f21a2325e65577648241660b09ac51954c573a36382fde62bfb`.

`20261002_targeted_repair.txt` preserves the exact UTF-8 bytes of the targeted-repair
prompt before the diagnosis-evaluation revision, with no trailing newline. SHA256:

`95b5f3a190430a10f63cf3a975b9c231a64226ca76daa09f0cec40b4fb896ad8`.

`20261002_diagnosis_eval.txt` preserves the exact UTF-8 bytes of the evaluation-framed
prompt before the independent-repair revision, with no trailing newline. SHA256:

`a177ad481bcb5b68108a4357bc83e9bd0a6c4902ed44c4f71bafb9b61efef003`.

`20261002_independent_repair.txt` preserves the exact UTF-8 bytes of the
independent-repair prompt before the independent-diagnosis revision, with no
trailing newline. SHA256:

`45ad66773e2fbacf28351da24b2d197641a8246c4f5335d4fd34f290b67f439a`.

The active prompt is defined in `mosslight_hunt/task.py`. Each rollout saves its
exact opening text and hash. Archives are not mounted for the agent.
