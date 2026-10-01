import math
import tempfile
from pathlib import Path
from mosslight.field_calibration import estimate, create_field_study
from mosslight.model import World, Cell
from mosslight.studies import StudyStore

def readings(origin):
    return [{'timestamp': origin + i, 'moisture': 40 + i*5} for i in range(3)]

# Same measurement window expressed with elapsed seconds vs common Unix seconds.
for origin in (0, 1750000000, 1750000000.25, -1750000000):
    value = estimate(readings(origin), origin+3)
    assert math.isclose(value, 55.0, abs_tol=1e-9), (origin, value)

# Downstream sources, cohort execution, stage continuation and reports remain
# invariant to timestamp origin; no other seed is needed for the numerical root.
with tempfile.TemporaryDirectory() as tmp:
    store = StudyStore(Path(tmp)/'study.sqlite')
    world = World(11,4,4,cells=[Cell(40,50,50) for _ in range(16)])
    reports=[]
    for origin in (0,1750000000):
        made = create_field_study(store, {'pond':world}, {'pond':readings(origin)}, origin+3,
            [{'name':'shade', 'events':[]}], [{'until':1,'keep':1},{'until':3,'keep':1}],metric='moisture')
        for _ in range(100):
            if store.work_once(made['study'],offsets=4) is None: break
        else: raise AssertionError('Study failed to complete')
        reports.append(store.checkpoint(made['study'],1,'pond','shade')['state']['world'])
    assert reports[0] == reports[1], 'Field timestamp origin altered a staged simulation'
    assert world.cells[0].moisture==40
    store.close()
