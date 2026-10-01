"""Durable searchable receipts for saved gardens, histories, and study reports."""
from __future__ import annotations
import copy
import json
import sqlite3
import unicodedata
import uuid

CURRENT_FORMAT = 2


def _normalizer(version):
    if version == 1:
        return lambda value: value.casefold()
    return lambda value: ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


class WorkspaceCatalog:
    """Catalog receipts own their payloads; external locators remain informative."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS catalog_format (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS catalog_receipts (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL,
                locator TEXT NOT NULL, payload TEXT NOT NULL);
        ''')
        stored = self.db.execute('SELECT version FROM catalog_format WHERE singleton=1').fetchone()
        version = stored[0] if stored else CURRENT_FORMAT
        if version not in (1, CURRENT_FORMAT):
            self.close()
            raise ValueError('Unsupported workspace catalog format')
        self._install_key(version)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute('CREATE INDEX IF NOT EXISTS catalog_by_label ON catalog_receipts(catalog_key(label),kind)')
            if version != CURRENT_FORMAT:
                self._upgrade_keys()
            self.db.execute('INSERT OR REPLACE INTO catalog_format VALUES(1,?)', (CURRENT_FORMAT,))

    def _install_key(self, version):
        self.db.create_function('catalog_key', 1, _normalizer(version), deterministic=True)

    def _upgrade_keys(self):
        self.db.execute('REINDEX catalog_by_label')
        self._install_key(CURRENT_FORMAT)

    def close(self):
        self.db.close()

    def add(self, kind, label, payload, locator=''):
        if kind not in ('garden','history','study'):
            raise ValueError('Unknown catalog kind')
        if not isinstance(label,str) or not label.strip() or not isinstance(locator,str):
            raise ValueError('Supply a nonempty label and a locator string')
        encoded = json.dumps(payload,allow_nan=False,sort_keys=True,separators=(',',':'))
        ident=uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO catalog_receipts VALUES(?,?,?,?,?)',(ident,kind,label,locator,encoded))
        return ident

    def capture_garden(self, label, world, locator=''):
        return self.add('garden',label,world.to_dict(),locator)

    def capture_study(self, label, store, study, stage=0):
        return self.add('study',label,store.report(study,stage),f'{study}:{stage}')

    def capture_history(self, label, parcel, locator=''):
        # Preserve the complete exported parcel, including original publications.
        return self.add('history',label,copy.deepcopy(parcel),locator)

    def get(self, ident):
        row=self.db.execute('SELECT id,kind,label,locator,payload FROM catalog_receipts WHERE id=?',(ident,)).fetchone()
        return self._receipt(row) if row else None

    @staticmethod
    def _receipt(row):
        return dict(zip(('id','kind','label','locator','payload'),(*row[:4],json.loads(row[4]))))

    def search(self, label, kind=None):
        if kind is not None and kind not in ('garden','history','study'):
            raise ValueError('Unknown catalog kind')
        query='SELECT id,kind,label,locator,payload FROM catalog_receipts WHERE catalog_key(label)=catalog_key(?)'
        args=[label]
        if kind is not None:
            query+=' AND kind=?';args.append(kind)
        return [self._receipt(row) for row in self.db.execute(query+' ORDER BY id',args)]

    def export(self):
        return {'format':CURRENT_FORMAT,'receipts':[self._receipt(row) for row in self.db.execute('SELECT id,kind,label,locator,payload FROM catalog_receipts ORDER BY id')]}

    def import_parcel(self, parcel):
        # Exported JSON carries original labels and payloads, not physical indexes.
        if parcel.get('format') not in (1,CURRENT_FORMAT) or not isinstance(parcel.get('receipts'),list):
            raise ValueError('Unsupported catalog parcel')
        with self.db:
            for item in parcel['receipts']:
                if item['kind'] not in ('garden','history','study') or not isinstance(item['label'],str) or not item['label'].strip():
                    raise ValueError('Invalid receipt')
                encoded=json.dumps(item['payload'],allow_nan=False,sort_keys=True,separators=(',',':'))
                data=(item['id'],item['kind'],item['label'],item['locator'],encoded)
                existing=self.db.execute('SELECT id,kind,label,locator,payload FROM catalog_receipts WHERE id=?',(item['id'],)).fetchone()
                if existing is not None and existing != data:
                    raise ValueError('Conflicting receipt identity')
                self.db.execute('INSERT OR IGNORE INTO catalog_receipts VALUES(?,?,?,?,?)',data)
