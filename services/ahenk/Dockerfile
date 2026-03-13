# ===========================================================
# Ahenk Agent — Multi-Stage Dockerfile
# Birincil: GitHub'dan gerçek Ahenk kodunu çeker
# Fallback: dummy_ahenk.py (raw XMPP client)
# ===========================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# Fallback agent'ı builder'a kopyala (git clone başarısız olursa kullanılır)
COPY dummy_ahenk.py /build/fallback/dummy_ahenk.py

ARG AHENK_GIT_URL=https://github.com/Pardus-LiderAhenk/ahenk.git

WORKDIR /build
RUN git clone --depth 1 ${AHENK_GIT_URL} . || \
    (echo "⚠️  Git clone başarısız — fallback XMPP agent kullanılıyor" && \
     cp /build/fallback/dummy_ahenk.py /build/ahenk.py && \
     echo "slixmpp>=1.8.4" > /build/requirements.txt)

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

ENTRYPOINT ["/entrypoint.sh"]
