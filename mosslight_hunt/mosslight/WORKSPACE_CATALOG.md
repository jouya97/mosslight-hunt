# Workspace receipt catalog

Keep a searchable collection of saved gardens, authored histories and completed
study reports with `WorkspaceCatalog`. The catalog stores a full copy of each
receipt, which is useful when the original work lives in a different workspace
or has been archived. A receipt's locator records where it came from; opening a
receipt does not fetch that external location.

```python
from mosslight.workspace_catalog import WorkspaceCatalog

catalog = WorkspaceCatalog('receipts.sqlite')
try:
    ident = catalog.capture_garden('Field pond', world)
    saved = catalog.get(ident)
    for match in catalog.search('Field pond', kind='garden'):
        print(match['label'], match['id'])
finally:
    catalog.close()
```

Use `capture_garden(label, world)` for a garden,
`capture_history(label, exported_parcel)` for an exported history, or
`capture_study(label, study_store, study_id, stage=0)` for a completed study stage.
`get(id)` retrieves a receipt by its identifier. Labels need not be unique;
searching returns matching receipts without combining their contents.

Search tolerates differences in capitalization, spacing and compatible character
forms such as fullwidth letters. Stored labels keep their original spelling for
display and export. The optional `kind` filter accepts `garden`, `history` or
`study`.

To move a collection, save the JSON parcel returned by `export()` and pass it to
another catalog's `import_parcel(parcel)`. Import accepts parcels from formats 1
and 2. Receipts already present with identical content are accepted; conflicting
definitions of the same receipt ID reject the import. Keep the receipt IDs when
moving a collection between machines.

The catalog may use its own SQLite file or share one with the study and history
stores. Older format 1 catalogs are upgraded when opened. Future formats that
this release cannot read are rejected. Historical payloads remain as captured;
the catalog does not rerun old simulations under a different engine.
