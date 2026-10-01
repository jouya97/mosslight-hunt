"""Single-agent provisional repair attribution."""
from mosslight_hunt.grader.attribution import ATTRIBUTION_POLICY, update_owners

LIVE_POLICY = ATTRIBUTION_POLICY

def update_live_owners(baseline, previous, current, owners, actor, changed, relevance):
    update_owners(baseline, previous, current, owners, actor)
