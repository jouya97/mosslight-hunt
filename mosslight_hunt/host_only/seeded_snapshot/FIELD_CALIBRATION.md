# Calibrating study cohorts from field observations

`mosslight.field_calibration.create_field_study` initializes ordinary staged
studies using measured garden moisture. Supply the study store, source worlds,
a mapping from the same garden labels to reading lists, an absolute target
timestamp, treatments and stages. Each reading has numeric `timestamp` (seconds)
and `moisture` (percentage). It returns the study ID and calibration provenance;
save that receipt alongside the ordinary study report. Sources are copied.

The estimator fits an ordinary least-squares linear local trend, evaluates it
at the target timestamp, clips the estimate to 0–100, and rounds once when
initializing the simulator's integer moisture cells. Identical timestamps use
the average. `estimate` exposes the unrounded estimate and `calibrated_sources`
returns the prepared sources plus the full original observations. The caller
chooses a scientifically appropriate observation window; the API does not
infer seasonality or claim the trend is appropriate outside that window.

Absolute epoch timestamps and relative elapsed timestamps describe the same
fit when every reading and target use the same origin. Changing time origin
must not change the initialized garden or its staged study results within
ordinary floating point tolerance. Negative timestamps and fractional seconds
are allowed. Inputs and retained observation receipts remain independently owned.

```python
from mosslight.field_calibration import create_field_study
from mosslight.studies import StudyStore
store = StudyStore('field-study.sqlite')
receipt = create_field_study(store, {'pond': world}, {'pond': [
    {'timestamp': 1750000000, 'moisture': 40},
    {'timestamp': 1750000001, 'moisture': 45},
    {'timestamp': 1750000002, 'moisture': 50},
]}, 1750000003, treatments, [{'until': 5, 'keep': 1}], metric='moisture')
store.close()
```
