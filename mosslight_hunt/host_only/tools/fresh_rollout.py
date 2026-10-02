"""Fresh single-agent Mosslight via explicit Anthropic or OpenRouter provider; --offline-check never launches.

Adapted from the audited 20260928T002300Z fresh runner. Preparation and launch
are explicit operations within one unique folder per run; no historical state
is resumed. Full histories retain provider reasoning details and signatures.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import uuid

REPO = Path(__file__).resolve().parents[3]
OUT = None  # Set only by the explicit --output argument; imports have no side effects.
PYTHON = Path(sys.executable)  # Use the environment that invoked the maintained CLI.
PROVIDER = 'openrouter'
SHELL_SECONDS = 180
MODEL = 'openrouter/anthropic/claude-opus-5.5'
MODEL_ARGS = {'max_retries': 0, 'stream': False, 'reasoning_enabled': True}
MODEL_BASE_URL = 'https://openrouter.ai/api/v1'
DEFAULT_IMAGE = 'docker.io/library/mosslight-tools:local'
IMAGE_ID = DEFAULT_IMAGE  # Resolved once during preparation; subsequent phases use the saved ID.
FULL_PARTICIPANTS = 1
FULL_TURN_LIMIT = 150
PARTICIPANTS = FULL_PARTICIPANTS
TURN_LIMIT = FULL_TURN_LIMIT
SMOKE_MODE = False
ACTION_SECONDS = 5400
GRADING_SECONDS = 3600
OUTER_MARGIN_SECONDS = 300
OUTER_CAP_SECONDS = ACTION_SECONDS + GRADING_SECONDS + OUTER_MARGIN_SECONDS
EXPECTED_PROMPT_SHA256 = '36d0ec1c7a8798ee14c88bb3ccc990e25d599c1834825a2ae5926a837f830709'
EXPECTED_LIVE_PROBES_SHA256 = '277166d239f0b41799c2fb69869d016201bf417f94c65c2bfdbec35f163ba6b4'
EXPECTED_GRADING_PROBES_SHA256 = '06334d0a3e51600b389e99b118a481bf46e9ff94a420f8799eca4bfaa62ee7fe'
PROBE_SOURCE = REPO / 'mosslight_hunt/host_only/fixtures/fresh_rollout_probes'
ENV_FILE = Path(os.environ.get('MOSSLIGHT_ENV_FILE', str(REPO / '.env')))
STATUS_PROTOCOL = 'caller_only_v1'
NOTICE_COUNTS = [20, *range(10, 0, -1)]
GENERATE_CONFIG = {
    'max_retries': 0,
    'max_tokens': 64000,
    'parallel_tool_calls': False,
    'reasoning_effort': 'xhigh',
}
INSPECT_RETRIES = 0
EVIDENCE_MARKERS = (
    'invocation.json', 'summary.json', 'supervisor.json', 'trajectories.json',
    'worker_stdout.log', 'episode_evidence', 'inspect', 'reasoning.jsonl', 'trajectory.jsonl',
)
PINNED_RUNTIME_FILES = (
    'mosslight_hunt/host_only/tools/fresh_rollout.py',
    'mosslight_hunt/harness/credentials.py',
    'mosslight_hunt/harness/adapters.py',
    'mosslight_hunt/harness/merge.py',
    'mosslight_hunt/environment.py',
    'mosslight_hunt/grader/primitives.py',
    'mosslight_hunt/grader/grader_data/manifest.json',
    'mosslight_hunt/variants.json',
    'mosslight_hunt/task.py',
    'mosslight_hunt/harness/core.py',
    'mosslight_hunt/harness/parallel.py',
    'mosslight_hunt/harness/credit.py',
    'mosslight_hunt/grader/attribution.py',
    'mosslight_hunt/host_only/tools/runtime.py',
    'mosslight_hunt/host_only/tools/live_log.py',
    'mosslight_hunt/host_only/tools/hunting_evidence.py',
    'mosslight_hunt/visibility/git_seed.py',
    'mosslight_hunt/host_only/fixtures/mosslight.bundle',
    'mosslight_hunt/harness/oracle.py',
    'mosslight_hunt/grader/grader.py',
    'mosslight_hunt/grader/hunting.py',
    'mosslight_hunt/qc.json',
    'mosslight_hunt/grader/weights.py',
    'mosslight_hunt/grader/submission_contract.py',
    'mosslight_hunt/visibility/build.py',
    'mosslight_hunt/adapters/inspect/inspect_task.py',
)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def import_repo():
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))


def exact_prompt() -> tuple[str, str]:
    import_repo()
    from mosslight_hunt.task import PROMPT, prompt_for
    digest = sha_bytes(PROMPT.encode('utf-8'))
    if digest != EXPECTED_PROMPT_SHA256:
        raise RuntimeError(f'PROMPT SHA256 mismatch: {digest}')
    prompt = PROMPT if SMOKE_MODE else prompt_for(actions=TURN_LIMIT)
    return prompt, sha_bytes(prompt.encode('utf-8'))


def runtime_hashes() -> dict[str, str]:
    return {relative: sha_file(REPO / relative) for relative in PINNED_RUNTIME_FILES}


def runtime_versions() -> dict[str, str]:
    from importlib.metadata import version
    return {'python': sys.version.split()[0], **{
        package: version(package) for package in ('inspect_ai', 'anthropic', 'openai', 'pydantic')}}


def image_preflight() -> dict[str, object]:
    image = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', IMAGE_ID],
                           capture_output=True, text=True, timeout=30)
    resolved = image.stdout.strip()
    if image.returncode or not resolved.startswith('sha256:'):
        raise RuntimeError('Docker image unavailable; build the tool image before preparation')
    if IMAGE_ID.startswith('sha256:') and resolved != IMAGE_ID:
        raise RuntimeError('Pinned Docker image resolves to a different ID')
    info = subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}} {{.MemTotal}} {{.NCPU}}'],
                          capture_output=True, text=True, timeout=30)
    if info.returncode:
        raise RuntimeError('Docker daemon is unavailable')
    parts = info.stdout.strip().split()
    if len(parts) != 3:
        raise RuntimeError('Docker daemon resource report is malformed')
    version, memory_bytes, cpus = parts[0], int(parts[1]), int(parts[2])
    # The configured 16 GB VM reports decimal bytes (about 15.6 GiB).
    if memory_bytes < 15_000_000_000 or cpus < 8:
        raise RuntimeError(f'Docker resources below rollout reservation: memory={memory_bytes}, cpus={cpus}')
    running = subprocess.run(['docker', 'ps', '--format', '{{.ID}} {{.Image}} {{.Names}}'],
                              capture_output=True, text=True, timeout=20)
    if running.returncode:
        raise RuntimeError('Unable to inspect active Docker containers')
    active = [line for line in running.stdout.splitlines() if line.strip()]
    if active:
        raise RuntimeError('Docker has unrelated active containers; stop and review them before launch')
    return {'image_id': resolved, 'docker_server_version': version,
            'docker_memory_bytes': memory_bytes, 'docker_cpus': cpus, 'active_containers': active}


def configure_provider(provider: str) -> None:
    """Explicit pinned selection; never infer a fallback from available keys."""
    global PROVIDER, MODEL, MODEL_ARGS, MODEL_BASE_URL
    if provider == 'anthropic':
        MODEL = 'anthropic/claude-opus-5-5'
        MODEL_ARGS = {'max_retries': 0}
        MODEL_BASE_URL = 'https://api.anthropic.com'
    elif provider == 'openrouter':
        MODEL = 'openrouter/anthropic/claude-opus-5.5'
        MODEL_ARGS = {'max_retries': 0, 'stream': False, 'reasoning_enabled': True}
        MODEL_BASE_URL = 'https://openrouter.ai/api/v1'
    else:
        raise ValueError('Unsupported provider')
    PROVIDER = provider


def configure_scope(*, smoke: bool, actions: int | None = None) -> None:
    """Select a bounded research budget or the one-action API smoke profile."""
    global PARTICIPANTS, TURN_LIMIT, SMOKE_MODE
    if actions is not None and (type(actions) is not int or not 1 <= actions <= FULL_TURN_LIMIT):
        raise ValueError('actions must be an integer from 1 through 150')
    if smoke and actions is not None:
        raise ValueError('--smoke and --actions are mutually exclusive')
    SMOKE_MODE = smoke
    PARTICIPANTS = 1
    TURN_LIMIT = 1 if smoke else actions if actions is not None else FULL_TURN_LIMIT


def launch_settings() -> dict:
    return {'provider': PROVIDER, 'model': MODEL, 'model_args': MODEL_ARGS,
            'model_base_url': MODEL_BASE_URL, 'generation_config': GENERATE_CONFIG,
            'smoke_mode': SMOKE_MODE, 'participants': PARTICIPANTS,
            'total_action_limit_per_actor': TURN_LIMIT,
            'shell_seconds': SHELL_SECONDS, 'agent_safety_seconds': ACTION_SECONDS,
            'independent_grading_seconds': GRADING_SECONDS, 'outer_cap_seconds': OUTER_CAP_SECONDS}


def credentials_preflight(*, required: bool = True) -> dict[str, bool]:
    """Load host credentials without displaying or storing any credential value."""
    import_repo()
    from mosslight_hunt.harness.credentials import load_host_credentials, load_openrouter_credentials
    loader = load_host_credentials if PROVIDER == 'anthropic' else load_openrouter_credentials
    loader(Path(os.environ.get('MOSSLIGHT_ENV_FILE', str(ENV_FILE))))
    key = 'ANTHROPIC_API_KEY' if PROVIDER == 'anthropic' else 'OPENROUTER_API_KEY'
    result = {PROVIDER + '_available': bool(os.environ.get(key)),
              'search_available': bool(os.environ.get('BRAVE_SEARCH_API_KEY') or
                                       os.environ.get('OPENAI_API_KEY'))}
    if required and not result[PROVIDER + '_available']:
        raise RuntimeError(PROVIDER + ' credential unavailable')
    if required and not result['search_available']:
        raise RuntimeError('Web-search credential unavailable')
    return result


def validate_prepared() -> dict:
    """Fail closed on drift before starting any worker or paid model request."""
    prepared = load_json(OUT / 'preflight.json')
    if prepared.get('status') != 'ready':
        raise RuntimeError('Offline baseline preparation is not ready')
    if prepared.get('image', {}).get('image_id') != IMAGE_ID or not IMAGE_ID.startswith('sha256:'):
        raise RuntimeError('Prepared Docker image changed or is not an immutable ID')
    for key, value in launch_settings().items():
        if prepared.get(key) != value:
            raise RuntimeError(f'Prepared launch setting changed: {key}')
    if prepared.get('runtime_file_sha256') != runtime_hashes():
        raise RuntimeError('Pinned runtime files changed after offline preparation')
    if prepared.get('runtime_versions') != runtime_versions():
        raise RuntimeError('Python/provider dependencies changed after preparation; prepare a new folder')
    _, digest = exact_prompt()
    if prepared.get('prompt_sha256') != digest:
        raise RuntimeError('Prepared prompt changed')
    baseline = load_json(OUT / 'baseline_audit.json')
    if prepared.get('baseline_audit_sha256') != sha_file(OUT / 'baseline_audit.json'):
        raise RuntimeError('Prepared baseline audit changed')
    if not baseline.get('all_defects_fail_at_baseline') or baseline.get('baseline_failing_count') != 119:
        raise RuntimeError('Prepared baseline is not 119 failing defects')
    manifest = load_json(OUT / 'seed_inventory.json')
    if manifest['tree_sha256'] != prepared.get('seed_tree_sha256'):
        raise RuntimeError('Prepared seed inventory changed')
    check_seed(OUT / 'initial_buggy_seed', manifest)
    load_prepared_probes()
    return prepared


def check_seed(seed: Path, manifest: dict) -> None:
    if not seed.is_dir() or seed.is_symlink():
        raise ValueError('Fresh initial seed is missing')
    actual = []
    for path in sorted(seed.rglob('*')):
        if path.is_symlink():
            raise ValueError('Seed archive contains a symlink')
        if path.is_file():
            data = path.read_bytes()
            actual.append({'path': path.relative_to(seed).as_posix(), 'size': len(data), 'sha256': sha_bytes(data)})
    digest = sha_bytes(json.dumps(actual, sort_keys=True, separators=(',', ':')).encode())
    if actual != manifest['files'] or digest != manifest['tree_sha256']:
        raise ValueError('Fresh initial seed archive differs from its preparation inventory')


def load_probe_pair(folder: Path) -> tuple[list[dict], list[dict]]:
    live_path = folder / 'live_probes.json'
    grading_path = folder / 'grading_probes.json'
    if sha_file(live_path) != EXPECTED_LIVE_PROBES_SHA256:
        raise RuntimeError('Saved live oracle probes changed')
    if sha_file(grading_path) != EXPECTED_GRADING_PROBES_SHA256:
        raise RuntimeError('Saved independent grading probes changed')
    live, grading = load_json(live_path), load_json(grading_path)
    if live == grading:
        raise RuntimeError('Live and independent grading probes must remain distinct sets')
    return live, grading


def load_pinned_probes() -> tuple[list[dict], list[dict]]:
    if not all((PROBE_SOURCE / name).is_file() for name in ('live_probes.json', 'grading_probes.json')):
        raise RuntimeError('Pinned probe pair unavailable; pass --probes-from DIRECTORY containing live_probes.json and grading_probes.json (exact pinned hashes required)')
    return load_probe_pair(PROBE_SOURCE)


def load_prepared_probes() -> tuple[list[dict], list[dict]]:
    return load_probe_pair(OUT)


def prepare() -> dict[str, object]:
    """Build and baseline-check the actual fresh seed before any paid model call."""
    global IMAGE_ID
    if (OUT / 'preflight.json').exists() or (OUT / 'initial_buggy_seed').exists():
        raise FileExistsError('This rollout folder already contains preparation evidence')
    if not PYTHON.is_file():
        raise RuntimeError(f'Pinned Inspect Python is unavailable: {PYTHON}')
    prompt, prompt_hash = exact_prompt()
    import_repo()
    import inspect_ai
    from mosslight_hunt.grader.grader import DEFAULT_MANIFEST, FinalOracle
    from mosslight_hunt.grader.weights import manifest_weights
    from mosslight_hunt.harness.oracle import DockerOracle
    from mosslight_hunt.visibility.git_seed import build_git_seed

    image = image_preflight()
    IMAGE_ID = image['image_id']
    credentials = credentials_preflight(required=False)
    live_probes, grading_probes = load_pinned_probes()
    weights = manifest_weights()
    if (len(weights), sum(weights.values())) != (119, 251):
        raise RuntimeError('Current scoring manifest is not 119 defects / 251 points')
    for probes in (live_probes, grading_probes):
        if len(probes) != 119 or {probe['id'] for probe in probes} != set(weights):
            raise RuntimeError('Pinned probe set does not cover all 119 defects exactly once')

    source = REPO / 'mosslight_hunt/host_only/fixtures/mosslight.bundle'
    source_hash_before = sha_file(source)
    seed = OUT / 'initial_buggy_seed'
    seed_manifest = build_git_seed(seed)
    write_json(OUT / 'git_seed.json', seed_manifest.pop('git'))
    write_json(OUT / 'seed_inventory.json', seed_manifest)
    check_seed(seed, seed_manifest)
    source_hash_after = sha_file(source)
    if source_hash_before != source_hash_after:
        raise RuntimeError('Application source changed while preparing the initial seed')

    shutil.copyfile(PROBE_SOURCE / 'live_probes.json', OUT / 'live_probes.json')
    shutil.copyfile(PROBE_SOURCE / 'grading_probes.json', OUT / 'grading_probes.json')
    write_json(OUT / 'prompt.json', {'text': prompt, 'encoding': 'UTF-8', 'byte_count': len(prompt.encode('utf-8')),
                                    'sha256': prompt_hash, 'source': 'mosslight_hunt.task:PROMPT'})
    run_label = 'mosslight-fresh-' + uuid.uuid4().hex
    previous_label = os.environ.get('MOSSLIGHT_RUN_ID')
    os.environ['MOSSLIGHT_RUN_ID'] = run_label
    try:
        oracle = DockerOracle(DEFAULT_MANIFEST, IMAGE_ID, probes=live_probes)
        verdict = oracle(seed, 3600)
    finally:
        if previous_label is None:
            os.environ.pop('MOSSLIGHT_RUN_ID', None)
        else:
            os.environ['MOSSLIGHT_RUN_ID'] = previous_label
    if set(verdict) != set(weights) or any(type(value) is not bool for value in verdict.values()):
        raise RuntimeError('Baseline oracle returned a malformed verdict')
    passing = sorted(defect for defect, passed in verdict.items() if passed)
    failing = sorted(defect for defect, passed in verdict.items() if not passed)
    baseline = {
        'seed_kind': 'pinned buggy application release with pristine application Git history',
        'seed_tree_sha256': seed_manifest['tree_sha256'],
        'source_inventory_sha256_before': source_hash_before,
        'source_inventory_sha256_after': source_hash_after,
        'image_id': IMAGE_ID,
        'live_probe_sha256': sha_file(OUT / 'live_probes.json'),
        'defect_count': len(weights),
        'eligible_points': sum(weights.values()),
        'passing_defects': passing,
        'baseline_failing_defects': failing,
        'baseline_failing_count': len(failing),
        'all_defects_fail_at_baseline': len(failing) == len(weights),
        'status_protocol': STATUS_PROTOCOL,
        'initial_actions': {'A':0},
        'initial_claims': 0,
        'inspect_version': inspect_ai.__version__,
        'runtime_file_sha256': runtime_hashes(),
    }
    write_json(OUT / 'baseline_audit.json', baseline)
    if not baseline['all_defects_fail_at_baseline']:
        write_json(OUT / 'preflight.json', {'status': 'rejected_baseline_not_all_failing',
            'baseline_audit': str(OUT / 'baseline_audit.json'), 'image': image})
        raise RuntimeError(f"Fresh seed baseline has {len(passing)} passing defects; expected 0")
    preflight = {'status': 'ready', 'prepared_at_unix': time.time(), 'image': image,
                 'credentials': credentials,
                 'prompt_sha256': prompt_hash, 'prompt_utf8_bytes': len(prompt.encode('utf-8')),
                 'live_probe_sha256': sha_file(OUT / 'live_probes.json'),
                 'grading_probe_sha256': sha_file(OUT / 'grading_probes.json'),
                 'baseline_audit': 'baseline_audit.json', 'seed_inventory': 'seed_inventory.json',
                 'prepared_probe_source': str(PROBE_SOURCE),
                 'seed_tree_sha256': seed_manifest['tree_sha256'], 'runtime_file_sha256': runtime_hashes(),
                 'model': MODEL, 'model_args': MODEL_ARGS, 'model_base_url': MODEL_BASE_URL,
                 'generation_config': GENERATE_CONFIG, 'participants': PARTICIPANTS,
                 'total_action_limit_per_actor': TURN_LIMIT, 'status_protocol': STATUS_PROTOCOL,
                 'notice_counts': NOTICE_COUNTS}
    preflight.update(launch_settings())
    preflight['runtime_versions'] = runtime_versions()
    preflight['baseline_audit_sha256'] = sha_file(OUT / 'baseline_audit.json')
    write_json(OUT / 'preflight.json', preflight)
    return preflight


def output_content(message) -> list[dict[str, object]]:
    """Readable, concise summaries; full original messages remain in trajectories.json and Inspect logs."""
    content = message.content
    if isinstance(content, str):
        return [{'type': 'text', 'summary': content[:2000]}]
    result = []
    for block in content or []:
        kind = getattr(block, 'type', None)
        if kind in ('reasoning', 'text'):
            if kind == 'reasoning':
                value = getattr(block, 'summary', None)
                if not value and not getattr(block, 'redacted', False):
                    value = getattr(block, 'reasoning', None)
            else:
                value = getattr(block, 'text', None)
            if value:
                result.append({'type': kind, 'summary': str(value)[:2000]})
        elif kind == 'tool_use':
            result.append({'type': kind, 'name': getattr(block, 'name', None),
                           'input': getattr(block, 'input', None)})
        elif kind == 'tool_result':
            result.append({'type': kind, 'summary': str(getattr(block, 'content', ''))[:1000]})
    return result


def readable_trajectories(histories: dict, participants: list[str]) -> list[dict[str, object]]:
    output = []
    for actor in participants:
        messages = []
        for message in histories.get(actor, []):
            role = getattr(message, 'role', None)
            if role == 'assistant':
                content = output_content(message)
            else:
                content = output_content(message)
            calls = []
            for call in getattr(message, 'tool_calls', None) or []:
                calls.append({'name': getattr(call, 'function', None),
                              'arguments': getattr(call, 'arguments', None)})
            messages.append({'role': str(role), 'content': content, 'tool_calls': calls})
        output.append({'actor': actor, 'message_count': len(messages), 'messages': messages})
    return output


def model_stop_reason(output) -> str:
    choices = getattr(output, 'choices', None) or []
    return getattr(choices[0], 'stop_reason', 'unknown') if choices else 'unknown'


def ensure_clean_model_termination(output) -> None:
    if not (getattr(output.message, 'tool_calls', None) or []) and model_stop_reason(output) != 'stop':
        raise RuntimeError(f'Model ended without a tool call using stop_reason={model_stop_reason(output)!r}')


def validate_completion(logs, competition) -> None:
    if not logs or any(log.status != 'success' or getattr(log, 'error', None) for log in logs):
        raise RuntimeError('Inspect evaluation did not finish cleanly')
    if any(getattr(sample, 'error', None) for log in logs for sample in (getattr(log, 'samples', None) or [])):
        raise RuntimeError('Inspect sample contains an error')
    if competition.reason not in ('agents_exhausted', 'turn_limit'):
        raise RuntimeError(f'Repair session stopped unexpectedly: {competition.reason}')
    if competition.inflight:
        raise RuntimeError('Competition ended with unfinished tool actions')
    if any(type(count) is not int or count < 0 or count > TURN_LIMIT
           for count in competition.turns_used.values()):
        raise RuntimeError(f'Participant action count is outside the total {TURN_LIMIT}-action limit')
    unfinished = [actor for actor in competition.agents
                  if actor not in competition.finished and competition.turns_used[actor] != TURN_LIMIT]
    if unfinished:
        raise RuntimeError(f'Participants neither finished normally nor reached the action limit: {unfinished}')
    if competition.reason == 'agents_exhausted' and competition.finished != set(competition.agents):
        raise RuntimeError('Competition reported agents_exhausted before every model finished')
    if SMOKE_MODE and any(competition.turns_used.get(actor) != 1 for actor in competition.agents):
        raise RuntimeError('One-action smoke did not record exactly one completed tool action per actor')


def collect_inspect_logs(logs) -> list[dict[str, object]]:
    summaries = []
    for log in logs:
        samples = []
        for sample in getattr(log, 'samples', None) or []:
            samples.append({'sample_id': sample.id, 'error': str(sample.error) if sample.error else None,
                            'scores': str(sample.scores) if sample.scores else None})
        summaries.append({'status': log.status, 'error': str(log.error) if log.error else None,
                          'stats': str(log.stats), 'samples': samples})
    return summaries


def worker() -> int:
    import_repo()
    import inspect_ai
    from inspect_ai import Task, eval as inspect_eval
    from inspect_ai.dataset import Sample
    from inspect_ai.model import ChatMessage, ChatMessageUser, GenerateConfig, get_model
    from inspect_ai.solver import solver
    from inspect_ai.tool import ToolInfo, ToolParams
    from mosslight_hunt.adapters.inspect.inspect_task import require_single_tool_call
    from mosslight_hunt.grader.grader import FinalOracle, grade_episode
    from mosslight_hunt.grader.weights import DEFAULT_MANIFEST, manifest_weights
    from mosslight_hunt.harness.adapters import BraveSearch, OpenAISearch
    from mosslight_hunt.harness.core import DockerShell, ScriptedAgent, TOOLS
    from mosslight_hunt.harness.oracle import DockerOracle
    from mosslight_hunt.harness.parallel import ACTIONS_REMAINING_NOTICES, ParallelCompetition
    from mosslight_hunt.host_only.tools.runtime import continue_participants
    from mosslight_hunt.host_only.tools.live_log import LiveLog
    validate_worker_gate()
    validate_prepared()
    credentials_preflight()
    prompt, prompt_hash = exact_prompt()
    if runtime_hashes() != load_json(OUT / 'preflight.json')['runtime_file_sha256']:
        raise RuntimeError('Pinned runtime files changed after offline preparation')
    preflight = load_json(OUT / 'preflight.json')
    seed_manifest = load_json(OUT / 'seed_inventory.json')
    check_seed(OUT / 'initial_buggy_seed', seed_manifest)
    live_probes, grading_probes = load_prepared_probes()
    if sha_file(OUT / 'live_probes.json') != EXPECTED_LIVE_PROBES_SHA256:
        raise RuntimeError('Prepared live probes changed')
    if sha_file(OUT / 'grading_probes.json') != EXPECTED_GRADING_PROBES_SHA256:
        raise RuntimeError('Prepared grading probes changed')
    if set(ACTIONS_REMAINING_NOTICES) != set(NOTICE_COUNTS):
        raise RuntimeError('Harness countdown differs from the pinned 20,10..1 notice policy')
    if (len(manifest_weights()), sum(manifest_weights().values())) != (119, 251):
        raise RuntimeError('Defect manifest changed after preparation')

    stage = Path(os.environ['MOSSLIGHT_STAGE_ROOT']).resolve()
    tree = stage / 'shared'
    shutil.copytree(OUT / 'initial_buggy_seed', tree)
    participants = ['A']
    histories = {actor: [ChatMessageUser(content=prompt)] for actor in participants}
    tools = [ToolInfo(name=tool['name'], description=tool['description'],
                      parameters=ToolParams.model_validate(tool['input_schema'])) for tool in TOOLS]
    oracle = DockerOracle(DEFAULT_MANIFEST, IMAGE_ID, probes=live_probes)
    search = BraveSearch() if os.environ.get('BRAVE_SEARCH_API_KEY') else OpenAISearch()
    competition = ParallelCompetition(tree, stage / 'protected', DockerShell(IMAGE_ID), oracle,
        {actor: ScriptedAgent([]) for actor in participants}, weights=manifest_weights(), search=search,
        prompt=prompt, status_protocol=STATUS_PROTOCOL, shell_seconds=SHELL_SECONDS)
    live_log = LiveLog(OUT)
    runtime = {'competition': competition, 'histories': histories, 'participants': participants,
               'stage': stage, 'logs': [], 'grade': None}

    @solver
    def fresh_solver():
        async def solve(state, generate):
            model = get_model()
            require_single_tool_call(model)
            try:
                await asyncio.to_thread(competition.begin, ACTION_SECONDS, TURN_LIMIT)
                baseline = competition.baseline
                if len(baseline) != 119 or any(baseline.values()):
                    raise RuntimeError('Live baseline is not 119 failing defects; refusing model calls')

                async def clean_generate(messages, **kwargs):
                    output = await model.generate(messages, **kwargs)
                    return output

                def received(identity, output, messages):
                    live_log.response(identity, output, messages)
                    ensure_clean_model_termination(output)

                await continue_participants(competition, histories, clean_generate, tools,
                                            GenerateConfig(**GENERATE_CONFIG),
                                            response_received=received, observation_received=live_log.observation)
            finally:
                if competition.started:
                    await asyncio.to_thread(competition.finish)
                state.messages = histories['A']
                state.metadata['hunt_conversations'] = {
                    actor: [message.model_dump(mode='json') for message in messages]
                    for actor, messages in histories.items()}
                state.metadata['fresh_run'] = True
            state.completed = True
            return state
        return solve

    # A task has one sample and no automatic scorer; the host runs its independent
    # replay only after Inspect reports a clean completed sample.
    logs = []
    success = False
    try:
        task = Task(dataset=[Sample(input=prompt, id='fresh-all-defects')], solver=fresh_solver())
        logs = inspect_eval(task, model=MODEL, model_args=MODEL_ARGS, model_base_url=MODEL_BASE_URL,
            log_dir=str(OUT / 'inspect'), epochs=1, retry_on_error=INSPECT_RETRIES,
            max_retries=INSPECT_RETRIES, display='plain')
        runtime['logs'] = logs
        validate_completion(logs, competition)
        # Independent replay must use the separately pinned grading set and same image.
        final_oracle = FinalOracle(image=IMAGE_ID)
        final_oracle.probes = grading_probes
        final_oracle.covered = {probe['id'] for probe in grading_probes}
        grade = grade_episode(stage / 'protected', oracle=final_oracle, seconds=GRADING_SECONDS)
        runtime['grade'] = grade
        write_json(OUT / 'independent_grade.json', grade)
        if not (grade.get('adjudication_complete') and grade.get('complete_submission')
                and grade.get('coverage_complete') and grade.get('covered_points') == 251):
            raise RuntimeError('Independent grading did not complete full adjudication and submission coverage')
        success = True
        write_json(OUT / 'summary.json', {
            'status': 'complete', 'model': MODEL, 'image_id': IMAGE_ID,
            'participants': participants, 'action_limit_per_participant': TURN_LIMIT,
            'turns_used': competition.turns_used, 'finished': sorted(competition.finished),
            'stop_reason': competition.reason, 'status_protocol': STATUS_PROTOCOL,
            'inspect_version': inspect_ai.__version__, 'inspect': collect_inspect_logs(logs),
            'provisional_result': competition.result, 'independent_grade': grade,
            'baseline_failing_count': len(competition.baseline),
            'repaired_bugs': grade['repaired_bugs']['A'],
            'ever_repaired_bugs': grade['ever_repaired_bugs']['A'],
            'claims_recorded': len(competition.claims),
            'final_score': grade['score'], 'behavioral_scores': grade['behavioral_scores'],
            'hunting':grade['hunting'],
            'prompt_sha256': prompt_hash,
            'live_probe_sha256': sha_file(OUT / 'live_probes.json'),
            'grading_probe_sha256': sha_file(OUT / 'grading_probes.json'),
        })
        return 0
    finally:
        live_log.close()
        ledger = stage / 'protected/events.jsonl'
        if ledger.exists():
            from mosslight_hunt.host_only.tools.hunting_evidence import index_ledger
            write_json(OUT / 'hunting_evidence.json', index_ledger(ledger))
        # Full original conversations and readable summaries survive both success and failure.
        histories_json = {actor: [message.model_dump(mode='json') for message in messages]
                          for actor, messages in runtime['histories'].items()}
        write_json(OUT / 'trajectories.json', [{'sample_id': 'fresh-all-defects',
                                                'conversations': histories_json}])
        write_json(OUT / 'readable_summaries.json', readable_trajectories(runtime['histories'], participants))
        if runtime['logs']:
            write_json(OUT / 'inspect_summary.json', collect_inspect_logs(runtime['logs']))
        if runtime['grade'] is None and (stage / 'protected' / 'result.json').exists():
            write_json(OUT / 'partial_hunt_result.json', load_json(stage / 'protected' / 'result.json'))
        write_json(OUT / 'partial_summary.json', {
            'status': 'complete' if success else 'failed', 'turns_used': competition.turns_used,
            'finished': sorted(competition.finished), 'stop_reason': competition.reason,
            'inspect': collect_inspect_logs(runtime['logs']),
            'independent_grade': runtime['grade'],
        })


def redacted_error(exc: BaseException) -> dict[str, str]:
    message = str(exc)
    for key, value in os.environ.items():
        if value and any(word in key for word in ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'OPEN_ROUTER_KEY')):
            message = message.replace(value, '[REDACTED]')
    return {'error_type': type(exc).__name__, 'message': message}


def dry_check() -> int:
    if not PYTHON.is_file():
        raise RuntimeError(f'Pinned Inspect Python is unavailable: {PYTHON}')
    prompt, digest = exact_prompt()
    from mosslight_hunt.grader.weights import manifest_weights
    from mosslight_hunt.harness.parallel import ACTIONS_REMAINING_NOTICES
    import inspect_ai
    image = image_preflight()
    credentials = credentials_preflight(required=False)
    live, grading = load_prepared_probes()
    if (len(manifest_weights()), sum(manifest_weights().values())) != (119, 251):
        raise RuntimeError('Manifest is not 119 defects / 251 points')
    if set(ACTIONS_REMAINING_NOTICES) != set(NOTICE_COUNTS):
        raise RuntimeError('Countdown policy does not match 20,10..1')
    if not (OUT / 'preflight.json').is_file():
        raise RuntimeError('Offline baseline preparation has not been completed')
    prepared = load_json(OUT / 'preflight.json')
    if prepared.get('status') != 'ready' or prepared.get('prompt_sha256') != digest:
        raise RuntimeError('Offline preparation is missing or does not match current prompt')
    validate_prepared()
    used = [name for name in EVIDENCE_MARKERS if (OUT / name).exists()]
    print(json.dumps({'dry_check': 'ready', 'output': str(OUT), 'repo': str(REPO),
        'model': MODEL, 'participants': PARTICIPANTS, 'action_limit_per_participant': TURN_LIMIT,
        'prompt_sha256': digest, 'prompt_utf8_bytes': len(prompt.encode('utf-8')),
        'defects': len(manifest_weights()), 'points': sum(manifest_weights().values()),
        'status_protocol': STATUS_PROTOCOL, 'notice_counts': NOTICE_COUNTS,
        'live_probe_sha256': sha_file(OUT / 'live_probes.json'),
        'grading_probe_sha256': sha_file(OUT / 'grading_probes.json'),
        'live_and_grading_probes_are_distinct': live != grading,
        'inspect_version': inspect_ai.__version__, 'image_preflight': image,
        'credential_presence': credentials,
        'runtime_file_sha256': runtime_hashes(), 'evidence_already_present': used}, indent=2))
    return 0


def controller() -> int:
    if not (OUT / 'preflight.json').is_file() or load_json(OUT / 'preflight.json').get('status') != 'ready':
        raise RuntimeError('Run --prepare and --dry-check before the one-shot paid launch')
    validate_prepared()
    used = [name for name in EVIDENCE_MARKERS if (OUT / name).exists()]
    if used:
        raise RuntimeError(f'Rollout folder already contains run evidence: {used}')
    prompt, prompt_hash = exact_prompt()
    image = image_preflight()
    credentials = credentials_preflight()
    from mosslight_hunt.grader.weights import manifest_weights
    from mosslight_hunt.harness.parallel import ACTIONS_REMAINING_NOTICES
    import inspect_ai
    run_label = 'mosslight-fresh-' + uuid.uuid4().hex
    stage_parent = Path(tempfile.mkdtemp(prefix='mosslight-fresh-'))
    invocation = {
        'status': 'starting', 'run_label': run_label, 'model': MODEL, 'model_args': MODEL_ARGS, 'model_base_url': MODEL_BASE_URL,
        'image': IMAGE_ID, 'participants': PARTICIPANTS, 'action_limit_per_participant': TURN_LIMIT,
        'agent_safety_seconds': ACTION_SECONDS, 'independent_grading_seconds': GRADING_SECONDS,
        'outer_cap_seconds': OUTER_CAP_SECONDS, 'outer_margin_seconds': OUTER_MARGIN_SECONDS,
        'inspect_retries': INSPECT_RETRIES, 'inspect_version': inspect_ai.__version__,
        'generation_config': GENERATE_CONFIG, 'status_protocol': STATUS_PROTOCOL,
        'actions_remaining_notices': NOTICE_COUNTS, 'prompt_source': 'mosslight_hunt.task:PROMPT',
        'prompt_sha256': prompt_hash, 'prompt_utf8_bytes': len(prompt.encode('utf-8')),
        'prompt_text': prompt, 'task_py_sha256': sha_file(REPO / 'mosslight_hunt/task.py'),
        'runtime_file_sha256': runtime_hashes(), 'seed_tree_sha256': load_json(OUT / 'seed_inventory.json')['tree_sha256'],
        'baseline_audit_sha256': sha_file(OUT / 'baseline_audit.json'),
        'live_probe_sha256': sha_file(OUT / 'live_probes.json'),
        'grading_probe_sha256': sha_file(OUT / 'grading_probes.json'),
        'image_preflight': image, 'argv': [str(PYTHON), '-B', str(Path(__file__).resolve()), '--provider', PROVIDER, '--env-file', str(ENV_FILE), '--output', str(OUT), '--worker'],
        'credential_presence': credentials,
        'neutral_staging_parent': str(stage_parent), 'started_unix': time.time(),
        'host_environment_file': str(ENV_FILE), 'credential_values_saved': False,
        'initial_action_counts': {'A':0}, 'initial_claim_count': 0,
    }
    invocation.update(launch_settings())
    if SMOKE_MODE:
        invocation['argv'].append('--smoke')
    else:
        invocation['argv'].extend(['--actions', str(TURN_LIMIT)])
    (OUT / 'prompt.txt').write_text(prompt, encoding='utf-8')
    with (OUT / 'invocation.json').open('x', encoding='utf-8') as stream:
        json.dump(invocation, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    env = {**os.environ, 'MOSSLIGHT_RUN_ID': run_label,
           'MOSSLIGHT_STAGE_ROOT': str(stage_parent), 'MOSSLIGHT_ENV_FILE': str(ENV_FILE)}
    child = None
    hard_timeout = False
    launch_error = None
    started_mono = time.monotonic()
    with (OUT / 'worker_stdout.log').open('w', encoding='utf-8') as stdout:
        try:
            command = invocation['argv']
            child = subprocess.Popen(command, cwd=REPO, env=env, stdout=stdout,
                                     stderr=subprocess.STDOUT, start_new_session=True)
            invocation.update(status='live_invocation_started', pid=child.pid, launch_unix=time.time())
            write_json(OUT / 'invocation.json', invocation)
            print('FRESH_LIVE_INVOCATION_STARTED', child.pid, flush=True)
            child.wait(timeout=OUTER_CAP_SECONDS)
        except subprocess.TimeoutExpired:
            hard_timeout = True
            if child is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=10)
        except BaseException as exc:
            launch_error = redacted_error(exc)
            if child is not None and child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=10)

    cleanup = {'complete': False, 'containers_removed': 0}
    try:
        listed = subprocess.run(['docker', 'ps', '-aq', '--filter', 'label=mosslight.run=' + run_label],
                                capture_output=True, text=True, timeout=15, check=True)
        containers = [item for item in listed.stdout.splitlines()
                      if item and all(char in '0123456789abcdef' for char in item)]
        if containers:
            subprocess.run(['docker', 'rm', '-f', *containers], capture_output=True, text=True,
                           timeout=30, check=True)
        cleanup = {'complete': True, 'containers_removed': len(containers)}
    except Exception as exc:
        cleanup = {'complete': False, 'error_type': type(exc).__name__, 'run_label': run_label}

    copied = []
    evidence_out = OUT / 'episode_evidence'
    evidence_out.mkdir(exist_ok=True)
    copy_complete = False
    try:
        destination = evidence_out / stage_parent.name
        if destination.exists():
            raise FileExistsError(destination)
        shutil.copytree(stage_parent, destination)
        copied.append(str(destination.relative_to(OUT)))
        copy_complete = True
    except Exception as exc:
        write_json(OUT / 'evidence_copy_error.json', {'error_type': type(exc).__name__,
            'message': redacted_error(exc)['message'], 'staging_parent': str(stage_parent),
            'staging_retained': True})
    supervisor = {'hard_timeout': hard_timeout,
        'worker_returncode': child.returncode if child is not None else None,
        'launch_error': launch_error, 'elapsed_seconds': round(time.monotonic() - started_mono, 3),
        'outer_cap_seconds': OUTER_CAP_SECONDS, 'cleanup': cleanup, 'copied_evidence_paths': copied,
        'staging_copied': copy_complete, 'staging_retained': not copy_complete}
    write_json(OUT / 'supervisor.json', supervisor)
    invocation.update(status='outer_timeout' if hard_timeout else 'launch_error' if launch_error else 'worker_finished',
                      finished_unix=time.time())
    write_json(OUT / 'invocation.json', invocation)
    if copy_complete:
        try:
            shutil.rmtree(stage_parent)
        except OSError:
            supervisor['staging_cleanup_error'] = True
            supervisor['staging_retained'] = True
            write_json(OUT / 'supervisor.json', supervisor)
    print('FRESH_SUPERVISOR_FINISHED', child.returncode if child is not None else None,
          'hard_timeout', hard_timeout, 'cleanup', cleanup['complete'], flush=True)
    if hard_timeout or launch_error or not cleanup['complete'] or not copy_complete:
        return 2
    return child.returncode if child is not None else 2


def offline_check() -> int:
    """No Docker, network, model request, output directory, or run start."""
    import_repo()
    import importlib.metadata
    from inspect_ai.model import GenerateConfig, get_model
    from mosslight_hunt.harness.parallel import ACTIONS_REMAINING_NOTICES
    from mosslight_hunt.grader.weights import manifest_weights
    prompt, digest = exact_prompt()
    assert set(ACTIONS_REMAINING_NOTICES) == set(NOTICE_COUNTS)
    assert (len(manifest_weights()), sum(manifest_weights().values())) == (119, 251)
    load_pinned_probes()
    # A dummy credential verifies local construction without letting a real key
    # enter model arguments or SDK serialization during offline checks.
    model = get_model(MODEL, api_key='offline-dummy', base_url=MODEL_BASE_URL,
                      memoize=False, **MODEL_ARGS)
    if PROVIDER == 'openrouter':
        params = model.api.completion_params(GenerateConfig(**GENERATE_CONFIG), tools=True)
        assert params['extra_body']['reasoning'] == {'effort': 'xhigh', 'enabled': True}
        assert params['parallel_tool_calls'] is False
    asyncio.run(model.api.aclose())
    credentials = credentials_preflight(required=False)
    print(json.dumps({'status': 'offline_ready_not_launched', **launch_settings(),
        'model_args': MODEL_ARGS, 'generation_config': GENERATE_CONFIG,
        'participants': PARTICIPANTS, 'actions_per_actor': TURN_LIMIT,
        'prompt_sha256': digest, 'status_protocol': STATUS_PROTOCOL,
        'notice_counts': NOTICE_COUNTS, 'credential_presence': credentials,
        'inspect_version': importlib.metadata.version('inspect_ai'),
        'openai_version': importlib.metadata.version('openai'),
        'live_provider_compatibility_tested': False}, indent=2))
    return 0


def validate_worker_gate() -> None:
    invocation = load_json(OUT / 'invocation.json')
    if (not os.environ.get('MOSSLIGHT_RUN_ID') or
            invocation.get('run_label') != os.environ['MOSSLIGHT_RUN_ID'] or
            invocation.get('neutral_staging_parent') != os.environ.get('MOSSLIGHT_STAGE_ROOT') or
            invocation.get('provider') != PROVIDER):
        raise RuntimeError('Worker requires the explicit launch controller')
    mismatches = [key for key, value in launch_settings().items() if invocation.get(key) != value]
    if mismatches:
        raise RuntimeError(f'Worker launch settings differ from recorded invocation: {mismatches}')


def main(default_provider: str | None = None) -> int:
    global OUT, PROBE_SOURCE, ENV_FILE, IMAGE_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=('anthropic', 'openrouter'),
                        default=default_provider, required=default_provider is None)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--probes-from', type=Path, help='Directory containing the exact pinned live/grading probe pair; used by prepare and offline-check')
    parser.add_argument('--env-file', type=Path, help='Host credential dotenv path (also accepts MOSSLIGHT_ENV_FILE)')
    parser.add_argument('--image', help='Locally built tool image for preparation; saved as its immutable ID')
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--smoke', action='store_true',
                        help='Use the explicit single-agent, one-tool-action validation profile')
    scope.add_argument('--actions', type=int,
                       help='Completed action budget from 1 through 150 (default: 150); use in all phases')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--offline-check', action='store_true')
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--dry-check', action='store_true')
    modes.add_argument('--launch', action='store_true')
    modes.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    configure_provider(args.provider)
    configure_scope(smoke=args.smoke, actions=args.actions)
    if args.probes_from is not None:
        PROBE_SOURCE = args.probes_from.resolve()
    if args.env_file is not None:
        ENV_FILE = args.env_file.resolve()
        os.environ['MOSSLIGHT_ENV_FILE'] = str(ENV_FILE)
    if args.offline_check:
        if args.image is not None:
            parser.error('--image applies only to --prepare')
        return offline_check()
    if args.output is None:
        parser.error('--output is required for preparation and launch')
    OUT = args.output.resolve()
    rollout_root = (REPO / 'mosslight_hunt/host_only/rollouts').resolve()
    if OUT.parent != rollout_root:
        parser.error('--output must be a direct child of host_only/rollouts')
    if args.prepare:
        IMAGE_ID = args.image or DEFAULT_IMAGE
        OUT.mkdir(parents=True, exist_ok=False)
        print(json.dumps(prepare(), indent=2))
        return 0
    if args.image is not None:
        parser.error('--image applies only to --prepare; later phases use the recorded immutable image')
    IMAGE_ID = load_json(OUT / 'preflight.json').get('image', {}).get('image_id', '')
    if not IMAGE_ID.startswith('sha256:'):
        raise RuntimeError('Preparation is missing an immutable Docker image ID')
    if args.dry_check:
        return dry_check()
    if args.worker:
        try:
            return worker()
        except BaseException as exc:
            detail = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            write_json(OUT / 'worker_failure.json', {'error_type': type(exc).__name__,
                'traceback': redacted_error(RuntimeError(detail))['message']})
            print('FRESH_WORKER_FAILED', type(exc).__name__, flush=True)
            return 2
    return controller()


if __name__ == '__main__':
    raise SystemExit(main())
