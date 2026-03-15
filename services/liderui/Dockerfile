FROM node:16-bullseye-slim AS builder

ARG LIDERUI_UPSTREAM_REF=

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY platform /workspace/platform
COPY services/liderui /workspace/services/liderui

RUN chmod +x /workspace/platform/scripts/*.sh
RUN REPO_ROOT=/workspace LIDERUI_UPSTREAM_REF="${LIDERUI_UPSTREAM_REF}" \
    /workspace/platform/scripts/prepare_component_source.sh liderui /app

WORKDIR /app

RUN sed -i 's/"node-sass":.*/"sass": "^1.57.0",/' package.json 2>/dev/null || true
RUN yarn install --network-timeout 300000
RUN yarn build

# Stage 2: Runtime
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY services/liderui/nginx.conf /etc/nginx/conf.d/default.conf
COPY services/liderui/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
