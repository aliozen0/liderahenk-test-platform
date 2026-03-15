# E2E Test Lane

`tests/e2e` is the official browser-driven acceptance lane for LiderAhenk.

## Goals

- Keep smoke coverage fast and reliable.
- Use UI assertions for user-visible behavior.
- Use backend checks only for long-running or eventually consistent actions.
- Always leave useful failure artifacts behind.

## Structure

- `config/`: runtime settings and environment-driven defaults
- `pages/`: route-oriented page objects
- `specs/auth/`: login and smoke scenarios
- `specs/management/`: hybrid management flows
- `support/`: backend facade and shared helpers

## Standard Fixtures

- `ui_page`: fresh Playwright page with tracing, video, and failure capture
- `authenticated_page`: logs in through the real UI before the scenario starts
- `backend`: direct facade over Lider API and XMPP
- `ready_backend`: waits for agent registration and XMPP readiness

## Markers

- `e2e`: every browser-driven scenario
- `smoke`: fast release-safe login and navigation coverage
- `management`: computer-management and task-related flows
- `hybrid`: UI + backend evidence in the same scenario

## Failure Artifacts

Artifacts are written under `artifacts/e2e/` per test case.

Captured on failure:

- `final-state.png`
- `dom.html`
- `trace.zip`
- `video.webm`
- `console.log`
- `page-errors.log`
- `request-failures.log`
- `metadata.json`

## Authoring Rules

- Prefer route-specific root selectors such as `.dashboard` or `.computer-management`.
- Prefer stable structural selectors over brittle positional selectors.
- Keep UI flows deterministic; use the backend facade only where UI timing would make the test flaky.
- If a scenario mutates the platform, assert the user-visible entry point first and the backend result second.

## Commands

- `make test-e2e`
- `make test-e2e-smoke`
- `make test-e2e-management`
- `make test-release-gate`
