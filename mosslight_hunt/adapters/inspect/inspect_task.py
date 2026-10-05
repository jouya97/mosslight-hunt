"""Single-agent Inspect entry point. The maintained launcher adds preparation/pinning."""
import asyncio
from pathlib import Path
import tempfile

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageUser, GenerateConfig, get_model
from inspect_ai.scorer import Score, scorer, mean, stderr
from inspect_ai.solver import solver
from inspect_ai.tool import ToolInfo, ToolParams

from mosslight_hunt.environment import Environment
from mosslight_hunt.grader.grader import grade_episode, training_scores
from mosslight_hunt.harness.core import STATUS_CALLER_ONLY
from mosslight_hunt.host_only.tools.runtime import continue_participants
from mosslight_hunt.host_only.tools.live_log import LiveLog
from mosslight_hunt.task import prompt_for

PARTICIPANTS = 1
TURNS = 150
EPISODE_SECONDS = 5400
GRADING_SECONDS = 3600
GENERATE_CONFIG = GenerateConfig(max_retries=0, max_tokens=64000, parallel_tool_calls=False,
                                 reasoning_effort='xhigh')
SINGLE_TOOL_CHOICE = {'type':'auto', 'disable_parallel_tool_use':True}


def require_single_tool_call(model):
    from inspect_ai.model._providers.anthropic import AnthropicAPI
    api = getattr(model, 'api', None)
    if isinstance(api, AnthropicAPI):
        api.extra_body = (api.extra_body or {}) | {'tool_choice':SINGLE_TOOL_CHOICE}


@solver
def hunt_solver(seconds=EPISODE_SECONDS, output_root=None, turns=TURNS):
    async def solve(state, generate):
        root = Path(tempfile.mkdtemp(prefix='mosslight-hunt-', dir=output_root))
        environment = Environment('standard', {'seconds':seconds, 'participants':1, 'turns':turns,
                                               'status_protocol':STATUS_CALLER_ONLY})
        histories = {'A':[ChatMessageUser(content=prompt_for())]}
        live = LiveLog(root)
        model = get_model()
        require_single_tool_call(model)
        try:
            setup = asyncio.create_task(asyncio.to_thread(environment.reset_parallel, root))
            try:
                await asyncio.shield(setup)
            except asyncio.CancelledError:
                await asyncio.gather(setup, return_exceptions=True)
                if hasattr(environment, 'competition'):
                    environment.competition.stop(TimeoutError('adapter cancelled during setup'))
                raise
            tools = [ToolInfo(name=t['name'], description=t['description'],
                             parameters=ToolParams.model_validate(t['input_schema']))
                     for t in environment.competition.view('A')['tools']]
            await continue_participants(environment.competition, histories, model.generate, tools,
                                        GENERATE_CONFIG, response_received=live.response,
                                        observation_received=live.observation)
        finally:
            if hasattr(environment, 'competition'):
                await asyncio.to_thread(environment.close)
                state.metadata['hunt_evidence'] = environment.evidence()
            live.close()
            state.messages = histories['A']
            state.metadata['hunt_conversations'] = {
                a:[m.model_dump(mode='json') for m in messages] for a,messages in histories.items()}
            state.metadata['live_log_root'] = str(root)
        state.completed = True
        return state
    return solve


@scorer(metrics={'*':[mean(), stderr()]})
def independent_final_score(grading_seconds=GRADING_SECONDS, hunting_review=None, process_review=None):
    async def score(state, target):
        graded = await asyncio.to_thread(grade_episode, state.metadata['hunt_evidence']['protected'],
                                        seconds=grading_seconds, hunting_review=hunting_review, process_review=process_review)
        return Score(value=training_scores(graded), explanation=graded['reason'], metadata=graded)
    return score


@task
def mosslight(seconds=EPISODE_SECONDS, grading_seconds=GRADING_SECONDS, turns=TURNS,
              hunting_review=None, process_review=None):
    return Task(dataset=[Sample(input=prompt_for(), id='answer-hunt')],
                solver=hunt_solver(seconds, turns=turns),
                scorer=independent_final_score(grading_seconds, hunting_review, process_review))
