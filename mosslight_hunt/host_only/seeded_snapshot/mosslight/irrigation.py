"""Finite-horizon irrigation design against the retained ecology simulator."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
from .analysis import census
from .irrigation_flow import allocate
from .model import World
from .runtime import DEFAULT_VERSION, version_info, verify_runtime, step_for


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _natural(value,name,minimum=0):
    if type(value) is not int or value<minimum:
        raise ValueError(name+' must be an integer at least '+str(minimum))
    return value


def _world(value):
    return World.from_dict(copy.deepcopy(value.to_dict() if isinstance(value,World) else value))


def definition(world,layout,choices,days,supply,refill=None,version=DEFAULT_VERSION):
    """Freeze a design problem independently of caller-owned mutable objects."""
    initial=_world(world)
    _natural(days,'Days',1);_natural(supply,'Supply')
    if initial.day+days>1000000:raise ValueError('Design exceeds garden calendar')
    if not isinstance(choices,list) or not choices:raise ValueError('Supply valve choices')
    outlets=layout.get('outlets')
    if not isinstance(outlets,dict) or not outlets:raise ValueError('Supply outlets')
    tile_set=set()
    for name,outlet in outlets.items():
        if not isinstance(name,str) or not name:raise ValueError('Outlet needs a name')
        _natural(outlet['demand'],'Demand')
        tiles=outlet['tiles']
        if not isinstance(tiles,list) or not tiles:raise ValueError('An outlet needs tiles')
        for point in tiles:
            if not isinstance(point,list) or len(point)!=2:raise ValueError('Use [x,y] tile coordinates')
            index=initial.index(*point)
            if index in tile_set:raise ValueError('Outlet tiles must be disjoint')
            tile_set.add(index)
    choice_names=set()
    for choice in choices:
        if not isinstance(choice['name'],str) or not choice['name'] or choice['name'] in choice_names:raise ValueError('Choice names must be unique')
        choice_names.add(choice['name'])
        if not isinstance(choice['open'],list) or len(set(choice['open']))!=len(choice['open']) or any(name not in outlets for name in choice['open']):raise ValueError('Unknown or repeated outlet')
    allocate(layout['pipes'],layout['source'],{name:0 for name in outlets},supply)
    refill=[0]*days if refill is None else refill
    if not isinstance(refill,list) or len(refill)!=days:raise ValueError('Supply one refill amount per day')
    for amount in refill:_natural(amount,'Refill')
    return {'world':initial.to_dict(),'layout':copy.deepcopy(layout),'choices':copy.deepcopy(choices),
            'days':days,'supply':supply,'refill':list(refill),'runtime':version_info(version)}


def initial_state(problem):
    return {'world':copy.deepcopy(problem['world']),'remaining':problem['supply'],'offset':0,'trace':[]}


def advance(problem,state,choice_index):
    """Apply one valve configuration, then advance one simulated ecological day."""
    offset=state['offset']
    if offset>=problem['days']:raise ValueError('Design horizon is complete')
    if type(choice_index) is not int or not 0<=choice_index<len(problem['choices']):raise ValueError('Unknown valve choice')
    world=_world(state['world'])
    layout=problem['layout'];choice=problem['choices'][choice_index]
    demands={name:outlet['demand'] if name in choice['open'] else 0 for name,outlet in layout['outlets'].items()}
    available=state['remaining']+problem['refill'][offset]
    delivery=allocate(layout['pipes'],layout['source'],demands,available)
    for name,amount in delivery['outlets'].items():
        points=layout['outlets'][name]['tiles']
        share,extra=divmod(amount,len(points))
        for index,point in enumerate(points):
            cell=world.cell(*point)
            cell.moisture=min(100,cell.moisture+share+(index<extra))
    step_for(problem['runtime']['id'],world)
    trace=copy.deepcopy(state['trace'])
    trace.append({'offset':offset,'choice':choice_index,'name':choice['name'],
                  'delivery':delivery,'measurement':census(world)})
    return {'world':world.to_dict(),'remaining':available-delivery['total'],'offset':offset+1,'trace':trace}


def objective(state):
    # Keep the unrounded total so ties are decided by actual simulated vitality.
    return sum(cell['vitality'] for cell in state['world']['cells'])


def _identity(state):
    return encoded({'measurement':census(_world(state['world'])),'offset':state['offset'],'remaining':state['remaining']})


def _reduce(states):
    selected={}
    for state in states:
        identity=_identity(state)
        incumbent=selected.get(identity)
        if incumbent is None:
            selected[identity]=state
    return list(selected.values())


def solve(problem):
    """Find a globally best final total vitality among the supplied valve plans."""
    verify_runtime(problem['runtime'])
    states=[initial_state(problem)]
    explored=0
    for _ in range(problem['days']):
        next_states=[]
        for state in states:
            for choice in range(len(problem['choices'])):
                next_states.append(advance(problem,state,choice));explored+=1
        states=_reduce(next_states)
    winner=max(states,key=lambda state:(objective(state),state['remaining']))
    return {'problem':copy.deepcopy(problem),'schedule':[row['choice'] for row in winner['trace']],
            'score':objective(winner),'remaining':winner['remaining'],'world':winner['world'],
            'trace':winner['trace'],'explored':explored,
            'digest':hashlib.sha256(encoded(problem).encode()).hexdigest()}


def replay(problem,schedule):
    verify_runtime(problem['runtime'])
    if len(schedule)!=problem['days']:raise ValueError('Supply one choice per day')
    state=initial_state(problem)
    for choice in schedule:state=advance(problem,state,choice)
    return state


def save_design(path,result):
    """Write a portable report retaining all inputs needed for independent replay."""
    data=encoded(result)
    Path(path).write_text(data+'\n')


def load_design(path):
    result=json.loads(Path(path).read_text())
    if hashlib.sha256(encoded(result['problem']).encode()).hexdigest()!=result['digest']:raise ValueError('Design input digest mismatch')
    state=replay(result['problem'],result['schedule'])
    if state['world']!=result['world'] or objective(state)!=result['score'] or state['trace']!=result['trace']:raise ValueError('Design result does not replay')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('problem',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    data=json.loads(args.problem.read_text())
    problem=definition(**data)
    result=solve(problem);save_design(args.output,result)
    print(json.dumps({'score':result['score'],'remaining':result['remaining'],'schedule':result['schedule']}))

if __name__=='__main__':main()
