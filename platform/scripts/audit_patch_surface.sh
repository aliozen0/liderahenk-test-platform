#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
repo_root="${REPO_ROOT:-$(CDPATH= cd -- "$script_dir/../.." && pwd)}"
inventory="$repo_root/platform/patch-inventory.csv"

python3 - "$repo_root" "$inventory" <<'PY'
import csv
import pathlib
import sys

repo_root = pathlib.Path(sys.argv[1])
inventory_path = pathlib.Path(sys.argv[2])

tracked_surfaces = []
tracked_surfaces.extend(repo_root.glob("services/liderapi/wiring/patches/overlay/**/*.java"))
tracked_surfaces.extend(repo_root.glob("services/liderapi/wiring/patches/queue/*.patch"))
tracked_surfaces.extend(repo_root.glob("services/liderui/wiring/patches/overlay/**/*"))
tracked_surfaces.extend(repo_root.glob("services/liderui/wiring/patches/queue/*.patch"))
tracked_surfaces.extend(repo_root.glob("services/liderui/extensions/src/platform/views/**/*.vue"))
tracked_surfaces.extend(repo_root.glob("services/ahenk/container_patches.py"))
tracked_surfaces.extend(repo_root.glob("services/ahenk/hooks/*.py"))

tracked_files = sorted(
    str(path.relative_to(repo_root))
    for path in tracked_surfaces
    if path.is_file()
)

with inventory_path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))

inventory_paths = {row["path"] for row in rows}
uncatalogued = [path for path in tracked_files if path not in inventory_paths]

full_override = [row for row in rows if row["category"] in {"full_override", "full_view_copy"}]
queue_patch = [row for row in rows if row["category"] == "queue_patch"]

print("Patch surface audit")
print(f"- tracked files: {len(tracked_files)}")
print(f"- inventory rows: {len(rows)}")
print(f"- queue patches: {len(queue_patch)}")
print(f"- remaining heavy overrides: {len(full_override)}")
for row in full_override:
    print(f"  - {row['path']} [{row['category']}] -> {row['target_state']}")

if uncatalogued:
    print("- uncatalogued files:")
    for path in uncatalogued:
        print(f"  - {path}")
    raise SystemExit(1)
PY
