# Calibrating study cohorts from field observations

Use field moisture readings to prepare gardens for a staged treatment study.
Mosslight estimates moisture at your chosen starting time from a local linear
least-squares trend, then initializes each garden's cells with that estimate. Choose a short
observation window appropriate for your experiment; this feature does not model
seasonality or judge whether extrapolation is appropriate.

`create_field_study(store, worlds, observations, at, treatments, stages, **options)`
creates a study in an ordinary `StudyStore`. The garden labels in `observations`
must match those in `worlds`. Supply a nonempty list of readings for each garden;
each reading contains a numeric `timestamp` in seconds and a `moisture` percentage
between 0 and 100. Use the same clock for the readings and target `at` time.
Timestamps may include fractional seconds or dates before the clock's origin.

The result contains `study`, the new study ID, and `calibration`, a receipt with
your readings, target time and estimated moisture for each garden. Save this
receipt alongside the study report to record how its initial conditions were
chosen. Source gardens are copied, so they remain available for other studies.

For example, given a source `world` and a treatment definition `treatments`:

```python
from mosslight.field_calibration import create_field_study
from mosslight.studies import StudyStore

store = StudyStore('field-study.sqlite')
try:
    receipt = create_field_study(
        store,
        {'pond': world},
        {'pond': [
            {'timestamp': 0, 'moisture': 42},
            {'timestamp': 60, 'moisture': 44},
            {'timestamp': 120, 'moisture': 43},
        ]},
        120,
        treatments,
        [{'until': 5, 'keep': 1}],
        metric='moisture',
    )
    print(receipt['study'])
finally:
    store.close()
```

For a preview, `estimate(readings, at)` returns a moisture percentage limited to
the 0–100 range. When observations share a timestamp, their average is used.
`calibrated_sources(worlds, observations, at)` returns prepared gardens and a
calibration receipt without creating a study. Prepared cells use whole percentage
points, while the receipt keeps the estimates before rounding.

See [Staged treatment studies](STUDIES.md) for treatment and stage definitions,
running a study and retrieving reports.
