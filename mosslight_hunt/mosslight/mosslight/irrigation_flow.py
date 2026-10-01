"""Integral capacity allocation for local irrigation layouts."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Arc:
    end: str
    reverse: int
    capacity: int
    pipe: int | None


def allocate(pipes, source, outlets, supply):
    if not isinstance(source, str) or not source:
        raise ValueError('Supply junction must have a name')
    if type(supply) is not int or supply < 0:
        raise ValueError('Supply must be a nonnegative integer')
    if not isinstance(pipes,list) or not isinstance(outlets,dict):
        raise ValueError('Supply a pipe list and outlet mapping')
    graph={}
    positions=[]
    def add(start,end,capacity,pipe):
        graph.setdefault(start,[]);graph.setdefault(end,[])
        left,right=len(graph[start]),len(graph[end])
        graph[start].append(Arc(end,right,capacity,pipe))
        graph[end].append(Arc(start,left,0,None))
        return start,left
    names={source,*outlets}
    for index,pipe in enumerate(pipes):
        start,end,capacity=pipe['from'],pipe['to'],pipe['capacity']
        if not isinstance(start,str) or not isinstance(end,str) or not start or not end or start==end:
            raise ValueError('Pipes need distinct named junctions')
        if type(capacity) is not int or capacity < 0:
            raise ValueError('Pipe capacity must be a nonnegative integer')
        names.update((start,end))
        positions.append(add(start,end,capacity,index))
    for name,demand in outlets.items():
        if not isinstance(name,str) or not name or name==source or type(demand) is not int or demand<0:
            raise ValueError('Invalid outlet demand')
    inlet='@supply';sink='@delivery'
    while inlet in names:inlet+='@'
    while sink in names or sink==inlet:sink+='@'
    add(inlet,source,supply,-1)
    outlet_positions={name:add(name,sink,demand,-1) for name,demand in outlets.items()}

    def route(node,amount,seen):
        if node==sink:return amount
        seen.add(node)
        for edge in graph.get(node,[]):
            if edge.capacity <= 0 or edge.end in seen or edge.pipe is None:
                continue
            sent=route(edge.end,min(amount,edge.capacity),seen)
            if sent:
                edge.capacity-=sent
                graph[edge.end][edge.reverse].capacity+=sent
                return sent
        return 0

    delivered=0
    while supply>delivered:
        sent=route(inlet,supply-delivered,set())
        if not sent:break
        delivered+=sent
    flows=[pipe['capacity']-graph[start][index].capacity for pipe,(start,index) in zip(pipes,positions)]
    doses={name:outlets[name]-graph[start][index].capacity for name,(start,index) in outlet_positions.items()}
    return {'total':delivered,'outlets':doses,'pipes':flows}
