_observations = []
"""Observed reverts survive two independent reconciliations of the same heads.

Each database receives complete parcels. The disposable replay cache is cleared
before a correction to isolate this publication-ancestry oracle from H01.
"""
from pathlib import Path
import tempfile
from mosslight.history_exchange import HistoryExchange
from mosslight.model import Cell, World

def note(text):
    return {'op': 'note', 'args': {'content': text}}
with tempfile.TemporaryDirectory() as directory:
    devices = [HistoryExchange(Path(directory) / (name + '.sqlite')) for name in ('desk', 'field', 'archive')]
    (desk, field, archive) = devices
    try:
        initial = desk.history.create(World(7, 4, 4, cells=[Cell(0, 50, 50) for _ in range(16)]))
        desk.history.append(initial['branch'], note('A0'))
        current = desk.history.append(initial['branch'], note('B0'))
        (a, b) = [event['id'] for event in current['events']]
        start = desk.announce(initial['branch'], author='desk')
        (channel, genesis) = (start['channel'], start['publication'])
        field.receive(desk.export(channel))

        def change(device, publication, event, text):
            checkout = device.checkout(publication)
            device.db.execute('DELETE FROM history_checkpoints')
            corrected = device.history.correct(checkout['branch'], {event: note(text)})
            return device.publish(corrected['branch'], checkout=checkout['branch'], author='gardener')
        left = change(desk, genesis, a, 'A1')
        right = change(field, genesis, b, 'B1')
        (left_parcel, right_parcel) = (desk.export(channel), field.export(channel))
        desk.receive(right_parcel)
        field.receive(left_parcel)
        one = desk.reconcile(left['publication'], right['publication'], author='desk')
        two = field.reconcile(left['publication'], right['publication'], author='field')
        _observations.append(len({one['publication'], two['publication']}))
        _observations.append(len({one['revision'], two['revision']}))
        undone_a = change(desk, one['publication'], a, 'A0')
        undone_b = change(field, two['publication'], b, 'B0')
        archive.receive(desk.export(channel))
        archive.receive(field.export(channel))
        result = archive.reconcile(undone_a['publication'], undone_b['publication'], author='archive')
        snapshot = archive.history.snapshot(result['branch'])
        texts = [item['text'] for item in snapshot['world']['workbench']['notes']]
        _observations.append(texts)
    finally:
        for device in devices:
            device.close()
result = _observations
