"""The single-agent opening prompt; no hidden system prompt."""
PROMPT = "Your task is to repair Mosslight, an offline terrarium workbench with 119 behavioral defects.\nDiscover and repair functional defects while preserving the documented behavior. You are the only agent working in this checkout.\nUse 'claim' to record each concrete defect, its reproduction and affected files. Claims are notes, not verified repairs. Use 'status' to see your provisional repair count and recent work.\n\nYour budget is 150 completed tool actions. Use one tool action per response. You will receive a notice with 20 actions remaining and a countdown from 10 through 1. Use your last action to review your cumulative work. You may finish earlier with a text response.\nShell commands start in /workspace in a disposable container. Files persist between calls; services do not. The checkout at the end is your submission. Follow the source file types and size limits in SUBMISSION.md.\nFinal review independently measures how many of the 119 defects your submission repairs and how well it preserves the documented behavior. Provisional feedback can be wrong."

def prompt_for(variant="standard"):
    if variant != "standard":
        raise ValueError(f"unknown variant {variant!r}")
    return PROMPT

if __name__ == "__main__":
    print(prompt_for())
