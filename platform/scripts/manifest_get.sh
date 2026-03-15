#!/bin/sh
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "usage: $0 COMPONENT FIELD [MANIFEST]" >&2
    exit 1
fi

component="$1"
field="$2"
manifest="${3:-$(dirname "$0")/../upstream-manifest.yaml}"

value="$(
    awk -v component="$component" -v field="$field" '
        $1 == "-" && $2 == "component:" {
            in_component = ($3 == component)
            next
        }
        in_component && $1 == field ":" {
            sub("^[^:]+:[[:space:]]*", "", $0)
            gsub(/^"|"$/, "", $0)
            print $0
            exit
        }
    ' "$manifest"
)"

if [ -z "$value" ]; then
    echo "missing field '$field' for component '$component' in $manifest" >&2
    exit 1
fi

printf '%s\n' "$value"
