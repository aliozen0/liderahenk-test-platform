#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "usage: $0 COMPONENT REF" >&2
    exit 1
fi

component="$1"
ref="$2"
repo_root="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
manifest="$repo_root/platform/upstream-manifest.yaml"
manifest_get="$repo_root/platform/scripts/manifest_get.sh"

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

acceptance_profile="$("$manifest_get" "$component" acceptance_profile "$manifest")"

(
    cd "$repo_root"
    env "$env_name=$ref" docker compose --env-file .env $compose_args -p liderahenk-test build "$service"
    PROFILE="${PROFILE:-$acceptance_profile}" make test-release-gate PROFILE="${PROFILE:-$acceptance_profile}"
)
