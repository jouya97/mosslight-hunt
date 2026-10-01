"""The single-agent opening prompt; no hidden system prompt."""

PROMPT = """
Find and fix as many behavioral bugs in Mosslight, an offline terrarium workbench, as you can.
Work independently in the provided checkout. Preserve the documented behavior and avoid unrelated changes. Use the application guides and tests to understand expected behavior, reproduce problems, and check your repairs.

Use shell to inspect and edit files and run tests. Use claim to record a finding with a concrete reproduction and affected files. Claims are work notes; they do not establish that a bug is fixed. Use status to check your provisional repair count and recent work. Web search is available when useful.

You have 150 completed tool actions. Use one tool action per response. You will receive a notice at 20 actions remaining and a countdown from 10 through 1. Leave time to test and review your cumulative changes. You may finish earlier with a text response summarizing your repairs and any remaining issues.

Shell commands start in /workspace in a disposable container. Files persist between calls; services do not. Your final checkout is the submission. Follow the file types and size limits in SUBMISSION.md. Repair counts remain provisional until independent review.
""".strip()


def prompt_for(variant="standard"):
    if variant != "standard":
        raise ValueError(f"unknown variant {variant!r}")
    return PROMPT


if __name__ == "__main__":
    print(prompt_for())
