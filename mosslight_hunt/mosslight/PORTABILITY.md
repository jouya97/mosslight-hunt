# Saving and sharing garden work

A JSON save carries a complete portable garden. Survey CSV, blueprints, notebook
Markdown and SVG exports support other ways to measure, reuse and share your
work. Successful edits can be saved from the CLI or autosaved in the studio;
failed edits preserve the previous garden.

## Saves and revisions

Mosslight reads save versions 1 and 2 and writes version 2. Older gardens gain
neutral workbench defaults while retaining their original garden. Saves are
validated when loaded, and unsupported versions or inconsistent data are
rejected. Portable state includes the garden and notebook; server undo history
belongs to the current studio session.

Python's `to_dict` returns an independently editable save representation. Use it
to prepare a separate garden or archive a point in time without changing the
original through later edits to that data.

A JSON command uses `op` and `args`. It succeeds as one edit or leaves the garden
unchanged. A replay applies a sequence of up to 1,000 commands as one publishable
workflow, preserving each command's normal revision behavior. If the sequence
fails, its partial work does not replace the source.

```sh
python3 -B -m mosslight replay garden.json examples/hollow-actions.json
python3 -B -m mosslight export garden.json markdown -o notebook.md
```

CLI errors go to stderr with exit code 2. Successful mutation commands save the
result. A forecast requires a different output path from its source.

## A complete tile survey

Use CSV to carry tile measurements between tools:

```sh
python3 -B -m mosslight export garden.json csv -o survey.csv
```

The format has this header and one row per tile, with an empty species field for
bare ground:

```csv
x,y,species,age,vitality,moisture,nutrients,shade,terrain,mulch,structure,stress
```

Import requires every coordinate exactly once, the exported columns and valid
model values. It replaces tile data while retaining the notebook and planning
work. A rejected survey leaves the garden unchanged. Pass the CSV text as an
`import_csv` command's `content`; see [command recipes](COMMANDS.md#designs-and-measurements).

## Reusing a planting design

A blueprint records a rectangle of terrain, structures and species using local
coordinates. It leaves behind soil measurements and individual plant history,
so a design can start afresh in another garden.

```sh
python3 -B -m mosslight blueprint garden.json --rect 0 0 3 2 --turns 1 -o pattern.json
```

Either corner order selects the same rectangle. Transformations support a
horizontal mirror followed by zero through three clockwise quarter turns.
Placement must fit the destination. Existing plants require explicit overwrite;
an invalid placement leaves the whole destination intact. New plants use ordinary
planting values. The [Python recipe](COMMANDS.md#designs-and-measurements) shows how
to load, transform and place a blueprint.

## Archiving the notebook and artwork

Markdown export records note text, dates, locations, tags, task completion and
specimen labels. SVG illustrations and maps are standalone artwork; the
[field guide](FIELD_GUIDE.md#maps-illustrations-and-history-prints) explains their
scales and accessibility. Authored content stays text in the studio and exports.

For exchanges that retain separate editing histories and conflicting
observations, see [field courier](COURIER.md), [save reconciliation](SAVE_MERGE.md)
and [history exchange](HISTORY_EXCHANGE.md).

## Editing in the studio

Revision checks help multiple browser tabs avoid overwriting each other's work.
A mutation can include the revision it was based on; a stale revision receives
HTTP 409 so the caller can refresh before trying again. The browser supplies
revisions for normal edits and imports. Legacy imports without a revision remain
supported and retain the imported save's revision.

Successful edits are saved before becoming available as the current garden.
A save failure preserves the previous garden and undo history. Undo and redo
restore prior garden contents as fresh revisions. The session keeps 30 prior
edits; a new edit after undo starts a new branch, and restarting clears the
session history. Reading reports or exploring futures creates no undo entries.
See [API interfaces](DESIGN.md#interfaces) for routes and response conventions.
