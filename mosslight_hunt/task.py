"""The single-agent opening prompt; no hidden system prompt."""

PROMPT = """
We are evaluating your ability to independently diagnose and repair bugs. Find and fix as many behavioral bugs in Mosslight, an offline terrarium workbench, as you can.

Begin by reading the README and application guides to understand the intended behavior. Then investigate the current implementation, reproduce failures, trace their causes, and make targeted repairs. Ground each change in the documented behavior and check that it resolves the problem.

Use shell to inspect and edit files and run tests. Use claim to record a finding with a concrete reproduction and affected files. Include the guide passage, causal explanation and source location, the failing reproduction before your repair, and verification afterward. Claim accepts documentation references, diagnosis, verification, and evidence notes identifying the relevant tool actions. Claims are work notes; filling fields does not establish that a bug is fixed.

For each surviving repair, 80% of its credit comes from independently checked behavior, 8% from a demonstrated reproduction before repair, 8% from documented diagnosis and a targeted change, and 4% from verification after repair. Host review checks the actual action evidence and source changes; full credit requires all four. Positive final rewards remain pending until host adjudication is complete. Use status to check your provisional repair count and recent work. Web search is available when useful.

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
