# Agent prompts

[Current prompt](current.txt) is the active v2 prompt: 1,969 UTF-8
bytes with no trailing newline, SHA256
`bdaefd17bba247f2e051ad6fe9043a3058ffeb0a67cad561e6ec2219ce332d50`.
Its runtime definition is [`mosslight_hunt/task.py`](../mosslight_hunt/task.py).
It explains behavioral and process credit; claims remain work notes.

[Recorded v1 prompt](recorded_v1.txt) is the exact text used by all three published
rollouts: 1,291 UTF-8 bytes with no trailing newline, SHA256
`13c5c581a5f82b260f7bc91d77bdbc298dd71153e3cc8c9ec606d116bce98bd7`.
The [offline evidence verifier](../mosslight_hunt/host_only/tools/verify_evidence.py)
checks it against the archived runtime prompt and each rollout's saved prompt.
The recorded evidence is not rescored under v2.
