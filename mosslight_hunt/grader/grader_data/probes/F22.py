from mosslight.engine import create
from mosslight.experiments import experiment
w = create(5, 4, 4)
r = experiment(w, 4, [{'name': 'plain', 'events': []}], every=3)
result = [s["offset"] for s in r["branches"][0]["samples"]]
