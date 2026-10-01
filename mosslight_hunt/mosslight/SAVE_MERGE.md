# Reconcile raw garden saves

Use save merge when two devices edit copies of a garden outside the event-history
workspace. Keep their actual common save, then supply both descendants with
distinct replica labels. Version 1 saves are supported. Input files stay untouched.

```sh
python3 -B -m mosslight.save_merge original.json desk.json field.json merged.json \
  --left-origin desk --right-origin field
```

The output is a reviewable JSON package. A `ready` package contains `world`, an
ordinary version 2 save, and a reproducibility receipt. Save the `world` object
separately to open it in the studio. `verify_receipt` checks the package against
the supplied originals; keep those originals with the result.

## What the merge preserves

Replica labels identify the two lines of work. Keep each label with its garden
when swapping inputs. The original must be their real common ancestor; a matching
seed or garden size alone is insufficient.

Existing records retain their identity. Independently created records stay
separate, even if the devices gave them the same number or text. The result uses
unique local identifiers, and its receipt records their correspondence to the
inputs. Saves must follow normal garden identity rules, including retaining the
meaning of an existing identifier.

Compatible notebook and planning edits combine. A field changed on only one side
keeps that change; equal edits agree. Different fields can be edited independently,
while list values such as tags are reviewed as a whole. A deletion opposed by an
edit requires a choice.

The living garden is kept as a coherent snapshot. Conflicting ecological changes
require choosing which complete snapshot to keep. Notebook and planning edits
can still be combined with that choice.

## Review a conflict

A `conflict` package records the alternatives and their JSON pointer paths. A
resolutions file maps paths to choices:

```json
{
  "/PATH_FROM_THE_CONFLICT_PACKAGE": {"choose": "left"}
}
```

Choices are `left`, `right` or `base`. Pass the file with
`--resolutions choices.json`. Resolutions must match the current conflicts.
Unresolved packages do not contain a usable output garden.

The combined result must also be a valid garden. If otherwise compatible edits
cannot coexist, an `incompatible` package explains the validation problem. Review
the inputs and merge again. The receipt establishes reproducibility from the
supplied files; it does not verify their external provenance.
