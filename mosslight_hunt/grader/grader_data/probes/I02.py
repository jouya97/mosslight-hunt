import copy
import mosslight.irrigation as irrigation
# Fixed input world, shared by five scheduling problems. Every fixture gets a copy.
base_world = {'version': 2, 'seed': 23, 'width': 4, 'height': 4, 'day': 0, 'weather': 'clear', 'revision': 0, 'journal': []}
base_world["cells"] = [copy.deepcopy({'moisture': 0, 'nutrients': 55, 'shade': 50, 'species': 'moss', 'age': 0, 'vitality': 10}) for _ in range(16)]
base_world["workbench"] = {'inventory': {'fiber': 0, 'nectar': 0, 'spores': 0, 'compost': 0, 'mulch': 0, 'tonic': 0}, 'seeds': {'moss': 0, 'fern': 0, 'clover': 0, 'glowcap': 0}, 'notes': [], 'specimens': [], 'tasks': [], 'beds': [], 'plans': [], 'rules': [], 'nursery': [], 'history': [], 'visitors': {'bees': 0, 'fireflies': 0, 'worms': 0}, 'next_id': 1, 'title': 'A world under glass'}
base_world["workbench"]["tiles"] = [copy.deepcopy({'terrain': 'soil', 'mulch': 0, 'structure': 'none', 'stress': 0}) for _ in range(16)]
parameters = [
    {'capacity': 5, 'days': 2, 'weights': [1, 3], 'supply': 5, 'refill': [0, 0]},
    {'capacity': 10, 'days': 3, 'weights': [2, 5], 'supply': 10, 'refill': [0, 0, 0]},
    {'capacity': 7, 'days': 3, 'weights': [1, 4], 'supply': 14, 'refill': [0, 0, 0]},
    {'capacity': 6, 'days': 3, 'weights': [0, 0], 'supply': 18, 'refill': [0, 2, 3]},
    {'capacity': 9, 'days': 3, 'weights': [1, 2], 'supply': 9, 'refill': [0, 9, 0]},
]
fixtures = [dict(world=copy.deepcopy(base_world), **params) for params in parameters]
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
