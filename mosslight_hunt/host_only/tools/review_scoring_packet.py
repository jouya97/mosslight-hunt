"""Print the complete code/input inventory for reviewing current reward production.

Run: python3 -m mosslight_hunt.host_only.tools.review_scoring_packet
The grader packet and the host integration boundary have separate totals. Each
row carries a checksum so a saved packet can be tied to the exact reviewed files.
"""
import json
from mosslight_hunt.grader.probes import reviewer_inventory


if __name__ == '__main__':
    print(json.dumps(reviewer_inventory(), indent=2))
