# Garden histories and corrections

A history keeps an imported garden and the commands authored from it. Use it
to revisit an observation, try an alternative care decision, or combine work
from related branches. Histories live in local SQLite files; exported gardens
use the ordinary version 2 save format.

```sh
python -m mosslight.history field.sqlite create examples/first-garden.json --label field
python -m mosslight.history field.sqlite append BRANCH command.json
python -m mosslight.history field.sqlite show BRANCH
python -m mosslight.history field.sqlite correct BRANCH corrections.json --label corrected
python -m mosslight.history field.sqlite export CORRECTED_BRANCH corrected-garden.json
```

`create` prints a branch identifier. `append` accepts ordinary command JSON and
returns an event identifier, revision, garden and object references. Use
`--revision REVISION` when an append should apply only to the revision you reviewed.
Earlier revisions remain available through `snapshot(branch, revision=...)`.
Forking and correcting create alternatives while preserving the original branch.

## Correcting an observation

A corrections file maps event IDs to replacement commands. Use `null` to remove
an event:

```json
{
  "EVENT_TO_REMOVE": null,
  "EVENT_TO_REVISE": {"op":"note","args":{"content":"Corrected observation"}}
}
```

A correction revises an authored action and its consequences. References in
later actions continue to identify the objects their authors selected, even
when a revised history assigns different local numbers. Replacing or deleting
an object does not turn an old reference into a reference to an unrelated one.
Numeric IDs in a replacement refer to the garden at that point in the history.

`references BRANCH` lists logical references, current local IDs and presence.
Commands that identify collection objects can also use an explicit reference:

```json
{"op":"edit_note","args":{"ident":{"$ref":"event:EVENT_ID:notes"},"content":"Revised observation"}}
```

If a revised history can no longer perform an action, the branch is marked
`conflicted` and identifies the event and reason. Its garden shows progress up
to the conflict. The remaining actions are retained for review. Correct or remove
the conflicting action before appending or exporting a complete garden.

## Combining related work

```sh
python -m mosslight.history field.sqlite fork BRANCH --label trial
python -m mosslight.history field.sqlite pick TARGET SOURCE EVENT_ONE EVENT_TWO --label combined
python -m mosslight.history field.sqlite rebase CHILD UPDATED_PARENT --label rebased
```

Cherry-pick carries selected actions into another branch. A shared action is
included once; independently authored actions remain distinct. Actions that use
an object need that object to exist in the resulting history.

Rebase updates an alternative using a related branch while retaining its local
changes. Compatible edits combine. Conflicting changes or incompatible action
orders require review; rebase does not silently choose which author's work to
lose. Action order matters for care decisions, and shared actions retain their
identity across branches. The result records the revisions used so it remains
understandable after the source branches change.

Cherry-pick and rebase require histories from the same imported root. Importing
the same save twice creates separate histories.

## Python and stored results

`HistoryStore(path)` provides `create`, `append`, `fork`, `correct`, `cherry_pick`,
`rebase`, `snapshot`, `references`, `verify` and `close`. Returned snapshots are
independent data. Use a separate connection for each worker. Concurrent work
must preserve successful edits and report changes that need to be retried.
`HistoryConflict.details` supplies structured errors; the CLI writes errors as
JSON to stderr and exits with status 2.

`verify BRANCH` checks the stored result against its recorded history. Saved
snapshots remain readable without their interpreter, but replay and editing
require the recorded release. A history is not automatically reinterpreted
under a newer release.
