# Platform Scenario Packs

This directory is the canonical home for scenario-pack definitions used by the
platform runtime.

- Runtime operational checks, acceptance summary, and release-gate logic read
  scenario packs from here.
- `PLATFORM_SCENARIO_PACKS` activates packs from this directory.
- Session-pack mappings also resolve into this surface.

This directory is separate from `/home/huma/liderahenk-test/orchestrator/legacy_scenarios/`,
which remains the legacy/simple scenario runner input.
