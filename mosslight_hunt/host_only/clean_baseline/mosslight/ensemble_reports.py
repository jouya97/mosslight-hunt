"""Paired comparisons over independent source gardens, including failed plans."""
from __future__ import annotations

from .ensemble_compute import measurement

METRICS = ("coverage", "richness", "diversity", "vitality", "moisture", "nutrients", "shade")


def summarize(definition, outcomes):
    """Match by source identity, then average complete pairs at each elapsed offset.

    Failed members are named explicitly. A treatment failure never removes that
    garden's control from another treatment's comparison. Equal-valued saves
    still represent distinct members of the requested cohort.
    """
    controls = {row["identity"]["replicate"]: row for row in outcomes
                if row["identity"]["treatment"] == "control" and row["payload"]["status"] == "complete"}
    comparisons = []
    for treatment in definition["treatments"]:
        rows = {row["identity"]["replicate"]: row for row in outcomes
                if row["identity"]["treatment"] == treatment["name"]}
        paired_ids = [replicate for replicate in definition["replicates"]
                      if replicate in controls and replicate in rows
                      and rows[replicate]["payload"]["status"] == "complete"]
        pairs = [(controls[replicate], rows[replicate]) for replicate in paired_ids]
        series = []
        if pairs:
            for index, sample in enumerate(pairs[0][0]["payload"]["samples"]):
                delta = {}
                for metric in METRICS:
                    values = [measurement(trial["payload"]["samples"][index], metric)
                              - measurement(control["payload"]["samples"][index], metric)
                              for control, trial in pairs]
                    delta[metric] = round(sum(values) / len(values), 6)
                series.append({"offset": sample["offset"], "pairs": len(pairs), "mean_delta": delta})
        comparisons.append({"name": treatment["name"], "paired_replicates": paired_ids,
                            "excluded_replicates": [r for r in definition["replicates"] if r not in paired_ids],
                            "series": series, "final_delta": series[-1]["mean_delta"] if series else None})
    return {"replicates": definition["replicates"], "comparisons": comparisons,
            "outcomes": outcomes}
