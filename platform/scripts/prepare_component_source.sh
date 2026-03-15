#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "usage: $0 COMPONENT TARGET_DIR" >&2
    exit 1
fi

component="$1"
target_dir="$2"
script_dir="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
repo_root="${REPO_ROOT:-$(CDPATH= cd -- "$script_dir/../.." && pwd)}"
manifest="$repo_root/platform/upstream-manifest.yaml"
manifest_get="$repo_root/platform/scripts/manifest_get.sh"

upstream_url="$("$manifest_get" "$component" upstream_url "$manifest")"
upstream_ref="$("$manifest_get" "$component" upstream_ref "$manifest")"
patch_queue_path="$("$manifest_get" "$component" patch_queue_path "$manifest")"
extension_source_path="$("$manifest_get" "$component" extension_source_path "$manifest")"

override_var="$(printf '%s' "$component" | tr '[:lower:]-' '[:upper:]_')_UPSTREAM_REF"
override_ref="$(printenv "$override_var" 2>/dev/null || true)"
if [ "$component" = "ahenk" ] && [ -z "$override_ref" ]; then
    override_ref="${AHENK_UPSTREAM_SHA:-}"
fi
if [ -n "$override_ref" ]; then
    upstream_ref="$override_ref"
fi

rm -rf "$target_dir"
mkdir -p "$(dirname "$target_dir")"
git clone "$upstream_url" "$target_dir"
(
    cd "$target_dir"
    git checkout --detach "$upstream_ref"
)

overlay_dir="$repo_root/$patch_queue_path/overlay"
queue_dir="$repo_root/$patch_queue_path/queue"

if [ -d "$queue_dir" ]; then
    find "$queue_dir" -type f -name '*.patch' | sort | while read -r patch_file; do
        (
            cd "$target_dir"
            git apply "$patch_file"
        )
    done
fi

if [ -d "$overlay_dir" ]; then
    cp -a "$overlay_dir"/. "$target_dir"/
fi

extension_dir="$repo_root/$extension_source_path"
if [ -d "$extension_dir" ]; then
    case "$component" in
        liderapi)
            if [ -d "$extension_dir/src/main/java" ]; then
                mkdir -p "$target_dir/src/main/java"
                cp -a "$extension_dir/src/main/java"/. "$target_dir/src/main/java"/
            fi
            if [ -d "$extension_dir/src/main/resources" ]; then
                mkdir -p "$target_dir/src/main/resources"
                cp -a "$extension_dir/src/main/resources"/. "$target_dir/src/main/resources"/
            fi
            ;;
        liderui)
            if [ -d "$extension_dir/src" ]; then
                mkdir -p "$target_dir/src"
                cp -a "$extension_dir/src"/. "$target_dir/src"/
            fi
            ;;
        ahenk)
            ;;
    esac
fi
