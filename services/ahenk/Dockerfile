# ===========================================================
# Ahenk Agent — Upstream Dockerfile
# ===========================================================

FROM python:3.12-slim AS builder

ARG AHENK_UPSTREAM_SHA=c0f216b05c335883d5b35bf606eac39bcb98b4bd

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY platform /workspace/platform
COPY services/ahenk /workspace/services/ahenk

RUN chmod +x /workspace/platform/scripts/*.sh
RUN REPO_ROOT=/workspace AHENK_UPSTREAM_SHA="${AHENK_UPSTREAM_SHA}" \
    /workspace/platform/scripts/prepare_component_source.sh ahenk /build/ahenk

RUN pip install --no-cache-dir \
        distro \
        netifaces \
        paramiko \
        psutil \
        py-cpuinfo \
        slixmpp \
        watchdog

FROM python:3.12-slim AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        iproute2 \
        nmap \
        passwd \
        procps \
        util-linux \
        whois \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -r -m -d /home/ahenk -s /bin/bash ahenk \
    && mkdir -p /etc/ahenk/config.d /opt/ahenk-patches /var/db \
    && chown -R ahenk:ahenk /etc/ahenk /opt/ahenk-patches /var/db

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build/ahenk /app/ahenk

COPY services/ahenk/dummy_ahenk.py /app/dummy_ahenk.py
COPY services/ahenk/container_patches.py /opt/ahenk-patches/container_patches.py
COPY services/ahenk/sitecustomize.py /opt/ahenk-patches/sitecustomize.py
COPY services/ahenk/entrypoint.sh /entrypoint.sh
COPY services/ahenk/hooks /opt/ahenk-patches/hooks

RUN chmod +x /entrypoint.sh \
    && chown -R ahenk:ahenk /app /opt/ahenk-patches

ENTRYPOINT ["/entrypoint.sh"]
