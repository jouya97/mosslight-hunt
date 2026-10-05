from mosslight.experiments import rank_experiment
r = {'branches': [{'name': 'zeta', 'final': {'coverage': 50}}, {'name': 'alpha', 'final': {'coverage': 50}}]}
result = [x["name"] for x in rank_experiment(r)]
