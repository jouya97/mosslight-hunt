# Build context is mosslight_hunt/:
#   docker build -f mosslight_hunt/adapters/docker/Dockerfile -t docker.io/library/mosslight-tools:review mosslight_hunt
#
# One image, two uses. The host broker (harness/) and the host grader start
# every container from it with --network none, a read-only root and dropped
# capabilities; no container outlives its command.
#
#   /workspace   tool container, one per agent action, run as the host uid: a
#                bind mount of that action's private copy of the shared
#                checkout, agent-writable. The broker merges it back afterwards.
#   /candidate   candidate container, one per probe, run as nobody: a
#                read-only bind mount of a freshly extracted committed
#                snapshot. Live-board checks also mount their own /check.py
#                read-only; final grading only prints observations.
#
# The trusted grader runs on the host, observing candidate execution in a fresh
# read-only /candidate container for each probe. The host entrypoint is
# (python -m mosslight_hunt.grader.grader <protected>) and compares those
# observations with answers that never leave the host. grader/ and host_only/
# never enter the image: .dockerignore keeps the whole build context out, and
# the build fails below if any of it, or any grader/host data, is present.
FROM python:3.12-slim@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016

# Python 3.12.15 / Debian trixie, immutable multi-platform base index.
# A dated Debian snapshot also fixes transitive apt dependencies. ripgrep's
# binary rebuild suffix differs by architecture; its source version is pinned
# and the snapshot fixes the selected architecture's exact binary revision.
RUN sed -i \
      -e 's|http://deb.debian.org/debian-security|https://snapshot.debian.org/archive/debian-security/20261002T000000Z|' \
      -e 's|http://deb.debian.org/debian|https://snapshot.debian.org/archive/debian/20261002T000000Z|' \
      /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends \
         git=1:2.47.3-0+deb13u1 \
         nodejs=20.19.2+dfsg-1+deb13u3 \
         'ripgrep=14.1.1-1*' \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /workspace

# Copies nothing when .dockerignore is intact; used only to prove that.
COPY . /tmp/build-context/

# Fail the build rather than ship an image that carries grader or host data,
# a non-empty /workspace, or a different toolchain.
RUN set -eu; \
    if [ -n "$(find /tmp/build-context -mindepth 1 -print -quit)" ]; then \
      echo "FATAL: build context reached the image; restore mosslight_hunt/.dockerignore" >&2; exit 1; fi; \
    rm -rf /tmp/build-context; \
    for sealed in /grader /host_only /mosslight_hunt /candidate; do \
      if [ -e "$sealed" ]; then echo "FATAL: $sealed is in the image" >&2; exit 1; fi; \
    done; \
    leaked="$(find / -xdev \( -name host_only -o -name grader_data -o -name reference_solution \
      -o -name submission_contract.py -o -name manifest.json -o -name events.jsonl \) -print -quit)"; \
    if [ -n "$leaked" ]; then echo "FATAL: grader/host data in the image: $leaked" >&2; exit 1; fi; \
    if [ -n "$(ls -A /workspace)" ]; then echo "FATAL: /workspace must be empty; it is bind-mounted per action" >&2; exit 1; fi; \
    git --version && node --version && rg --version >/dev/null && python --version
