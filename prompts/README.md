# Agent prompt

[Current prompt](current.txt) is the exact text used by all three reported rollouts:
1,291 UTF-8 bytes with no trailing newline, SHA256
`13c5c581a5f82b260f7bc91d77bdbc298dd71153e3cc8c9ec606d116bce98bd7`.

The runtime definition is [`mosslight_hunt/task.py`](../mosslight_hunt/task.py).
The [offline evidence verifier](../mosslight_hunt/host_only/tools/verify_evidence.py)
checks this copy against the runtime and each rollout's saved prompt. These review
files are host-side; the agent receives the prompt as its opening message.
