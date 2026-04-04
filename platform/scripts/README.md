# Platform Scripts

This directory is the canonical home for platform automation scripts.

- Bootstrap, runtime validation, baseline capture, release gate, and governance
  scripts live here.
- New operational scripts should prefer this directory over the repository root.
- `Makefile` should treat this directory as the primary script surface.

Only keep a script outside this directory when it is a narrow repo helper and
not part of the platform control plane.
