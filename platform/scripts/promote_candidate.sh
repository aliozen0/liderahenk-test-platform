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

python3 - "$manifest" "$component" "$ref" <<'PY'
from pathlib import Path
import sys

manifest = Path(sys.argv[1])
component = sys.argv[2]
new_ref = sys.argv[3]
lines = manifest.read_text(encoding="utf-8").splitlines()

out = []
in_component = False
updated = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith("- component: "):
        in_component = stripped.split(": ", 1)[1] == component
    if in_component and stripped.startswith("upstream_ref: "):
        indent = line[: len(line) - len(line.lstrip())]
        out.append(f"{indent}upstream_ref: {new_ref}")
        updated = True
        continue
    out.append(line)

if not updated:
    raise SystemExit(f"component not found: {component}")

manifest.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
