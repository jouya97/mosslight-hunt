"""Rebuild the host's exhaustive I02 table for a controlled ecology dependency.

The solver remains candidate code. A deterministic spatial growth fixture makes
state aliasing reproducible independently of the 30 seeded ecology defects.
The host reference enumerates choices and directly calculates watering/growth;
it never imports Mosslight or uses solve, replay, advance, census or _identity.
"""
import copy
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build():
    # This inert world serialization is test input; no reference code is imported.
    fixture_source = ROOT / 'host_only/checks/I02.py'
    import ast
    module = ast.parse(fixture_source.read_text())
    original = next(ast.literal_eval(node.value) for node in module.body
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FIXTURES' for t in node.targets))
    base = copy.deepcopy(original[0]['world'])
    for cell in base['cells']:
        cell.update(moisture=0, nutrients=55, shade=50, species='moss', age=0, vitality=10)
    fixtures = []
    for capacity, days, weights, supply, refill in (
            (5, 2, [1, 3], 5, [0, 0]),
            (10, 3, [2, 5], 10, [0, 0, 0]),
            (7, 3, [1, 4], 14, [0, 0, 0]),
            (6, 3, [0, 0], 18, [0, 2, 3]),
            (9, 3, [1, 2], 9, [0, 9, 0])):
        fixtures.append({'world': copy.deepcopy(base), 'capacity': capacity, 'days': days,
                         'weights': weights, 'supply': supply, 'refill': refill})
    expected = []
    for fixture in fixtures:
        schedules = {}
        for schedule in itertools.product(range(3), repeat=fixture['days']):
            world = copy.deepcopy(fixture['world'])
            remaining = fixture['supply']
            for day, choice in enumerate(schedule):
                remaining += fixture['refill'][day]
                if choice < 2:
                    amount = min(fixture['capacity'], remaining)
                    remaining -= amount
                    world['cells'][choice]['moisture'] = min(100, world['cells'][choice]['moisture'] + amount)
                world['day'] += 1
                for index, cell in enumerate(world['cells']):
                    cell['age'] += int(cell['moisture'] > 0)
                    if index < 2:
                        cell['vitality'] = min(100, cell['vitality'] + fixture['weights'][index] * max(0, cell['age']-1) * cell['moisture'] // 5)
            schedules[','.join(map(str, schedule))] = {'score': sum(cell['vitality'] for cell in world['cells']),
                                                       'remaining': remaining, 'world': world}
        expected.append({'best': max([state['score'], state['remaining']] for state in schedules.values()), 'schedules': schedules})
    program = '''import copy
import mosslight.irrigation as irrigation
fixtures = FIXTURES
result = []
for fixture in fixtures:
    weights = fixture['weights']
    def fixture_growth(version, world):
        world.day += 1
        for index, cell in enumerate(world.cells):
            cell.age += int(cell.moisture > 0)
            if index < 2:
                cell.vitality = min(100, cell.vitality + weights[index] * max(0, cell.age-1) * cell.moisture // 5)
    irrigation.step_for = fixture_growth
    capacity = fixture['capacity']
    layout = {'source':'tank', 'pipes':[{'from':'tank','to':name,'capacity':capacity} for name in ('left','right')],
              'outlets':{'left':{'demand':capacity,'tiles':[[0,0]]},'right':{'demand':capacity,'tiles':[[1,0]]}}}
    choices = [{'name':'left','open':['left']},{'name':'right','open':['right']},{'name':'closed','open':[]}]
    problem = irrigation.definition(copy.deepcopy(fixture['world']), layout, choices, fixture['days'], fixture['supply'], fixture['refill'])
    report = irrigation.solve(problem)
    result.append({key:report[key] for key in ('schedule','score','remaining','world')})
'''.replace('FIXTURES', repr(fixtures))
    output = ROOT / 'grader/grader_data/probes_irrigation.json'
    output.write_text(json.dumps([{'id':'I02', 'program':program, 'comparator':'irrigation_optimum', 'expected':expected}], indent=2)+'\n')
    print('I02:', len(fixtures), 'problems;', sum(len(case['schedules']) for case in expected), 'exhaustive schedules')


if __name__ == '__main__':
    build()
