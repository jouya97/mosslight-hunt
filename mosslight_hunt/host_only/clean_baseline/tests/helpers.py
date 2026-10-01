from mosslight.engine import create
from mosslight.model import Cell


def empty_world():
    world = create(7,4,4)
    world.cells = [Cell(50,50,50) for _ in range(16)]
    return world


def plant(world,x=0,y=0,species="moss",age=10,vitality=80):
    cell = world.cell(x,y)
    cell.species,cell.age,cell.vitality = species,age,vitality
    return cell
