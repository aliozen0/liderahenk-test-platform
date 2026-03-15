#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "usage: $0 COMPONENT REF" >&2
    exit 1
fi

component="$1"
ref="$2"
repo_root="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"

case "$component" in
    liderapi)
        env_name="LIDERAPI_UPSTREAM_REF"
        service="liderapi"
        compose_args="-f compose/compose.core.yml -f compose/compose.lider.yml"
        ;;
    liderui)
        env_name="LIDERUI_UPSTREAM_REF"
        service="lider-ui"
        compose_args="-f compose/compose.core.yml -f compose/compose.lider.yml"
        ;;
    ahenk)
        env_name="AHENK_UPSTREAM_SHA"
        service="ahenk"
        compose_args="-f compose/compose.core.yml -f compose/compose.lider.yml -f compose/compose.agents.yml"
        ;;
    *)
        echo "unsupported component: $component" >&2
        exit 1
        ;;
esac

(
    cd "$repo_root"
    env "$env_name=$ref" docker compose --env-file .env $compose_args -p liderahenk-test build "$service"
    PROFILE="${PROFILE:-v1-broad}" make test-acceptance PROFILE="${PROFILE:-v1-broad}"
)
