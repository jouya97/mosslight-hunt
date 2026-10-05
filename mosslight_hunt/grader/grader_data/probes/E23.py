from mosslight.engine import create
from mosslight.nursery import _batch, advance_nursery
w = create(26, 4, 4)
b = _batch(w, 'moss', 1, 'seed')
w.workbench['nursery'][0]['hydration'] = 0
advance_nursery(w)
result = [w.workbench["nursery"][0][k] for k in ("age","vitality")]
