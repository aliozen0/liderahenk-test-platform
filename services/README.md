# Runtime Services

This directory contains the runtime service build contexts.

- Each subdirectory represents a service image or service-specific wiring
  surface used by the composed LiderAhenk runtime.
- Upstream-derived service seams, patches, and Dockerfiles belong here.
- This is the main home for runtime services such as `liderapi`, `liderui`,
  `lidercore`, `ldap`, `mariadb`, and `ejabberd`.

If a service is platform-owned and exists outside the upstream product model,
prefer `/home/huma/liderahenk-test/platform/services/`.
