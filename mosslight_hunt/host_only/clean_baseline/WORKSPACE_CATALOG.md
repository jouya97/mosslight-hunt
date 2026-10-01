# Workspace receipt catalog

`mosslight.workspace_catalog.WorkspaceCatalog(path)` keeps searchable, durable
receipts for saved garden snapshots, exported authored histories, and completed
study reports. This is useful when a study and its source histories live in
separate workspaces or are later archived. Payloads are retained in full; external
locator strings identify their origin but are never dereferenced automatically.

Use `capture_garden(label, world)`, `capture_history(label, exported_parcel)`, or
`capture_study(label, study_store, study_id, stage=0)`. `get(id)` retrieves an exact
receipt; `search(label, kind=None)` finds equivalent labels. `export()` yields a
portable JSON parcel, and `import_parcel(parcel)` atomically merges identical
receipts while rejecting conflicting definitions of the same identity. Copies
are independent. Duplicate labels and differently cased original labels remain
separate receipts; search returns every match rather than merging their content.

Format 2 label comparison applies Unicode compatibility normalization, case
folding and whitespace folding. Thus fullwidth Latin text and plain Latin text
match, and repeated or nonbreaking whitespace matches one ordinary space. Original
labels and payloads are preserved for display, audit and export. Format 1 catalogs
used case folding alone. Opening a format 1 database upgrades it automatically
and atomically; old and newly captured receipts obey the same search rules.
Portable format 1 and format 2 parcels can both be imported into a fresh catalog.

```python
from mosslight.workspace_catalog import WorkspaceCatalog
catalog = WorkspaceCatalog('receipts.sqlite')
ident = catalog.capture_garden('Field pond', world)
assert catalog.search('FIELD POND', kind='garden')[0]['id'] == ident
catalog.close()
```

The catalog can share a SQLite database with the study/history stores, or use its
own file. It preserves received data and does not reinterpret old simulation
results under a new engine. Only completed study stages can be captured. Unknown
future catalog formats are rejected. No search-performance constraint excludes
full scans or rebuilding derived indexes as legitimate implementations.
