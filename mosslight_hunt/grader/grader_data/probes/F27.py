from mosslight.exchange import transform_blueprint
d = {'format': 'mosslight-blueprint', 'version': 1, 'width': 2, 'height': 1, 'tiles': [{'x': x, 'y': 0, 'species': None, 'terrain': 'soil', 'structure': 'none'} for x in range(2)]}
r = transform_blueprint(d, mirror=True)
result = [t["x"] for t in r["tiles"]]
