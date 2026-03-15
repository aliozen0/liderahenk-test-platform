# Patch Policy

Bu repo upstream kaynaklari dogrudan fork ederek tasimaz. Nihai model:

- upstream clone + pinned ref
- kucuk wiring patch queue
- additive extension modules
- runtime hook katmani

## Patch Categories

- `full_override`: upstream dosyanin tamamini override eden gecici istisna
- `wiring_patch`: upstream touchpoint icine delegasyon/seam acan ince patch
- `extension_logic`: platforma ait asil davranis
- `runtime_hook`: container-mode monkey patch veya bootstrap hook
- `compat_fix`: schema/entity/uyumluluk zorunlulugu

## Contributor Rules

1. Yeni davranis once extension katmanina eklenir.
2. Upstream dosyaya yeni business logic yazilmaz; delegasyon hook'u acilir.
3. Bir feature icin upstream touchpoint sayisi `3`u geciyorsa yeni provider veya registry interface acilir.
4. `full_override` sadece gecici compatibility istisnasidir ve ADR ile gerekcelendirilir.
5. `platform/upstream-manifest.yaml` disinda upstream ref degisikligi yapilmaz.

## Current Inventory

| Path | Category | Notes |
| --- | --- | --- |
| `services/liderapi/wiring/patches/overlay/src/main/java/tr/org/lider/ldap/LDAPServiceImpl.java` | `full_override` | Presence ve LDAP davranisi halen buyuk touchpoint |
| `services/liderapi/wiring/patches/overlay/src/main/java/tr/org/lider/services/AgentService.java` | `full_override` | Online state ve DTO davranisi halen upstream'e yakin tutuluyor |
| `services/liderapi/wiring/patches/overlay/src/main/java/tr/org/lider/services/DashboardService.java` | `wiring_patch` | Metrics provider delegasyonu |
| `services/liderapi/wiring/patches/overlay/src/main/java/tr/org/lider/services/PluginService.java` | `wiring_patch` | Catalog provider ve seed service delegasyonu |
| `services/liderapi/wiring/patches/overlay/src/main/java/tr/org/lider/services/PluginTaskService.java` | `wiring_patch` | Feature catalog delegasyonu |
| `services/liderapi/extensions/src/main/java/tr/org/lider/platform/**` | `extension_logic` | Presence, inventory, dashboard, catalog, compat |
| `services/liderui/wiring/patches/overlay/src/**` | `wiring_patch` | Wrapper route, role, view giris noktalari |
| `services/liderui/extensions/src/platform/**` | `extension_logic` | Feature registry, guards, routes, wrapper view logic |
| `services/ahenk/hooks/**` | `runtime_hook` | Registration, system, network, plugin, runtime hook'lari |
| `services/ahenk/container_patches.py` | `runtime_hook` | Ince bootstrap dispatcher |
| `services/liderapi/wiring/patches/overlay/src/main/java/tr/org/lider/entities/ProfileImpl.java` | `compat_fix` | Schema uyumlulugu |
| `services/liderapi/wiring/patches/overlay/src/main/java/tr/org/lider/entities/OperationLogImpl.java` | `compat_fix` | Schema uyumlulugu |
| `services/liderapi/wiring/patches/overlay/src/main/java/tr/org/lider/entities/CommandExecutionImpl.java` | `compat_fix` | Schema uyumlulugu |
