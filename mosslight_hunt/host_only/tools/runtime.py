"""Fresh single-agent model/action loop with cancellation-safe container cleanup."""
import asyncio
import json

async def continue_participants(competition, histories, generate, tools, config, response_received=None, observation_received=None):
    """Dependency-injected model boundary allows offline end-to-end continuation tests."""
    from inspect_ai.model import ChatMessageTool
    from inspect_ai.tool import ToolCallError
    allowed = {t.name for t in tools}

    async def action(identity, value):
        operation = asyncio.create_task(asyncio.to_thread(competition.act, identity, value))
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            competition.stop(TimeoutError('continuation cancelled'))
            await asyncio.gather(operation, return_exceptions=True)
            raise

    async def participant(identity):
        messages = histories[identity]
        try:
            while not competition.view(identity)['terminal']:
                output = await asyncio.wait_for(generate(messages, tools=tools, tool_choice='auto', config=config),
                                                competition.remaining())
                messages.append(output.message)
                raw = output.model_dump(mode='json')
                competition.agents[identity].last_response = raw
                if response_received is not None:
                    response_received(identity, output, messages)
                transformations = ((raw.get('metadata') or {}).get('extra_body') or {}).get('input_transformations')
                if transformations:
                    competition.audit.append(dict(type='continuation_input_transformed', agent=identity,
                                                   transformations=transformations))
                    raise ValueError('Provider transformed restored input; stop to review continuation fidelity')
                calls = output.message.tool_calls or []
                error = ('Use exactly one action per response.' if len(calls) > 1 else
                         calls[0].parse_error if calls else None)
                if calls and (calls[0].type != 'function' or calls[0].function not in allowed):
                    error = 'Only declared function tools are available.'
                if error:
                    competition.reject_response(identity, raw, error)
                    for call in calls:
                        messages.append(ChatMessageTool(content=error, tool_call_id=call.id, function=call.function,
                            error=ToolCallError(type='parsing', message=error)))
                    value = dict(tool='invalid_response', arguments={})
                else:
                    value = dict(tool=calls[0].function, arguments=calls[0].arguments) if calls else None
                try:
                    observation = await action(identity, value)
                except InterruptedError:
                    ended = competition.ended_observation()
                    if ended is None:
                        raise
                    if calls and not error:
                        messages.append(ChatMessageTool(content=json.dumps(ended), tool_call_id=calls[0].id,
                                                        function=calls[0].function))
                    return
                if observation_received is not None:
                    observation_received(identity, value, observation, messages)
                if calls and not error and observation is not None:
                    messages.append(ChatMessageTool(content=json.dumps(observation), tool_call_id=calls[0].id,
                                                    function=calls[0].function))
                elif error and isinstance(observation, dict) and 'notice' in observation:
                    messages[-1] = messages[-1].model_copy(update={'content': f"{error}\n{observation['notice']}"})
        except BaseException as exc:
            competition.stop(TimeoutError('continuation cancelled') if isinstance(exc, asyncio.CancelledError) else exc)
            raise

    workers = [asyncio.create_task(participant(a)) for a in histories]
    try:
        _, pending = await asyncio.wait(workers, return_when=asyncio.FIRST_EXCEPTION)
        for worker in pending:
            worker.cancel()
        outcomes = await asyncio.gather(*workers, return_exceptions=True)
        failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
        if failures:
            # A cancelled earlier worker must not hide the worker that actually failed.
            raise next((error for error in failures
                        if not isinstance(error, (asyncio.CancelledError, InterruptedError))),
                       next((error for error in failures if not isinstance(error, asyncio.CancelledError)), failures[0]))
    finally:
        for worker in workers:
            if not worker.done():
                worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
