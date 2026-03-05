#!/bin/sh
# LiderUI — Runtime Environment Injection Entrypoint
# LIDER_API_URL ve LIDER_API_VERSION değerlerini window.__ENV__ olarak
# index.html'e enjekte eder, sonra nginx başlatır.

set -e

# Varsayılan değerler
LIDER_API_URL="${LIDER_API_URL:-http://localhost:8080}"
LIDER_API_VERSION="${LIDER_API_VERSION:-v1}"

INDEX_FILE="/usr/share/nginx/html/index.html"

if [ -f "$INDEX_FILE" ]; then
  # window.__ENV__ script bloğu oluştur
  ENV_SCRIPT="<script>window.__ENV__={LIDER_API_URL:\"${LIDER_API_URL}\",LIDER_API_VERSION:\"${LIDER_API_VERSION}\"};</script>"

  # </head> etiketinden hemen önce enjekte et
  sed -i "s|</head>|${ENV_SCRIPT}</head>|" "$INDEX_FILE"

  echo "✅ Runtime env enjekte edildi:"
  echo "   LIDER_API_URL=${LIDER_API_URL}"
  echo "   LIDER_API_VERSION=${LIDER_API_VERSION}"
else
  echo "⚠️  index.html bulunamadı: ${INDEX_FILE}"
fi

# Nginx'i foreground'da başlat
exec nginx -g "daemon off;"
