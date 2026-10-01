"""Host-only response summaries and trajectories, flushed before tools execute."""
import json
import os
import time


def reasoning_summaries(message):
    content = message.content
    if isinstance(content, str):
        return []
    summaries = []
    for block in content:
        if getattr(block, 'type', None) != 'reasoning':
            continue
        summary = getattr(block, 'summary', None)
        if not summary and not getattr(block, 'redacted', False):
            summary = getattr(block, 'reasoning', None)
        if summary:
            summaries.append(summary)
    return summaries


class LiveLog:
    def __init__(self, folder):
        self.reasoning = (folder / 'reasoning.jsonl').open('x', encoding='utf8')
        self.trajectory = (folder / 'trajectory.jsonl').open('x', encoding='utf8')
        self.responses = 0

    def append(self, stream, record):
        stream.write(json.dumps(record, ensure_ascii=True, default=str) + '\n')
        stream.flush()
        os.fsync(stream.fileno())

    def response(self, identity, output, messages):
        self.responses += 1
        record = {'type':'model_response', 'actor':identity, 'response':self.responses,
                  'time':time.time(), 'message_index':len(messages)-1,
                  'summaries':reasoning_summaries(output.message)}
        self.append(self.reasoning, record)
        self.append(self.trajectory, {**record, 'provider_response':output.model_dump(mode='json')})
        # Keep provider summaries intact in JSONL; stdout gives a readable live view.
        print('REASONING', json.dumps(record, ensure_ascii=True, default=str), flush=True)

    def observation(self, identity, action, observation, messages):
        self.append(self.trajectory, {'type':'tool_result', 'actor':identity,
                    'response':self.responses, 'time':time.time(),
                    'action':action, 'observation':observation})

    def close(self):
        self.reasoning.close()
        self.trajectory.close()
