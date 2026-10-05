_observations = []
import json
import sqlite3
import tempfile
from pathlib import Path
from mosslight.workspace_catalog import WorkspaceCatalog

def legacy(path):
    db = sqlite3.connect(path)
    db.create_function('catalog_key', 1, lambda value: value.casefold(), deterministic=True)
    db.executescript('\n    CREATE TABLE catalog_format(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL);\n    INSERT INTO catalog_format VALUES(1,1);\n    CREATE TABLE catalog_receipts(id TEXT PRIMARY KEY,kind TEXT NOT NULL,label TEXT NOT NULL,locator TEXT NOT NULL,payload TEXT NOT NULL);\n    CREATE INDEX catalog_by_label ON catalog_receipts(catalog_key(label),kind);\n    ')
    data = [('old-garden', 'garden', 'Ｆｉｅｌｄ  pond', 'source:7', json.dumps({'seed': 7})), ('old-history', 'history', 'Field\xa0pond', 'publication:2', json.dumps({'heads': ['publication:2']})), ('ordinary', 'study', 'Control', 'study:0', json.dumps({'status': 'complete'}))]
    db.executemany('INSERT INTO catalog_receipts VALUES(?,?,?,?,?)', data)
    db.commit()
    db.close()
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'workspace.sqlite'
    legacy(path)
    old = WorkspaceCatalog(path)
    new = old.add('study', 'Field pond', {'status': 'complete', 'winner': 'shelter'})
    archive = old.export()
    _observations.append(len(archive['receipts']))
    fresh = WorkspaceCatalog(Path(tmp) / 'fresh.sqlite')
    fresh.import_parcel(archive)
    expected = {row['id'] for row in fresh.search('field pond')}
    observed = {row['id'] for row in old.search('field pond')}
    _observations.append(sorted([row['kind'] for row in old.search('field pond')]))
    _observations.append(len(old.search('FIELD POND', kind='history')))
    old.close()
    old = WorkspaceCatalog(path)
    _observations.append(sorted([row['kind'] for row in old.search('field pond')]))
    _observations.append(old.get('old-garden')['label'])
    old.close()
    fresh.close()
result = _observations
