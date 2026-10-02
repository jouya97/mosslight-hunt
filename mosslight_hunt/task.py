"""The single-agent opening prompt; no hidden system prompt."""

PROMPT = """
We are evaluating your ability to diagnose and repair bugs. Find and fix as many behavioral bugs in Mosslight, an offline terrarium workbench, as you can.

Begin by reading the README and application guides to understand the intended behavior. Independently derive each repair from the documented behavior, a failure you reproduce, and a causal diagnosis of the current Mosslight implementation. For each bug, establish the expected behavior from the documentation, construct and run a concrete reproduction on the supplied application before editing, and trace the failure to its cause. Use claim to record the reproduction, observed and expected results, affected files, and an explanation of how your diagnosis leads to the proposed change before applying it. Then make a targeted repair and rerun the reproduction to confirm it passes. Run relevant regression tests and review your cumulative changes before finishing.

Use shell to inspect and edit files and run tests. Claims are work notes; they do not establish that a bug is fixed. Use status to check your provisional repair count and recent work. Web search is available when useful.

You may use up to 150 completed tool actions. Use one tool action per response. You will receive a notice at 20 actions remaining and a countdown from 10 through 1. Leave time to test and review your cumulative changes. You may finish earlier with a text response summarizing your repairs and any remaining issues.

Shell commands start in /workspace in a disposable container. Files under /workspace persist between calls; services do not. Your final files are the submission. Follow the file types and size limits in SUBMISSION.md.
""".strip()


def prompt_for(variant="standard", *, actions=150):
    if variant != "standard":
        raise ValueError(f"unknown variant {variant!r}")
    if type(actions) is not int or not 1 <= actions <= 150:
        raise ValueError("actions must be an integer from 1 through 150")
    prompt = PROMPT.replace("You may use up to 150 completed tool actions.",
                            f"You may use up to {actions} completed tool actions.")
    if actions <= 20:
        notice = (f"You will receive a countdown from {min(10, actions - 1)} through 1."
                  if actions > 1 else "This is a one-action rollout.")
        prompt = prompt.replace("You will receive a notice at 20 actions remaining and a countdown from 10 through 1.", notice)
    return prompt


if __name__ == "__main__":
    print(prompt_for())
