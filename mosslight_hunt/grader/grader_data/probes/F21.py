from mosslight.engine import create
import mosslight.experiments as experiments
calls=[]
execute=experiments.execute
def observe(world,command):
    calls.append([world.day,command["args"]["x"]])
    return execute(world,command)
experiments.execute=observe
w=create(4,4,4)
events=[{"offset":offset,"command":{"op":"tend","args":{"x":x,"y":0,"action":"water"}}} for offset,x in [(0,0),(1,1),(3,2)]]
experiments.experiment(w,3,[{"name":"scheduled water","events":events}])
result=calls
