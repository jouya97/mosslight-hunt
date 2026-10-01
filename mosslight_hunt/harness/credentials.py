"""Load an allowlisted subset of dotenv data without executing shell syntax."""
import os
from pathlib import Path
import shlex

ALLOWED_KEYS = frozenset({"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "BRAVE_SEARCH_API_KEY"})
OPENROUTER_KEYS = ALLOWED_KEYS | {"OPENROUTER_API_KEY", "OPEN_ROUTER_KEY"}

def load_host_credentials(path: Path, *, allowed_keys=ALLOWED_KEYS) -> None:
    """Existing environment wins. Missing files are allowed; callers validate keys.

    Accept KEY=value, optional export, single/double quotes and inline comments.
    Variable interpolation, command substitution and multiline values are not
    evaluated. Never return, print, or include credential values in exceptions.
    """
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf8").splitlines()
    except (OSError, UnicodeError):
        raise ValueError("Unable to read the host credential file") from None
    for line in lines:
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or key not in allowed_keys or key in os.environ:
            continue
        try:
            words = shlex.split(value, comments=True, posix=True)
        except ValueError:
            raise ValueError(f"Invalid dotenv quoting for {key}") from None
        if len(words) > 1:
            raise ValueError(f"Dotenv value for {key} must be quoted if it contains spaces")
        if words:
            os.environ[key] = words[0]


def load_openrouter_credentials(path: Path) -> None:
    """Resolve the host dotenv alias without exposing it to logs or model args."""
    load_host_credentials(path, allowed_keys=OPENROUTER_KEYS)
    if not os.environ.get("OPENROUTER_API_KEY") and os.environ.get("OPEN_ROUTER_KEY"):
        os.environ["OPENROUTER_API_KEY"] = os.environ["OPEN_ROUTER_KEY"]


def load_model_credentials(model: str, path: Path) -> None:
    """Load the selected provider's credentials before starting expensive execution."""
    if model.startswith('openrouter/'):
        load_openrouter_credentials(path)
        key = 'OPENROUTER_API_KEY'
    elif model.startswith('anthropic/'):
        load_host_credentials(path)
        key = 'ANTHROPIC_API_KEY'
    elif model.startswith('mock'):
        return
    else:
        raise ValueError('Unsupported continuation provider')
    if not os.environ.get(key):
        raise ValueError(f'{key} is required; set the host environment or --env-file')
