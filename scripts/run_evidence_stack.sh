#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROJECT_NAME="${EVIDENCE_PROJECT_NAME:-liderahenk-test-evidence}"
DEFAULT_N="$(grep '^AHENK_COUNT=' .env | cut -d= -f2)"
N="${N:-$DEFAULT_N}"

COMPOSE_ARGS=(
  --env-file .env
  -f compose/compose.core.yml
  -f compose/compose.lider.yml
  -f compose/compose.agents.yml
  -f compose/compose.obs.yml
  -f compose/compose.tracing.yml
  -p "$PROJECT_NAME"
)

cleanup() {
  docker compose "${COMPOSE_ARGS[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}

if docker ps --format '{{.Names}}' | grep -Eq '^liderahenk-test-'; then
  echo "Shared liderahenk-test stack is running. Stop it before isolated evidence runs."
  exit 1
fi

trap cleanup EXIT

echo "Starting disposable evidence stack: $PROJECT_NAME"
docker compose "${COMPOSE_ARGS[@]}" up -d --build --scale ahenk="$N"

echo "Waiting for services to settle..."
sleep 20

python3 -m pip install --break-system-packages -r requirements-test.txt -q
PYTHONPATH=. pytest tests/test_observability.py tests/test_evidence_pipeline.py -v --timeout=120
