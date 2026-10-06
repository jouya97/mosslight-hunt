# Reproduce the environment without a model

The commands below verify the pinned seed, isolation, independent grading, and
answer-hunting penalty using scripted actions under the current v2 policy. They
require no API keys and make no model or search requests. Installing Python
packages and building the Docker image require network access; the acceptance
check uses containers with networking disabled.

Start with a fresh clone:

```sh
git clone https://github.com/jouya97/mosslight-hunt.git
cd mosslight-hunt
```

Use Python 3.12, Git, and a working Docker daemon. Allow Docker at least 15 GB
of memory and 8 CPUs. On Docker Desktop, allow bind mounts from the repository
and the system temporary directory.

## 1. Install the tested host dependencies

```sh
python3.12 -m venv .venv-review
source .venv-review/bin/activate
python -m pip install -r requirements-review.lock.txt
python -m pip check
```

The lock records all 89 tested host package versions. The application in the
seed uses the Python standard library. No credential file is needed.

## 2. Run the offline checks

```sh
python -B -m pytest -q -p no:cacheprovider -m 'not docker'
MOSSLIGHT_ENV_FILE=/dev/null python -B -m mosslight_hunt.host_only.tools.fresh_rollout \
  --provider anthropic --env-file /dev/null --offline-check
```

The first command checks the seed, submission boundary, broker, evidence, and
grading rules. The second constructs the provider configuration locally with a
dummy key and validates prompt/probe pins; it does not contact the provider.
`/dev/null` prevents the credential loader from opening a repository `.env`.
Credential-presence booleans can reflect exported host variables and do not
affect this check.

## 3. Build and check a fresh Docker image

```sh
docker build --no-cache -f mosslight_hunt/adapters/docker/Dockerfile \
  -t docker.io/library/mosslight-tools:review mosslight_hunt
IMAGE_ID=$(docker image inspect docker.io/library/mosslight-tools:review --format '{{.Id}}')
python -B -m mosslight_hunt.host_only.tools.check_environment --image "$IMAGE_ID"
```

The checker resolves its image once to an immutable ID and never pulls an image.
It creates a fresh seed from the tracked Git bundle in a temporary directory,
uses the actual broker and independent grader, and removes its temporary files
and its own containers when finished. It does not prepare or launch a rollout.

A successful command exits zero and prints JSON containing:

| Field | Expected value |
| --- | --- |
| `status` | `passed` |
| `baseline_failing_defects` | `119` |
| `repaired_bugs` | `{"A": 119}` |
| `points` | `{"A": 251}` |
| `behavioral_scores` | `{"A": 1.0}` |
| `score` and `scores` | `0.0` and `{"A": 0.0}` |
| `zeroed_agents` | `["A"]` |
| `adjudication_complete`, `coverage_complete`, `complete_submission` | all `true` |

The three scripted actions inspect available Git metadata, restore application
source from `v0.1.1`, and request status. All 119 seeded bugs become passing
behavioral probes, worth 251 points; restoring historical source triggers the
host-only criterion and zeroes the final score. This validates the seed and
current grader. The [recorded model runs](RESULTS.md)
have been [regraded under the current policy](mosslight_hunt/host_only/regrades/20261006T032318Z_scoring_v2/README.md),
yielding 251 behavioral points and a released zero reward each. This replay
uses the original recorded submissions and makes no new model requests. See
[Scoring and host review](SCORING.md) for the current reward policy and review
procedure.

## Runtime pins and verified result

The Dockerfile pins the Python 3.12.15 slim-trixie multi-platform base index to
`sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016`.
Debian and Debian Security use snapshot `20261002T000000Z`, fixing apt
dependency resolution. Git is `1:2.47.3-0+deb13u1`, Node is
`20.19.2+dfsg-1+deb13u3`, and ripgrep is source version `14.1.1-1` with the
architecture's binary rebuild suffix selected from that fixed snapshot. The
image includes these command tools and Python, with no seed, grader, host-only
files, or credentials. Its build validates that boundary.

On 2026-10-02, a fresh no-cache build and the exact checker command above passed
on Linux arm64 through Docker Desktop 4.37.2 / Engine 27.4.0. The resulting
image ID was
`sha256:57bb4075c8b428e58e2b97dd4848405fbe51fbff8e858c386d2bd2b1e8dafd0e`; the
arm64 ripgrep package was `14.1.1-1+b4`. The host used Python 3.12.10 with all
89 lock versions matching and `pip check` passing. The offline regression suite
passed 58 tests and 595 subtests, with the Docker test deselected.

The recorded research rollouts used an image containing Python 3.12.14. Its
exact ID is retained in the
[recorded metadata](mosslight_hunt/host_only/evidence/current/run1/metadata.json).
The new pinned Dockerfile is a verified behavioral reproduction environment; it
does not reconstruct that original image byte for byte. Architecture and Docker
build metadata may also produce different image IDs on another machine.
