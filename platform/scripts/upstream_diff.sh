#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: $0 COMPONENT" >&2
    exit 1
fi

component="$1"
script_dir="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../.." && pwd)"
manifest="$repo_root/platform/upstream-manifest.yaml"
manifest_get="$repo_root/platform/scripts/manifest_get.sh"

upstream_url="$("$manifest_get" "$component" upstream_url "$manifest")"
upstream_ref="$("$manifest_get" "$component" upstream_ref "$manifest")"
patch_queue_path="$("$manifest_get" "$component" patch_queue_path "$manifest")"
extension_source_path="$("$manifest_get" "$component" extension_source_path "$manifest")"

remote_head="$(git ls-remote "$upstream_url" HEAD | awk '{print $1}')"

printf 'component: %s\n' "$component"
printf 'manifest_ref: %s\n' "$upstream_ref"
printf 'remote_head: %s\n' "$remote_head"
printf 'patch_queue_path: %s\n' "$patch_queue_path"
printf 'extension_source_path: %s\n' "$extension_source_path"

if [ -d "$repo_root/$patch_queue_path" ]; then
    printf '\npatch files:\n'
    find "$repo_root/$patch_queue_path" -type f | sed "s#^$repo_root/##" | sort
fi

if [ -d "$repo_root/$extension_source_path" ]; then
    printf '\nextension files:\n'
    find "$repo_root/$extension_source_path" -type f | sed "s#^$repo_root/##" | sort
fi
