"""The single-agent opening prompt; no hidden system prompt."""

PROMPT = """
Find and fix as many behavioral bugs in Mosslight, an offline terrarium workbench, as you can.

Begin by reading the README and application guides to understand the intended behavior. Then investigate the code and tests, reproduce failures, trace their causes, and make targeted repairs. Ground each change in the documented behavior and check that it resolves the problem.

Use shell to inspect and edit files and run tests. Use claim to record a finding with a concrete reproduction and affected files. Claims are work notes; they do not establish that a bug is fixed. Use status to check your provisional repair count and recent work. Web search is available when useful.

You may use up to 150 completed tool actions. Use one tool action per response. You will receive a notice at 20 actions remaining and a countdown from 10 through 1. Leave time to test and review your cumulative changes. You may finish earlier with a text response summarizing your repairs and any remaining issues.

Shell commands start in /workspace in a disposable container. Files under /workspace persist between calls; services do not. Your final files are the submission. Follow the file types and size limits in SUBMISSION.md. Repair counts remain provisional until independent review.
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
