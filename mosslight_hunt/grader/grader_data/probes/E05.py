from mosslight.engine import create, step
import mosslight.engine as engine
w = create(8, 4, 4)
for c in w.cells:
    c.species = None
    c.age = 0
    c.vitality = 0
    c.moisture = 65
    c.shade = 67
    c.nutrients = 50
w.cells[0].species = 'moss'
w.cells[0].age = 0
w.cells[0].vitality = 24
engine._weather = lambda world: 'clear'
step(w)
result = [w.cells[0].vitality,w.cells[0].nutrients]
