from mosslight.irrigation_flow import allocate
from mosslight.irrigation import definition,solve,replay
from mosslight.model import World,Cell

pipes=[{'from':'tank','to':'upper','capacity':16},
       {'from':'upper','to':'cross','capacity':16},
       {'from':'cross','to':'bed','capacity':16},
       {'from':'tank','to':'cross','capacity':16},
       {'from':'upper','to':'bed','capacity':16}]
# Independent max-flow/min-cut oracle, including tank supply and outlet demand.
# This does not duplicate the implementation's augmenting-path procedure.
import itertools
nodes=['tank','upper','cross','bed']
cut=min(sum(p['capacity'] for p in pipes if p['from'] in group and p['to'] not in group)
        for bits in itertools.product([False,True],repeat=2)
        for group in [{'tank',*(n for n,keep in zip(['upper','cross'],bits) if keep)}])
assert cut==32
result=allocate(pipes,'tank',{'bed':32},32)
assert result['total']==min(cut,32), 'A feasible part of the watering budget was stranded'
for node in ['upper','cross']:
 incoming=sum(flow for pipe,flow in zip(pipes,result['pipes']) if pipe['to']==node)
 outgoing=sum(flow for pipe,flow in zip(pipes,result['pipes']) if pipe['from']==node)
 assert incoming==outgoing
assert all(0<=flow<=pipe['capacity'] for pipe,flow in zip(pipes,result['pipes']))
world=World(23,4,4,cells=[Cell(18,55,60,'moss',4,45) for _ in range(16)])
layout={'source':'tank','pipes':pipes,'outlets':{'bed':{'demand':32,'tiles':[[1,1]]}}}
problem=definition(world,layout,[{'name':'shelter','open':['bed']}],3,96)
report=solve(problem)
assert [day['delivery']['total'] for day in report['trace']]==[32,32,32]
assert report['world']==replay(problem,report['schedule'])['world']
assert world.cells[5].moisture==18
