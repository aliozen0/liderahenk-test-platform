# ============================================
# LiderUI — Vue.js Nginx Build
# ============================================
# Stage 1: Build
# node:16-bullseye-slim — Python 3.9 ile uyumlu
FROM node:16-bullseye-slim AS builder

# Build bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG LIDERUI_GIT_URL=https://github.com/Pardus-LiderAhenk/liderui.git

WORKDIR /app

RUN git clone ${LIDERUI_GIT_URL} .

# node-sass deprecated ve native compilation sorunlu,
# dart-sass ile değiştir (drop-in replacement)
RUN sed -i 's/"node-sass":.*/"sass": "^1.57.0",/' package.json 2>/dev/null || true

COPY patches/ /tmp/ui-patches/
RUN cp -a /tmp/ui-patches/. /app/

RUN yarn install --network-timeout 300000

RUN yarn build

# Stage 2: Runtime
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
