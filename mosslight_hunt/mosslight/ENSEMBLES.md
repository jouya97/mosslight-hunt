# Editable experiment ensembles

An ensemble compares care treatments with untreated controls across 1–64 saved
gardens. Use it to compare watering schedules, for example, across gardens with
different sizes or starting days. Named plans can be shared across treatments.
Editing a plan updates the comparison while retaining past published reports.

Ensembles accept 1–8 treatments, a 1–120 day horizon, and at most 100 events per
trial. `examples/ensemble.json` is a runnable example with two saved gardens.

```sh
python3 -B -m mosslight.ensembles workspace.sqlite create examples/ensemble.json
python3 -B -m mosslight.ensembles workspace.sqlite work ENSEMBLE_ID --steps 20
python3 -B -m mosslight.ensembles workspace.sqlite status ENSEMBLE_ID
python3 -B -m mosslight.ensembles workspace.sqlite report ENSEMBLE_ID
```

Repeat bounded `work` invocations to finish. Separate processes use separate
store connections. Work can resume after interruption. `work --no-cache` runs
pending simulations afresh; reuse of earlier computation must preserve results.

## Plans and routes

Creation JSON contains `sources` (labels mapped to full garden saves), `days`,
`every`, `plans`, `routes`, `treatments` and `version`. A route chooses a plan for
each source. For example, these entries choose watering for initially dry gardens:

```json
{
  "plans": {
    "observe": {"events": []},
    "water": {"events": [{"offset": 0,
      "command": {"op": "tend", "args": {"x": 0, "y": 0, "action": "water"}}}]}
  },
  "routes": {
    "dry gardens": {"plan": "observe",
      "when": {"metric": "moisture", "below": 45, "plan": "water"}}
  },
  "treatments": [{"name": "Targeted watering", "route": "dry gardens"}]
}
```

Conditions use the initial source census and support coverage, richness,
diversity, vitality, moisture, nutrients and shade. A garden below the threshold
uses the conditional plan; otherwise it uses the primary plan. Events and
samples follow ordinary experiment schedules, including initial and final
samples. A failed trial is reported by name while other trials continue.

## Edit and compare revisions

`inputs` returns editable keys such as `plan:water`, `source:north bed` and
`route:dry gardens`. Save replacements in a JSON object keyed by those names:

```sh
python3 -B -m mosslight.ensembles workspace.sqlite edit ENSEMBLE_ID changes.json --expected-revision 0
python3 -B -m mosslight.ensembles workspace.sqlite report ENSEMBLE_ID --revision 0
```

An edit batch creates one revision unless all supplied values are unchanged.
The optional expected revision protects against overwriting intervening edits.
Input names, source and treatment membership, release and horizon are fixed for
the workspace; create another ensemble to change them. Source files stay untouched.

Each published report belongs to one input revision and remains available after
later edits and restarts. The current report becomes available when its trials
have succeeded or failed. A superseded, unfinished revision has no published
report, but `replay ID --revision N` can recompute its retained inputs. Working
and editing concurrently must produce reports consistent with their named inputs.

Reports include outcomes, selected plans and provenance for reviewing how results
were obtained. Source labels identify distinct comparison members even when two
sources contain equal saves. Treatment curves compare each garden with its own
control using elapsed experiment offsets. Averages describe the paired changes
across complete pairs, with excluded sources listed. They imply no confidence
interval or assumption of statistical independence.
