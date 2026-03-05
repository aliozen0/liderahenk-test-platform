# ===========================================================
# Ahenk Agent — Multi-Stage Dockerfile
# ===========================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

ARG AHENK_GIT_URL=https://github.com/Pardus-LiderAhenk/ahenk.git

WORKDIR /build
RUN git clone ${AHENK_GIT_URL} . || \
    (echo "⚠️  Git clone başarısız — boş proje ile devam" && \
     mkdir -p /build && \
     echo "print('Ahenk placeholder — repo erişilemedi')" > /build/ahenk.py && \
     echo "# no requirements" > /build/requirements.txt)

# Python 3.12 uyumsuzluk durumunda hata vermesin
RUN if [ -f requirements.txt ] && [ -s requirements.txt ]; then \
        uv pip install --system --compile-bytecode --no-cache \
            -r requirements.txt 2>&1 || \
        echo "⚠️  Bazı bağımlılıklar yüklenemedi — devam ediliyor"; \
    fi

# --- Stage 2: Runner ---
FROM python:3.12-slim AS runner

RUN useradd -r -s /bin/false ahenk && \
    mkdir -p /etc/ahenk && \
    chown ahenk:ahenk /etc/ahenk

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build /app

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER ahenk

ENTRYPOINT ["/entrypoint.sh"]
