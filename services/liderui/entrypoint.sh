#!/bin/sh
# LiderUI — Runtime Environment Injection Entrypoint
# LIDER_API_URL ve LIDER_API_VERSION değerlerini window.__ENV__ olarak
# index.html'e enjekte eder, sonra nginx başlatır.

set -e

# Varsayılan değerler
LIDER_API_URL="${LIDER_API_URL:-http://localhost:8080}"
LIDER_API_VERSION="${LIDER_API_VERSION:-v1}"
LIDER_FEATURE_PROFILE="${LIDER_FEATURE_PROFILE:-v1-broad}"
UI_DISABLED_FEATURES="${UI_DISABLED_FEATURES:-}"

INDEX_FILE="/usr/share/nginx/html/index.html"

if [ -f "$INDEX_FILE" ]; then
  # window.__ENV__ script bloğu oluştur
  ESCAPED_DISABLED_FEATURES=$(printf '%s' "${UI_DISABLED_FEATURES}" | sed 's/\\/\\\\/g; s/"/\\"/g')
  ENV_SCRIPT="<script>window.__ENV__={LIDER_API_URL:\"${LIDER_API_URL}\",LIDER_API_VERSION:\"${LIDER_API_VERSION}\",LIDER_FEATURE_PROFILE:\"${LIDER_FEATURE_PROFILE}\",UI_DISABLED_FEATURES:\"${ESCAPED_DISABLED_FEATURES}\"};</script>"

  # </head> etiketinden hemen önce enjekte et
  sed -i "s|</head>|${ENV_SCRIPT}</head>|" "$INDEX_FILE"

  echo "✅ Runtime env enjekte edildi:"
  echo "   LIDER_API_URL=${LIDER_API_URL}"
  echo "   LIDER_API_VERSION=${LIDER_API_VERSION}"
  echo "   LIDER_FEATURE_PROFILE=${LIDER_FEATURE_PROFILE}"
  echo "   UI_DISABLED_FEATURES=${UI_DISABLED_FEATURES}"
else
  echo "⚠️  index.html bulunamadı: ${INDEX_FILE}"
fi

# Nginx'i foreground'da başlat
exec nginx -g "daemon off;"
